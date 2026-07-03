# src/core/linker.py
from typing import List, Dict, Optional, Any
from src.core.ner import NEREngine
from src.core.candidate import CandidateGenerator
from src.core.disambiguate import Disambiguator
from src.core.tracer import LinkTracer
from src.core.coreference import CoreferenceResolver
from src.knowledge.kb_manager import KnowledgeBase
from src.knowledge.vector_index import VectorIndex
from src.models.mention import StandardMention
from src.models.entity import StandardEntity
from src.models.candidate import Candidate
from src.utils.config import get_config
from src.utils.logger import logger, generate_trace_id


class EntityLinker:
    """
    实体链接主流程

    流程:
    1. NER 识别实体 → StandardMention 列表
    2. 知识库链接（候选生成 → 消歧 → NIL检测）
    3. FastCoref 共指消解（按需启用）
    4. 链接留痕 (SQLite)
    """

    # src/core/linker.py - 修改初始化部分

    def __init__(self, config: dict = None):
        """
        初始化实体链接器
        """
        config = config or get_config()
        self.config = config

        # 1. 初始化知识库
        self.kb = KnowledgeBase(config["knowledge_base"])
        logger.info(f"📚 知识库加载完成: {len(self.kb.get_all_entities())} 个实体")

        # 2. 初始化向量索引（传入知识库引用，以便复用缓存）
        self.vector_index = VectorIndex(config["bge_model_path"], kb=self.kb)

        # 3. 构建向量索引（会优先使用KB的缓存）
        self.vector_index.build(self.kb.get_all_entities())

        # 4. 初始化各模块
        self.ner = NEREngine(config["ner"])
        self.candidate_gen = CandidateGenerator(self.kb, self.vector_index)
        self.disambiguator = Disambiguator(config)
        self.tracer = LinkTracer(config.get("tracer_db", "./data/link_records.db"))
        self.coref = CoreferenceResolver(config.get("coreference", {}))

        logger.info("✅ EntityLinker 初始化完成")
        logger.info(f"   📚 知识库: {len(self.kb.get_all_entities())} 个实体")
        logger.info(f"   🔍 向量索引: {self.vector_index.index.ntotal if self.vector_index.index else 0} 个向量")
        logger.info(f"   💾 KB缓存: {'有' if self.kb.has_embeddings() else '无'}")
        logger.info(f"   🔗 共指消解: {'启用' if self.coref.enabled else '禁用'}")

    def link(self, text: str, options: dict = None) -> dict:
        """
        端到端实体链接 (从原始文本到链接结果)

        Args:
            text: 输入文本
            options: 可选参数，支持:
                - enable_coreference: bool, 是否启用共指消解
                - enable_llm_fallback: bool, 是否启用LLM兜底
                - nil_threshold: float, NIL阈值覆盖
                - linkable_types: List[str], 可链接的实体类型覆盖

        Returns:
            dict: {
                "trace_id": str,
                "text": str,
                "results": List[Dict],
                "stats": Dict
            }
        """
        options = options or {}
        trace_id = generate_trace_id()

        logger.info(f"🔍 开始处理: trace_id={trace_id}")
        logger.info(f"📝 文本长度: {len(text)} 字符")
        logger.info(f"📝 文本预览: {text[:100]}...")

        # ============================================================
        # Step 1: NER 识别 → 返回 StandardMention 列表
        # ============================================================
        ner_mentions: List[StandardMention] = self.ner.extract(text)

        if not ner_mentions:
            logger.info("⚠️ 未识别到任何实体")
            return {
                "trace_id": trace_id,
                "text": text,
                "results": [],
                "stats": {
                    "total_mentions": 0,
                    "linked": 0,
                    "nil": 0,
                    "coreference_resolved": 0
                }
            }

        logger.info(f"📌 NER 识别到 {len(ner_mentions)} 个实体: {[m.mention for m in ner_mentions]}")

        # 获取可链接类型 (支持 options 覆盖)
        linkable_types = options.get(
            "linkable_types",
            self.config["ner"].get("linkable_types", ["ORG", "PERSON", "GPE", "LOC"])
        )

        # 过滤: 只处理可链接的实体类型
        filtered_mentions = [m for m in ner_mentions if m.mention_type in linkable_types]
        if len(filtered_mentions) < len(ner_mentions):
            logger.info(f"  过滤后: {len(filtered_mentions)} 个实体需要链接")

        # ============================================================
        # Step 2: 知识库链接（候选生成 → 消歧 → NIL检测）
        # ============================================================
        results = []
        nil_threshold = options.get("nil_threshold", self.disambiguator.nil_threshold)

        for mention_obj in filtered_mentions:
            mention_text = mention_obj.mention
            mention_type = mention_obj.mention_type

            # 候选生成 → 返回 List[Candidate]
            candidates: List[Candidate] = self.candidate_gen.generate(mention_text, top_k=50, context=text)

            if not candidates:
                results.append(mention_obj.to_link_result(
                    entity_id="",
                    standard_name="",
                    confidence=0.0,
                    evidence="无候选实体",
                    is_nil=True
                ))
                logger.info(f"  ❌ 无候选: {mention_text}")
                continue

            # 消歧排序 → 接收 List[Candidate]，返回消歧结果
            disambig_result = self.disambiguator.disambiguate(
                mention_text, candidates, text
            )

            entity: StandardEntity = disambig_result.get("entity")
            score = disambig_result.get("score", 0.0)
            method = disambig_result.get("method", "unknown")
            evidence = disambig_result.get("evidence", "")

            # NIL检测
            if entity and score >= nil_threshold:
                results.append(mention_obj.to_link_result(
                    entity_id=entity.entity_id,
                    standard_name=entity.standard_name,
                    confidence=score,
                    evidence=evidence,
                    is_nil=False
                ))
                logger.info(
                    f"  ✅ 链接成功: {mention_text} → {entity.standard_name} "
                    f"(置信度: {score:.3f}, 方法: {method})"
                )
            else:
                results.append(mention_obj.to_link_result(
                    entity_id="",
                    standard_name="",
                    confidence=score,
                    evidence=f"低于 NIL 阈值 ({nil_threshold})，当前置信度: {score:.3f}",
                    is_nil=True
                ))
                logger.info(f"  ❌ NIL: {mention_text} (置信度: {score:.3f})")

        # ============================================================
        # Step 3: FastCoref 共指消解（独立工作）
        # ============================================================
        coref_enabled = options.get(
            "enable_coreference",
            self.config.get("coreference", {}).get("enabled", False)
        )

        if coref_enabled:
            logger.info("🔗 启用 FastCoref 共指消解...")

            # 3.1 获取 FastCoref 的共指链
            clusters = self.coref.get_clusters(text)
            logger.info(f"   FastCoref 识别到 {len(clusters)} 个共指链")

            # 3.2 构建已链接实体的映射 (mention → result)
            linked_map = {}
            for r in results:
                if not r.get("is_nil", True):
                    mention = r.get("mention", "")
                    if mention:
                        linked_map[mention] = r

            # 3.3 遍历共指链，做代词回链
            resolved_count = 0
            added_mentions = set()
            pronouns = ["它", "其", "该公司", "该企业", "该机构", "该组织",
                        "后者", "前者", "这家", "这家公司", "该集团", "该单位"]

            for cluster in clusters:
                # 找出链中已链接的实体
                linked_mention = None
                linked_result = None

                for mention in cluster:
                    if mention in linked_map:
                        linked_mention = mention
                        linked_result = linked_map[mention]
                        break

                # 如果链中有已链接的实体，将链中其他 mention 回链
                if linked_result is not None:
                    for mention in cluster:
                        # 跳过已链接的实体
                        if mention in linked_map:
                            continue
                        # 避免重复添加
                        if mention in added_mentions:
                            continue

                        # 判断是否是代词
                        is_pronoun = len(mention) <= 3 or mention in pronouns

                        # 创建 StandardMention 并转换为链接结果
                        mention_obj = StandardMention(
                            mention=mention,
                            mention_type="PRON" if is_pronoun else "NOUN",
                            char_start=text.find(mention),
                            char_end=text.find(mention) + len(mention) if mention in text else 0
                        )

                        results.append(mention_obj.to_link_result(
                            entity_id=linked_result.get("entity_id", ""),
                            standard_name=linked_result.get("standard_entity", ""),
                            confidence=linked_result.get("confidence", 0.8) * 0.9,
                            evidence=f"FastCoref: '{mention}'回链到'{linked_mention}'",
                            is_nil=False,
                            is_coreference=True,
                            resolved_from=linked_mention
                        ))
                        added_mentions.add(mention)
                        resolved_count += 1
                        logger.info(f"  🔗 FastCoref: '{mention}' → '{linked_mention}'")

            logger.info(f"   FastCoref 共指解析完成: {resolved_count} 个代词回链")
        else:
            logger.info("⏭️ 共指消解未启用 (设置 enable_coreference=true 可开启)")

        # ============================================================
        # Step 4: 链接留痕
        # ============================================================
        self.tracer.save(trace_id, text, results)

        # 统计信息
        stats = {
            "total_mentions": len(results),
            "linked": sum(1 for r in results if not r.get("is_nil", True)),
            "nil": sum(1 for r in results if r.get("is_nil", True)),
            "coreference_resolved": sum(1 for r in results if r.get("is_coreference", False))
        }

        logger.info(f"📊 统计: 共 {stats['total_mentions']} 个实体, "
                    f"链接 {stats['linked']} 个, NIL {stats['nil']} 个, "
                    f"共指解析 {stats['coreference_resolved']} 个")

        return {
            "trace_id": trace_id,
            "text": text,
            "results": results,
            "stats": stats
        }

    def link_with_mentions(self, text: str, mentions: List[Dict], options: dict = None) -> dict:
        """
        已有 mention 列表时直接链接 (跳过 NER)

        Args:
            text: 原始文本
            mentions: 已识别的 mention 列表，格式: [{"mention": "国网", "type": "ORG"}, ...]
            options: 同 link() 方法

        Returns:
            dict: 同 link() 方法
        """
        options = options or {}
        trace_id = generate_trace_id()

        logger.info(f"🔍 开始处理 (已有mention): trace_id={trace_id}")
        logger.info(f"📝 文本长度: {len(text)} 字符")
        logger.info(f"📌 输入 {len(mentions)} 个 mention")

        if not mentions:
            logger.info("⚠️ 无 mention 输入")
            return {
                "trace_id": trace_id,
                "text": text,
                "results": [],
                "stats": {
                    "total_mentions": 0,
                    "linked": 0,
                    "nil": 0,
                    "coreference_resolved": 0
                }
            }

        # 将输入字典列表转换为 StandardMention 列表
        mention_objs: List[StandardMention] = []
        for m in mentions:
            if isinstance(m, dict):
                mention_objs.append(StandardMention.from_dict(m))
            elif isinstance(m, StandardMention):
                mention_objs.append(m)
            else:
                logger.warning(f"  ⚠️ 跳过无效 mention: {m}")

        if not mention_objs:
            logger.warning("⚠️ 无有效 mention")
            return {
                "trace_id": trace_id,
                "text": text,
                "results": [],
                "stats": {
                    "total_mentions": 0,
                    "linked": 0,
                    "nil": 0,
                    "coreference_resolved": 0
                }
            }

        # # 获取可链接类型
        # linkable_types = options.get(
        #     "linkable_types",
        #     self.config["ner"].get("linkable_types", ["ORG", "PERSON", "GPE", "LOC"])
        # )
        #
        # # 过滤类型
        # filtered_mentions = [m for m in mention_objs if m.mention_type in linkable_types]

        # ============================================================
        # 知识库链接
        # ============================================================
        results = []
        nil_threshold = options.get("nil_threshold", self.disambiguator.nil_threshold)

        for mention_obj in mention_objs:
            mention_text = mention_obj.mention
            mention_type = mention_obj.mention_type

            # 候选生成 → 返回 List[Candidate]
            candidates: List[Candidate] = self.candidate_gen.generate(mention_text, top_k=50, context=text)

            if not candidates:
                results.append(mention_obj.to_link_result(
                    entity_id="",
                    standard_name="",
                    confidence=0.0,
                    evidence="无候选实体",
                    is_nil=True
                ))
                continue

            # 消歧
            disambig_result = self.disambiguator.disambiguate(mention_text, candidates, text)
            entity: StandardEntity = disambig_result.get("entity")
            score = disambig_result.get("score", 0.0)
            method = disambig_result.get("method", "unknown")

            if entity and score >= nil_threshold:
                results.append(mention_obj.to_link_result(
                    entity_id=entity.entity_id,
                    standard_name=entity.standard_name,
                    confidence=score,
                    evidence=disambig_result.get("evidence", ""),
                    is_nil=False
                ))
                logger.info(f"  ✅ 链接成功: {mention_text} → {entity.standard_name} (置信度: {score:.3f})")
            else:
                results.append(mention_obj.to_link_result(
                    entity_id="",
                    standard_name="",
                    confidence=score,
                    evidence=f"低于 NIL 阈值 ({nil_threshold})",
                    is_nil=True
                ))
                logger.info(f"  ❌ NIL: {mention_text} (置信度: {score:.3f})")

        # ============================================================
        # 共指消解
        # ============================================================
        coref_enabled = options.get(
            "enable_coreference",
            self.config.get("coreference", {}).get("enabled", False)
        )

        if coref_enabled:
            logger.info("🔗 启用 FastCoref 共指消解...")
            clusters = self.coref.get_clusters(text)
            logger.info(f"   FastCoref 识别到 {len(clusters)} 个共指链")

            linked_map = {}
            for r in results:
                if not r.get("is_nil", True):
                    mention = r.get("mention", "")
                    if mention:
                        linked_map[mention] = r

            resolved_count = 0
            added_mentions = set()
            pronouns = ["它", "其", "该公司", "该企业", "该机构", "该组织",
                        "后者", "前者", "这家", "这家公司", "该集团", "该单位"]

            for cluster in clusters:
                linked_mention = None
                linked_result = None
                for mention in cluster:
                    if mention in linked_map:
                        linked_mention = mention
                        linked_result = linked_map[mention]
                        break

                if linked_result is not None:
                    for mention in cluster:
                        if mention in linked_map or mention in added_mentions:
                            continue

                        is_pronoun = len(mention) <= 3 or mention in pronouns
                        mention_obj = StandardMention(
                            mention=mention,
                            mention_type="PRON" if is_pronoun else "NOUN",
                            char_start=text.find(mention),
                            char_end=text.find(mention) + len(mention) if mention in text else 0
                        )

                        results.append(mention_obj.to_link_result(
                            entity_id=linked_result.get("entity_id", ""),
                            standard_name=linked_result.get("standard_entity", ""),
                            confidence=linked_result.get("confidence", 0.8) * 0.9,
                            evidence=f"FastCoref: '{mention}'回链到'{linked_mention}'",
                            is_nil=False,
                            is_coreference=True,
                            resolved_from=linked_mention
                        ))
                        added_mentions.add(mention)
                        resolved_count += 1
                        logger.info(f"  🔗 FastCoref: '{mention}' → '{linked_mention}'")

            logger.info(f"   FastCoref 共指解析完成: {resolved_count} 个代词回链")

        # ============================================================
        # 留痕
        # ============================================================
        self.tracer.save(trace_id, text, results)

        stats = {
            "total_mentions": len(results),
            "linked": sum(1 for r in results if not r.get("is_nil", True)),
            "nil": sum(1 for r in results if r.get("is_nil", True)),
            "coreference_resolved": sum(1 for r in results if r.get("is_coreference", False))
        }

        return {
            "trace_id": trace_id,
            "text": text,
            "results": results,
            "stats": stats
        }

    def get_knowledge_base(self) -> List[Dict]:
        """获取知识库所有实体（字典格式）"""
        return self.kb.get_all_entities_dict()

    def get_trace(self, trace_id: str) -> List[Dict]:
        """根据 trace_id 查询留痕记录"""
        return self.tracer.query_by_trace_id(trace_id)