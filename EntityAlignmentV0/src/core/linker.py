# src/core/linker.py
from typing import List, Dict, Optional
from src.core.ner import NEREngine
from src.core.candidate import CandidateGenerator
from src.core.disambiguate import Disambiguator
from src.core.tracer import LinkTracer
from src.core.coreference import CoreferenceResolver
from src.knowledge.kb_manager import KnowledgeBase
from src.knowledge.vector_index import VectorIndex
from src.utils.config import get_config
from src.utils.logger import logger, generate_trace_id


class EntityLinker:
    """
    实体链接主流程

    流程:
    1. HanLP NER 识别实体（用于知识库链接）
    2. 知识库链接（候选生成 → 消歧 → NIL检测）
    3. FastCoref 共指消解（独立工作，不依赖外部 NER）
       - FastCoref 自己的 NER 识别所有提及
       - 形成共指链
       - 将代词回链到已链接的实体
    4. 链接留痕 (SQLite)
    """

    def __init__(self, config: dict = None):
        """
        初始化实体链接器

        Args:
            config: 配置字典，如果不传则自动加载
        """
        config = config or get_config()
        self.config = config

        # 初始化知识库
        self.kb = KnowledgeBase(
            kb_type=config["knowledge_base"]["type"],
            path=config["knowledge_base"]["path"]
        )

        # 初始化向量索引 (BGE)
        self.vector_index = VectorIndex(config["bge_model_path"])
        self.vector_index.build(self.kb.get_all_entities())

        # 初始化各模块
        self.ner = NEREngine(config["ner"])
        self.candidate_gen = CandidateGenerator(self.kb, self.vector_index)
        self.disambiguator = Disambiguator(config)
        self.tracer = LinkTracer(config.get("tracer_db", "./data/link_records.db"))
        self.coref = CoreferenceResolver(config.get("coreference", {}))

        logger.info("✅ EntityLinker 初始化完成")
        logger.info(f"   📚 知识库: {len(self.kb.get_all_entities())} 个实体")
        logger.info(f"   🔍 向量索引: {self.vector_index.index.ntotal if self.vector_index.index else 0} 个向量")
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
        # Step 1: HanLP NER 识别实体（用于知识库链接）
        # ============================================================
        ner_mentions = self.ner.extract(text)
        if not ner_mentions:
            logger.info("⚠️ 未识别到任何实体")
            return {
                "trace_id": trace_id,
                "text": text,
                "results": [],
                "stats": {"total_mentions": 0, "linked": 0, "nil": 0, "coreference_resolved": 0}
            }

        logger.info(f"📌 HanLP NER 识别到 {len(ner_mentions)} 个实体: {[m['mention'] for m in ner_mentions]}")

        # 获取可链接类型 (支持options覆盖)
        linkable_types = options.get("linkable_types",
                                     self.config["ner"].get("linkable_types", ["ORG", "PERSON", "GPE", "LOC"]))

        # 过滤: 只处理可链接的实体类型
        filtered_mentions = [m for m in ner_mentions if m["type"] in linkable_types]
        if len(filtered_mentions) < len(ner_mentions):
            logger.info(f"  过滤后: {len(filtered_mentions)} 个实体需要链接")

        # ============================================================
        # Step 2: 知识库链接（候选生成 → 消歧 → NIL检测）
        # ============================================================
        results = []
        nil_threshold = options.get("nil_threshold", self.disambiguator.nil_threshold)

        for mention_info in filtered_mentions:
            mention = mention_info["mention"]
            mention_type = mention_info["type"]

            # 候选生成
            candidates = self.candidate_gen.generate(mention)

            if not candidates:
                results.append({
                    "mention": mention,
                    "type": mention_type,
                    "is_nil": True,
                    "confidence": 0.0,
                    "evidence": "无候选实体"
                })
                logger.info(f"  ❌ 无候选: {mention}")
                continue

            # 消歧排序
            disambig_result = self.disambiguator.disambiguate(
                mention, candidates, text
            )

            entity = disambig_result.get("entity")
            score = disambig_result.get("score", 0.0)
            method = disambig_result.get("method", "bge")
            evidence = disambig_result.get("evidence", "")

            # NIL检测
            if entity and score >= nil_threshold:
                results.append({
                    "mention": mention,
                    "type": mention_type,
                    "standard_entity": entity["standard_name"],
                    "entity_id": entity["entity_id"],
                    "confidence": score,
                    "is_nil": False,
                    "method": method,
                    "evidence": evidence
                })
                logger.info(
                    f"  ✅ 链接成功: {mention} → {entity['standard_name']} (置信度: {score:.3f}, 方法: {method})")
            else:
                results.append({
                    "mention": mention,
                    "type": mention_type,
                    "is_nil": True,
                    "confidence": score,
                    "evidence": f"低于 NIL 阈值 ({nil_threshold})，当前置信度: {score:.3f}"
                })
                logger.info(f"  ❌ NIL: {mention} (置信度: {score:.3f})")

        # ============================================================
        # Step 3: FastCoref 共指消解（独立工作）
        # ============================================================
        coref_enabled = options.get("enable_coreference",
                                    self.config.get("coreference", {}).get("enabled", False))

        if coref_enabled:
            logger.info("🔗 启用 FastCoref 共指消解...")

            # 3.1 获取 FastCoref 的共指链
            clusters = self.coref.get_clusters(text)
            logger.info(f"   FastCoref 识别到 {len(clusters)} 个共指链")

            # 3.2 构建已链接实体的映射
            linked_map = {}
            for r in results:
                if not r.get("is_nil", True):
                    mention = r.get("mention", "")
                    if mention:
                        linked_map[mention] = r

            # 3.3 遍历共指链，做代词回链
            resolved_count = 0
            added_mentions = set()

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

                        # 判断是否是代词（简单判断：长度较短或在代词列表中）
                        pronouns = ["它", "其", "该公司", "该企业", "该机构", "该组织",
                                    "后者", "前者", "这家", "这家公司", "该集团", "该单位"]
                        is_pronoun = len(mention) <= 3 or mention in pronouns

                        new_result = {
                            "mention": mention,
                            "type": "PRON" if is_pronoun else "NOUN",
                            "standard_entity": linked_result.get("standard_entity"),
                            "entity_id": linked_result.get("entity_id"),
                            "confidence": linked_result.get("confidence", 0.8) * 0.9,
                            "is_nil": False,
                            "is_coreference": True,
                            "resolved_from": linked_mention,
                            "method": "fastcoref",
                            "evidence": f"FastCoref: '{mention}'回链到'{linked_mention}'"
                        }
                        results.append(new_result)
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
                "stats": {"total_mentions": 0, "linked": 0, "nil": 0, "coreference_resolved": 0}
            }

        # 获取可链接类型
        linkable_types = options.get("linkable_types",
                                     self.config["ner"].get("linkable_types", ["ORG", "PERSON", "GPE", "LOC"]))

        results = []
        nil_threshold = options.get("nil_threshold", self.disambiguator.nil_threshold)

        for mention_info in mentions:
            mention = mention_info.get("mention", "")
            mention_type = mention_info.get("type", "UNKNOWN")

            if not mention:
                continue

            # 类型过滤
            if mention_type not in linkable_types:
                logger.info(f"  ⏭️ 跳过: {mention} (类型: {mention_type} 不在可链接列表中)")
                continue

            # 候选生成
            candidates = self.candidate_gen.generate(mention)

            if not candidates:
                results.append({
                    "mention": mention,
                    "type": mention_type,
                    "is_nil": True,
                    "confidence": 0.0,
                    "evidence": "无候选实体"
                })
                continue

            # 消歧
            disambig_result = self.disambiguator.disambiguate(mention, candidates, text)
            entity = disambig_result.get("entity")
            score = disambig_result.get("score", 0.0)

            if entity and score >= nil_threshold:
                results.append({
                    "mention": mention,
                    "type": mention_type,
                    "standard_entity": entity["standard_name"],
                    "entity_id": entity["entity_id"],
                    "confidence": score,
                    "is_nil": False,
                    "method": disambig_result.get("method", "bge"),
                    "evidence": disambig_result.get("evidence", "")
                })
                logger.info(f"  ✅ 链接成功: {mention} → {entity['standard_name']} (置信度: {score:.3f})")
            else:
                results.append({
                    "mention": mention,
                    "type": mention_type,
                    "is_nil": True,
                    "confidence": score,
                    "evidence": f"低于 NIL 阈值 ({nil_threshold})"
                })
                logger.info(f"  ❌ NIL: {mention} (置信度: {score:.3f})")

        # 共指消解
        coref_enabled = options.get("enable_coreference",
                                    self.config.get("coreference", {}).get("enabled", False))

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

                        new_result = {
                            "mention": mention,
                            "type": "PRON",
                            "standard_entity": linked_result.get("standard_entity"),
                            "entity_id": linked_result.get("entity_id"),
                            "confidence": linked_result.get("confidence", 0.8) * 0.9,
                            "is_nil": False,
                            "is_coreference": True,
                            "resolved_from": linked_mention,
                            "method": "fastcoref",
                            "evidence": f"FastCoref: '{mention}'回链到'{linked_mention}'"
                        }
                        results.append(new_result)
                        added_mentions.add(mention)
                        resolved_count += 1
                        logger.info(f"  🔗 FastCoref: '{mention}' → '{linked_mention}'")

            logger.info(f"   FastCoref 共指解析完成: {resolved_count} 个代词回链")

        # 留痕
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
        """获取知识库所有实体"""
        return self.kb.get_all_entities()

    def get_trace(self, trace_id: str) -> List[Dict]:
        """根据 trace_id 查询留痕记录"""
        return self.tracer.query_by_trace_id(trace_id)