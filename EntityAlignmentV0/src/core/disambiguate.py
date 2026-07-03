# src/core/disambiguate.py
"""
消歧精排模块 - 增强语义信息

优化点：
1. 查询文本：包含mention类型、上下文关键信息、实体类型提示
2. 回答文本：包含实体名称、别名、类型、描述、行业、标签等完整语义
"""

import numpy as np
import json
import hashlib
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer, CrossEncoder
from src.models.entity import StandardEntity
from src.models.candidate import Candidate
from src.utils.logger import logger


class Disambiguator:
    """
    消歧精排器 - 增强语义信息版本
    """

    # src/core/disambiguate.py - 修复 Reranker 加载部分

    def __init__(self, config):
        # ============================================================
        # 1. Reranker 模型（精排核心）
        # ============================================================
        self.enable_reranker = config.get("reranker_enabled", False)
        self.reranker_top_k = config.get("reranker_top_k", 10)
        self.reranker_weight = config.get("reranker_weight", 0.7)
        self.bge_weight = config.get("bge_reranker_weight", 0.3)

        self.reranker = None
        if self.enable_reranker:
            reranker_path = config.get("reranker_model_path", "./models_cache/bge-reranker-base")
            try:
                import torch
                from sentence_transformers import CrossEncoder

                # ============================================================
                # 修复：CrossEncoder 直接加载，不使用 .to() 方法
                # 通过 device 参数指定设备
                # ============================================================
                if torch.cuda.is_available():
                    self.reranker = CrossEncoder(reranker_path, device='cuda')
                    logger.info("✅ BGE Reranker 已加载 (GPU)")
                else:
                    self.reranker = CrossEncoder(reranker_path, device='cpu')
                    logger.info("✅ BGE Reranker 已加载 (CPU)")
                # 注意：新版本 CrossEncoder 不支持 .to() 或 .half()
                # 改用 model 属性访问
                if hasattr(self.reranker, 'model') and torch.cuda.is_available():
                    # 如果模型有 .half() 方法，可以尝试
                    if hasattr(self.reranker.model, 'half'):
                        self.reranker.model.half()
                        logger.info("   Reranker 已转为 FP16")

                logger.info(f"   Top-K: {self.reranker_top_k}")
                logger.info(f"   Reranker权重: {self.reranker_weight}, BGE权重: {self.bge_weight}")

            except Exception as e:
                logger.warning(f"⚠️ Reranker 加载失败: {e}，禁用Reranker")
                self.enable_reranker = False
                self.reranker = None

        # ============================================================
        # 2. 配置参数
        # ============================================================
        self.nil_threshold = config.get("disambiguator", {}).get("nil_threshold", 0.65)
        self.llm_trigger_threshold = config.get("disambiguator", {}).get("bge_llm_trigger_threshold", 0.55)

        # ============================================================
        # 3. LLM 兜底配置
        # ============================================================
        llm_config = config.get("llm_fallback", {})
        self.enable_llm = llm_config.get("enabled", False)
        self.llm_provider = llm_config.get("provider", "openai")
        self.llm_api_key = llm_config.get("api_key")
        self.llm_model = llm_config.get("model", "qwen-max")
        self.llm_base_url = llm_config.get("base_url")
        self.llm_timeout = llm_config.get("timeout", 30)
        self.llm_max_retries = llm_config.get("max_retries", 2)

        # ============================================================
        # 4. 缓存
        # ============================================================
        self.cache_enabled = config.get("llm_fallback", {}).get("cache_enabled", True)
        self.cache_ttl = config.get("llm_fallback", {}).get("cache_ttl", 86400)
        self._cache = {}

        # ============================================================
        # 5. 统计
        # ============================================================
        self.stats = {
            "reranker_calls": 0,
            "llm_calls": 0,
            "llm_cache_hits": 0,
            "llm_errors": 0,
            "avg_llm_time": 0.0,
            "nil_by_score": 0,
            "nil_by_llm": 0,
            "reranker_used": 0
        }

        logger.info("✅ 消歧精排器初始化完成")
        logger.info(f"   📊 NIL阈值: {self.nil_threshold}")
        logger.info(f"   📊 Reranker: {'启用' if self.enable_reranker else '禁用'}")
        if self.enable_llm:
            logger.info(f"   🤖 LLM兜底: {self.llm_provider}/{self.llm_model}")
            logger.info(f"   ⚡ 触发阈值: {self.llm_trigger_threshold}")

    # ============================================================
    # 增强的语义构建方法
    # ============================================================

    # 实体类型中文映射（扩展版）
    TYPE_DISPLAY = {
        # 基础类型
        "ORG": "组织机构",
        "GPE": "地理政治实体（国家/城市/地区）",
        "PERSON": "人物",
        "LOC": "地理位置（山川/河流/景点）",
        # 行业细分
        "GRID_COMPANY": "电网企业（电力输配）",
        "POWER_GENERATOR": "发电企业（电力生产）",
        "NEW_ENERGY_ENTERPRISE": "新能源企业（风电/光伏/储能）",
        "POWER_FACILITY": "电力设施（电站/变电站）",
        "TECHNICAL_TERM": "专业术语（电力/能源领域）",
        "RESEARCH_INSTITUTION": "研究机构",
        "TECH_COMPANY": "科技企业（信息技术/互联网）",
        "FINANCIAL_INSTITUTION": "金融机构（银行/证券/保险）",
        "AUTO_MANUFACTURER": "汽车制造商",
        "GOVERNMENT_AGENCY": "政府机构（部委/厅局）",
        "EDUCATIONAL_INSTITUTION": "教育机构（大学/研究院）",
        "CONSUMER_PRODUCT": "消费品品牌",
        "SOFTWARE_PLATFORM": "软件平台（互联网产品）",
        "ENERGY_ENTERPRISE": "能源企业（综合能源）",
        "STATE_ENTERPRISE": "国有企业（央企/地方国企）",
        "PRIVATE_ENTERPRISE": "民营企业",
        "FOREIGN_ENTERPRISE": "外资企业",
        "JOINT_VENTURE": "合资企业",
        "INDUSTRY_ASSOCIATION": "行业协会/组织",
        "STANDARD_BODY": "标准制定机构",
        "REGULATORY_AGENCY": "监管机构",
        "UNKNOWN": "未知类型"
    }

    def _get_type_display(self, entity_type: str) -> str:
        """获取类型中文显示（带语义说明）"""
        return self.TYPE_DISPLAY.get(entity_type, entity_type)

    def _extract_context_keywords(self, context: str, mention: str) -> str:
        """
        从上下文中提取关键语义信息
        1. 提取提及前后的关键信息
        2. 提取与提及相关的动作/属性
        """
        if not context or not context.strip():
            return ""

        # 找到mention在上下文中的位置
        mention_pos = context.find(mention)

        if mention_pos != -1:
            # 提取mention前后的文本（各50个字符）
            start = max(0, mention_pos - 50)
            end = min(len(context), mention_pos + len(mention) + 50)
            context_fragment = context[start:end]

            # 尝试提取关键信息
            keywords = []

            # 提取“的”字结构（如“公司的”、“集团的”）
            import re

            # 提取动作词（动词）
            action_pattern = r'[，,、。.！!？?\s]*([组织提供发布宣布开展推行推出制定实施进行参与建设发展管理运营)][了着过]?'
            # 简化处理：提取一些关键词
            key_terms = []
            for term in ["成立", "发布", "宣布", "推出", "设立", "组建", "运营", "管理", "服务", "生产", "销售"]:
                if term in context:
                    key_terms.append(term)

            if key_terms:
                keywords.append(f"动作/状态：{'、'.join(key_terms[:3])}")

            # 提取数字/日期信息
            date_pattern = r'(\d{4}年|\d{1,2}月|\d{1,2}日|近期|最近|此前|此前不久)'
            dates = re.findall(date_pattern, context)
            if dates:
                keywords.append(f"时间：{dates[0]}")

            # 提取实体类型线索
            type_clues = {
                "公司": "企业/公司",
                "集团": "企业集团",
                "电网": "电力企业",
                "电力": "电力行业",
                "能源": "能源行业",
                "科技": "科技企业",
                "研究": "研究机构",
                "大学": "教育机构",
                "政府": "政府机构",
                "国家": "国家级机构",
                "国际": "国际组织",
                "协会": "行业协会",
                "基金": "金融/基金",
                "银行": "金融机构",
                "证券": "金融机构",
                "保险": "金融机构",
                "汽车": "汽车制造",
                "智能": "科技/智能化",
                "数字": "数字化/科技",
                "数据": "数据/信息",
                "云": "云计算/科技",
                "AI": "人工智能/科技",
                "人工智能": "人工智能/科技",
                "5G": "通信/科技",
                "芯片": "半导体/科技"
            }

            found_clues = []
            for clue, desc in type_clues.items():
                if clue in context:
                    found_clues.append(desc)

            if found_clues:
                keywords.append(f"领域/类型线索：{'、'.join(found_clues[:3])}")

            # 提取位置信息
            # location_pattern = r'(在[^，,、。.；;：:\s]{1,10}|位于[^，,、。.；;：:\s]{1,10})'
            # locations = re.findall(location_pattern, context)
            # if locations:
            #     keywords.append(f"位置：{locations[0]}")

            if keywords:
                return f"上下文关键信息：{'；'.join(keywords)}"

        return ""

    def _build_enhanced_query(self, mention: str, context: str, mention_type: str = "") -> str:
        """
        构建增强的查询文本

        Args:
            mention: 实体指称
            context: 上下文文本
            mention_type: 实体类型（如果有）
        """
        parts = []

        # 1. 基础信息：提及和类型
        if mention_type and mention_type != "UNKNOWN":
            type_desc = self._get_type_display(mention_type)
            parts.append(f"需要消歧的实体指称：“{mention}”（类型提示：{type_desc}）")
        else:
            parts.append(f"需要消歧的实体指称：“{mention}”")

        # 2. 上下文信息（截取限制）
        if context and context.strip():
            # 截取上下文，避免过长
            context_text = context[:500]
            parts.append(f"所属上下文：{context_text}")

        # 3. 提取的关键语义信息
        key_info = self._extract_context_keywords(context, mention)
        if key_info:
            parts.append(key_info)

        # 4. 明确任务指示
        parts.append(f"请根据以上信息，判断该实体指称“{mention}”对应哪个标准实体？需判断的实体：{mention}，需判断的实体：{mention}，需判断的实体：{mention}，实体“{mention}”对应哪个标准实体？")

        return "；".join(parts)

    def _build_enhanced_passage(self, entity: StandardEntity) -> str:
        """
        构建增强的候选实体描述文本（包含完整语义信息）
        """
        parts = []

        # 1. 实体标识
        parts.append(f"实体ID：{entity.entity_id}")
        parts.append(f"标准名称：{entity.standard_name}")

        # 2. 别名信息
        if entity.aliases:
            aliases_str = "、".join(entity.aliases)
            parts.append(f"别名/简称：{aliases_str}")

        # 3. 类型信息（带语义说明）
        if entity.entity_type and entity.entity_type != "UNKNOWN":
            type_desc = self._get_type_display(entity.entity_type)
            parts.append(f"实体类型：{type_desc}")

        # 4. 描述信息
        if entity.description:
            # 如果描述较长，适当截取
            desc = entity.description[:200]
            parts.append(f"实体描述：{desc}")

        # 5. 行业信息（从metadata获取）
        industry = entity.metadata.get("industry", "")
        if industry:
            parts.append(f"所属行业/领域：{industry}")

        # 6. 标签信息
        tags = entity.metadata.get("tags", [])
        if tags:
            tags_str = "、".join(tags[:5])
            parts.append(f"标签/关键词：{tags_str}")

        # 7. 其他元信息
        abbreviation = entity.metadata.get("abbreviation", "")
        if abbreviation:
            parts.append(f"缩写：{abbreviation}")

        source = entity.metadata.get("source", "")
        if source:
            parts.append(f"数据来源：{source}")

        # 8. 实体特征总结
        if entity.description and entity.entity_type:
            # 构建简短的实体特征
            type_short = self._get_type_display(entity.entity_type).split("（")[0] if "（" in self._get_type_display(
                entity.entity_type) else self._get_type_display(entity.entity_type)
            if entity.aliases:
                main_alias = entity.aliases[0] if entity.aliases else ""
                if main_alias and main_alias != entity.standard_name:
                    parts.append(f"实体特征：{type_short}「{entity.standard_name}」（又称{main_alias}）")
                else:
                    parts.append(f"实体特征：{type_short}「{entity.standard_name}」")
            else:
                parts.append(f"实体特征：{type_short}「{entity.standard_name}」")

        return "；".join(parts)

    def _build_reranker_pairs(self, mention: str, candidates: List[Candidate], context: str, mention_type: str = "") -> \
    List[List[str]]:
        """
        构建 Reranker 输入对（增强语义版本）
        """
        pairs = []

        # 构建增强的查询文本
        query = self._build_enhanced_query(mention, context, mention_type)

        for cand in candidates:
            # 构建增强的实体描述
            passage = self._build_enhanced_passage(cand.entity)
            pairs.append([query, passage])

        return pairs

    def _build_single_pair(self, mention: str, entity: StandardEntity, context: str, mention_type: str = "") -> List[
        str]:
        """
        构建单个候选的Reranker输入对
        """
        query = self._build_enhanced_query(mention, context, mention_type)
        passage = self._build_enhanced_passage(entity)
        return [query, passage]

    # ============================================================
    # 精排核心方法
    # ============================================================

    def _rerank(self, mention: str, candidates: List[Candidate], context: str = "", mention_type: str = "") -> List[
        Candidate]:
        """
        使用 Reranker 对候选进行精排（增强语义版本）
        """
        if not self.enable_reranker or not candidates or len(candidates) <= 1:
            return candidates

        self.stats["reranker_calls"] += 1
        self.stats["reranker_used"] += 1

        top_k = min(self.reranker_top_k, len(candidates))
        top_candidates = candidates[:top_k]

        # 构建增强语义的查询和回答对
        pairs = self._build_reranker_pairs(mention, top_candidates, context, mention_type)

        try:
            rerank_scores = self.reranker.predict(pairs)

            for i, cand in enumerate(top_candidates):
                combined = self.bge_weight * cand.score + self.reranker_weight * rerank_scores[i]
                cand.score = float(combined)

            top_candidates.sort(key=lambda c: c.score, reverse=True)
            candidates[:top_k] = top_candidates

            logger.debug(f"  🔄 Reranker精排完成: {len(top_candidates)} 个候选 (增强语义)")

        except Exception as e:
            logger.warning(f"⚠️ Reranker精排失败: {e}，使用BGE分数")

        return candidates

    def _process_single_candidate(self, mention: str, candidates: List[Candidate], context: str,
                                  mention_type: str = "") -> Dict[str, Any]:
        """
        处理单个候选的情况（使用增强语义精排）
        """
        if len(candidates) != 1:
            return None

        cand = candidates[0]

        if self.enable_reranker:
            # 构建增强语义的查询和回答对
            pair = self._build_single_pair(mention, cand.entity, context, mention_type)
            try:
                rerank_score = self.reranker.predict([pair])[0]
                final_score = self.bge_weight * cand.score + self.reranker_weight * rerank_score
                cand.score = float(final_score)
                logger.debug(f"  📊 单候选精排: {cand.entity.standard_name} → {cand.score:.3f}")
            except Exception as e:
                logger.warning(f"⚠️ 单候选精排失败: {e}，使用原分数")

        if cand.score >= self.nil_threshold:
            return {
                "entity": cand.entity,
                "score": cand.score,
                "method": "single_reranker" if self.enable_reranker else "single_bge",
                "evidence": f"唯一候选，分数 {cand.score:.3f} >= 阈值 {self.nil_threshold}"
            }
        else:
            self.stats["nil_by_score"] += 1
            return {
                "entity": None,
                "score": cand.score,
                "method": "nil_single",
                "evidence": f"唯一候选，分数 {cand.score:.3f} < 阈值 {self.nil_threshold}"
            }

    # ============================================================
    # NIL 检测
    # ============================================================

    def _check_nil(self, candidates: List[Candidate]) -> bool:
        """基于精排后的分数判断是否为 NIL"""
        if not candidates:
            return True

        top = candidates[0]

        if top.score < self.nil_threshold:
            logger.info(f"  📊 NIL判定: 最高分 {top.score:.3f} < 阈值 {self.nil_threshold}")
            return True

        if len(candidates) >= 2:
            second = candidates[1]
            gap = top.score - second.score
            if gap < 0.01 and top.score < 0.6:
                logger.info(f"  📊 NIL判定: 最高分 {top.score:.3f}, 次高分 {second.score:.3f}, 差距 {gap:.3f} < 0.01")
                return True

        return False

    # ============================================================
    # LLM 兜底（增强语义版本）
    # ============================================================

    def _build_llm_prompt(self, mention: str, candidates: List[Candidate], context: str,
                          mention_type: str = "") -> tuple:
        """构建LLM提示词（增强语义版本）"""
        candidate_descriptions = []
        for i, cand in enumerate(candidates[:10], 1):
            entity = cand.entity
            desc = f"【候选{i}】\n"
            desc += f"  标准名称：{entity.standard_name}\n"

            if entity.aliases:
                desc += f"  别名：{'、'.join(entity.aliases[:5])}\n"

            if entity.entity_type and entity.entity_type != "UNKNOWN":
                desc += f"  类型：{self._get_type_display(entity.entity_type)}\n"

            if entity.description:
                desc += f"  描述：{entity.description[:150]}\n"

            industry = entity.metadata.get("industry", "")
            if industry:
                desc += f"  行业：{industry}\n"

            tags = entity.metadata.get("tags", [])
            if tags:
                desc += f"  标签：{'、'.join(tags[:5])}\n"

            desc += f"  精排分数：{cand.score:.3f}"
            candidate_descriptions.append(desc)

        system_prompt = """你是一个专业的实体链接消歧专家。你的任务是根据给定的上下文和提及（mention），从候选实体中选出最匹配的一个。

【分析要点】
1. 关注提及本身的语义：它是什么类型的实体？
2. 利用上下文中的线索：提及在上下文中扮演什么角色？
3. 比较候选实体的完整信息：名称、类型、描述、行业等
4. 判断匹配度：综合考虑所有信息

【决策规则】
1. 如果没有任何候选实体与提及匹配 → 输出 NIL
2. 如果有多个候选都匹配，选择最匹配的一个
3. NIL判断标准：
   - 所有候选都与提及语义不相关
   - 候选类型与提及类型不匹配
   - 提及是通用词汇，没有特指某个具体实体

【输出格式】
必须输出JSON格式：
{"entity_id": "实体ID或NIL", "reason": "详细的选择理由", "confidence": 0.0-1.0}

注意：
- entity_id必须从候选列表中选取
- 如果选NIL，reason要说明为什么没有匹配
- confidence表示你的确定程度"""

        # 构建用户提示
        type_hint = f"（类型提示：{self._get_type_display(mention_type)}）" if mention_type and mention_type != "UNKNOWN" else ""

        user_prompt = f"""【待消歧的提及】
'{mention}' {type_hint}

【上下文】
{context[:500] if context else "（无上下文）"}

【候选实体列表】
{chr(10).join(candidate_descriptions)}

请分析并选择最匹配的实体，或判定为NIL。"""

        return system_prompt, user_prompt

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM API"""
        try:
            import openai
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

        client = openai.OpenAI(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=self.llm_timeout
        )

        model = self.llm_model
        if model == "qwen":
            model = "qwen-turbo"

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=300
        )

        return response.choices[0].message.content

    def _parse_llm_response(self, content: str) -> Dict:
        """解析 LLM 响应"""
        import re

        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass

        if "NIL" in content.upper():
            return {"entity_id": "NIL", "reason": "LLM判定为NIL", "confidence": 0.7}

        id_match = re.search(r'[a-zA-Z0-9_]+', content)
        if id_match:
            return {"entity_id": id_match.group(), "reason": "从响应中提取", "confidence": 0.6}

        return {"entity_id": "NIL", "reason": "无法解析LLM响应", "confidence": 0.0}

    def _llm_disambiguate(self, mention: str, candidates: List[Candidate], context: str,
                          mention_type: str = "") -> Dict:
        """LLM兜底消歧（增强语义版本）"""
        cache_key = hashlib.md5(
            f"{mention}|{context[:200]}|{mention_type}|{','.join([c.entity.entity_id for c in candidates[:5]])}".encode()
        ).hexdigest()

        if self.cache_enabled and cache_key in self._cache:
            entry = self._cache[cache_key]
            if datetime.now() - entry["timestamp"] < timedelta(seconds=self.cache_ttl):
                self.stats["llm_cache_hits"] += 1
                return entry["result"]

        start_time = time.time()
        self.stats["llm_calls"] += 1

        for attempt in range(self.llm_max_retries + 1):
            try:
                logger.info(f"  🤖 LLM尝试 {attempt + 1}/{self.llm_max_retries + 1}")
                system_prompt, user_prompt = self._build_llm_prompt(mention, candidates, context, mention_type)
                raw_content = self._call_llm(system_prompt, user_prompt)
                result = self._parse_llm_response(raw_content)

                entity_id = result.get("entity_id", "NIL")
                reason = result.get("reason", "")
                confidence = result.get("confidence", 0.5)

                if entity_id == "NIL":
                    self.stats["nil_by_llm"] += 1
                    llm_result = {
                        "entity": None,
                        "score": 0.0,
                        "method": "llm_nil",
                        "evidence": f"LLM判定NIL: {reason}"
                    }
                else:
                    found = next((c for c in candidates if c.entity.entity_id == entity_id), None)
                    if found:
                        llm_result = {
                            "entity": found.entity,
                            "score": confidence,
                            "method": "llm",
                            "evidence": f"LLM选择: {reason}"
                        }
                    else:
                        self.stats["nil_by_llm"] += 1
                        llm_result = {
                            "entity": None,
                            "score": 0.0,
                            "method": "llm_nil",
                            "evidence": f"LLM返回无效ID: {entity_id}"
                        }

                if self.cache_enabled:
                    self._cache[cache_key] = {"result": llm_result, "timestamp": datetime.now()}

                elapsed = time.time() - start_time
                self.stats["avg_llm_time"] = (
                                                     self.stats["avg_llm_time"] * (
                                                         self.stats["llm_calls"] - 1) + elapsed
                                             ) / self.stats["llm_calls"]

                return llm_result

            except Exception as e:
                logger.warning(f"  ⚠️ LLM尝试 {attempt + 1} 失败: {e}")
                if attempt == self.llm_max_retries:
                    return {
                        "entity": None,
                        "score": 0.0,
                        "method": "llm_failed",
                        "evidence": f"LLM调用失败: {e}"
                    }
                time.sleep(1)

        return {"entity": None, "score": 0.0, "method": "llm_fallback", "evidence": "LLM全部失败"}

    # ============================================================
    # 主入口
    # ============================================================

    def disambiguate(self, mention: str, candidates: List[Candidate], context: str = "", mention_type: str = "") -> \
    Dict[str, Any]:
        """
        消歧精排主入口（增强语义版本）

        Args:
            mention: 实体指称
            candidates: 候选列表（已由 CandidateGenerator 生成）
            context: 上下文文本
            mention_type: 实体类型（从NER获取）

        Returns:
            {
                "entity": StandardEntity or None,
                "score": float,
                "method": str,
                "evidence": str
            }
        """
        # ============================================================
        # 边界情况
        # ============================================================
        if not mention or not mention.strip():
            return {"entity": None, "score": 0.0, "method": "nil", "evidence": "空mention → NIL"}

        if not candidates:
            return {"entity": None, "score": 0.0, "method": "nil", "evidence": "无候选 → NIL"}

        # ============================================================
        # 单个候选：用Reranker精排获取准确分数
        # ============================================================
        if len(candidates) == 1:
            return self._process_single_candidate(mention, candidates, context, mention_type)

        # ============================================================
        # 多候选：精排（Reranker）
        # ============================================================
        if self.enable_reranker:
            candidates = self._rerank(mention, candidates, context, mention_type)

        # 排序
        top = candidates[0]

        logger.info(f"  📊 消歧: '{mention}' → {top.entity.standard_name} (分数: {top.score:.3f})")
        if len(candidates) > 1:
            logger.info(f"      次优: {candidates[1].entity.standard_name} (分数: {candidates[1].score:.3f})")

        # ============================================================
        # NIL 检测（基于精排后的分数）
        # ============================================================
        if self._check_nil(candidates):
            self.stats["nil_by_score"] += 1
            nil_reason = f"NIL: 最高分 {top.score:.3f}"
            if len(candidates) > 1:
                nil_reason += f", 次高分 {candidates[1].score:.3f}"

            if self.enable_llm and top.score < self.llm_trigger_threshold:
                logger.info(f"  🤖 NIL检测触发LLM二次确认")
                llm_result = self._llm_disambiguate(mention, candidates, context, mention_type)
                if llm_result.get("entity") is not None:
                    logger.info(f"  ✅ LLM确认有实体: {llm_result['entity'].standard_name}")
                    return llm_result
                else:
                    logger.info(f"  ✅ LLM也判定为NIL")
                    return {
                        "entity": None,
                        "score": 0.0,
                        "method": "nil_llm",
                        "evidence": f"LLM确认NIL: {nil_reason}"
                    }

            return {
                "entity": None,
                "score": top.score,
                "method": "nil",
                "evidence": nil_reason
            }

        # ============================================================
        # LLM兜底（低置信度但未达到NIL阈值）
        # ============================================================
        if self.enable_llm and top.score < self.llm_trigger_threshold:
            logger.info(f"  🤖 低置信度 {top.score:.3f} < {self.llm_trigger_threshold}，触发LLM兜底")
            llm_result = self._llm_disambiguate(mention, candidates, context, mention_type)

            if llm_result.get("entity") is not None:
                logger.info(f"  ✅ LLM选择: {llm_result['entity'].standard_name}")
                return llm_result
            elif llm_result.get("method") == "llm_nil":
                self.stats["nil_by_llm"] += 1
                return {
                    "entity": None,
                    "score": 0.0,
                    "method": "llm_nil",
                    "evidence": llm_result["evidence"]
                }

        # ============================================================
        # 返回结果
        # ============================================================
        method = "reranker" if self.enable_reranker else "bge"
        return {
            "entity": top.entity,
            "score": top.score,
            "method": method,
            "evidence": f"{method.upper()} 精排: {top.score:.3f}"
        }

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "reranker_calls": self.stats["reranker_calls"],
            "llm_calls": self.stats["llm_calls"],
            "llm_cache_hits": self.stats["llm_cache_hits"],
            "llm_errors": self.stats["llm_errors"],
            "avg_llm_time": self.stats["avg_llm_time"],
            "nil_by_score": self.stats["nil_by_score"],
            "nil_by_llm": self.stats["nil_by_llm"],
            "reranker_used": self.stats["reranker_used"],
            "cache_size": len(self._cache)
        }

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("💾 缓存已清空")