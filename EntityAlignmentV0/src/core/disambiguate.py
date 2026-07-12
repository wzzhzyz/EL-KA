# src/core/disambiguate.py
"""
消歧精排模块 - 增强语义信息

优化点：
1. 使用 StandardMention 作为输入，利用 char_start/char_end 精确标记
2. 查询文本：包含mention类型、上下文关键信息、实体类型提示
3. 回答文本：包含实体名称、别名、类型、描述、行业、标签等完整语义
"""

import numpy as np
import json
import hashlib
import time
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from src.models.entity import StandardEntity
from src.models.candidate import Candidate
from src.models.mention import StandardMention
from src.utils.logger import logger
from src.utils.lazy_loader import lazy_load, clear_model_cache
from src.core.llm_client import LLMDisambiguator

class Disambiguator:
    """
    消歧精排器 - 增强语义信息版本
    支持 StandardMention 作为输入，利用字符位置精确标记
    """

    """
    消歧精排器 - 增强语义信息版本 + 懒加载
    """

    def __init__(self, config):
        # ============================================================
        # 1. Reranker 配置（懒加载）
        # ============================================================
        self.enable_reranker = config.get("reranker_enabled", False)
        self.reranker_top_k = config.get("reranker_top_k", 10)
        self.reranker_weight = config.get("reranker_weight", 0.7)
        self.bge_weight = config.get("bge_weight", 0.3)
        self.reranker_mode = config.get("reranker_mode", "original")
        self.reranker_model_path = config.get("reranker_model_path", "./models_cache/bge-reranker-base")

        # 懒加载：不立即加载模型
        self._reranker = None
        self._reranker_tokenizer = None
        self._reranker_model = None
        self._reranker_loaded = False

        # ============================================================
        # 2. 配置参数
        # ============================================================
        self.nil_threshold = config.get("disambiguator", {}).get("nil_threshold", 0.65)
        self.llm_trigger_threshold = config.get("disambiguator", {}).get("bge_llm_trigger_threshold", 0.55)

        # ============================================================
        # 3. 🔥 LLM 抽象层客户端（替换原来的 LLM 兜底逻辑）
        # ============================================================
        self.llm_config = {
            "enabled": config.get("llm_fallback", {}).get("enabled", False),
            "provider": config.get("llm_fallback", {}).get("provider", "openai"),
            "api_key": config.get("llm_fallback", {}).get("api_key"),
            "model": config.get("llm_fallback", {}).get("model", "gpt-4o-mini"),
            "base_url": config.get("llm_fallback", {}).get("base_url"),
            "timeout": config.get("llm_fallback", {}).get("timeout", 30),
            "max_retries": config.get("llm_fallback", {}).get("max_retries", 2),
            "cache_enabled": config.get("llm_fallback", {}).get("cache_enabled", True),
            "cache_ttl": config.get("llm_fallback", {}).get("cache_ttl", 86400),
            "trigger_threshold": self.llm_trigger_threshold,
        }

        self.llm_client = LLMDisambiguator(self.llm_config)

        # ============================================================
        # 4. 缓存（用于 LLM 消歧结果）
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

        # ============================================================
        # 6. 日志
        # ============================================================
        logger.info("✅ 消歧精排器初始化完成（懒加载模式）")
        logger.info(f"   📊 NIL阈值: {self.nil_threshold}")
        logger.info(f"   📊 Reranker: {'启用' if self.enable_reranker else '禁用'}")

        if self.llm_client.is_enabled():
            provider_name = "unknown"
            if hasattr(self.llm_client, '_provider') and self.llm_client._provider:
                provider_name = self.llm_client._provider.get_model_name()
            logger.info(f"   🤖 LLM兜底: {provider_name}")
            logger.info(f"   ⚡ 触发阈值: {self.llm_trigger_threshold}")
        else:
            logger.info("   ℹ️ LLM兜底: 未启用")

    def _ensure_reranker(self):
        """懒加载 Reranker 模型"""
        if self._reranker_loaded:
            return

        if not self.enable_reranker:
            return

        reranker_path = self.reranker_model_path

        def load_reranker():
            import torch

            if self.reranker_mode == "original":
                from sentence_transformers import CrossEncoder

                if torch.cuda.is_available():
                    reranker = CrossEncoder(reranker_path, device='cuda')
                    logger.info("✅ BGE Reranker (原版) 已加载 (GPU)")
                else:
                    reranker = CrossEncoder(reranker_path, device='cpu')
                    logger.info("✅ BGE Reranker (原版) 已加载 (CPU)")

                if hasattr(reranker, 'model') and torch.cuda.is_available():
                    if hasattr(reranker.model, 'half'):
                        reranker.model.half()
                        logger.info("   Reranker 已转为 FP16")
                return reranker

            elif self.reranker_mode == "finetuned":
                from transformers import AutoTokenizer, AutoModelForSequenceClassification

                tokenizer = AutoTokenizer.from_pretrained(reranker_path)
                model = AutoModelForSequenceClassification.from_pretrained(reranker_path)

                special_tokens = ["[*]", "[/*]"]
                existing_tokens = tokenizer.get_vocab()
                new_tokens = [t for t in special_tokens if t not in existing_tokens]
                if new_tokens:
                    tokenizer.add_tokens(new_tokens)
                    model.resize_token_embeddings(len(tokenizer))
                    logger.info(f"   Reranker tokenizer 已添加新 token: {new_tokens}")

                model.eval()

                if torch.cuda.is_available():
                    model = model.half().cuda()
                    logger.info("✅ BGE Reranker (微调) 已加载 (GPU + FP16)")
                else:
                    logger.info("✅ BGE Reranker (微调) 已加载 (CPU)")

                return tokenizer, model

            else:
                raise ValueError(f"不支持的 reranker_mode: {self.reranker_mode}")

        try:
            if self.reranker_mode == "original":
                self._reranker = lazy_load("reranker", load_reranker)
            else:
                self._reranker_tokenizer, self._reranker_model = lazy_load("reranker_finetuned", load_reranker)
            self._reranker_loaded = True
            logger.info(f"   Reranker Top-K: {self.reranker_top_k}")
            logger.info(f"   Reranker权重: {self.reranker_weight}, BGE权重: {self.bge_weight}")
        except Exception as e:
            logger.warning(f"⚠️ Reranker 加载失败: {e}，禁用Reranker")
            self.enable_reranker = False
            self._reranker_loaded = True

    # ============================================================
    # 🔥 核心方法：利用字符位置标记 mention
    # ============================================================

    # src/core/disambiguate.py

    def _mark_mention_in_context(self, context: str, mention: Union[str, StandardMention]) -> str:
        """
        利用 StandardMention 的字符位置信息，在上下文中精确添加 [*] 和 [/*] 标记

        Args:
            context: 原始上下文
            mention: StandardMention 对象或字符串

        Returns:
            标记后的上下文，如 "[*]苹果[/*]公司今天发布了新iPhone"
        """
        # 如果是字符串，降级使用 replace
        if isinstance(mention, str):
            logger.debug(f"  ⚠️ mention 是字符串，使用 replace 降级标记: '{mention}'")
            return context.replace(mention, f"[*]{mention}[/*]", 1)

        mention_text = mention.mention
        char_start = mention.char_start
        char_end = mention.char_end

        # 检查位置是否有效
        if char_start == 0 and char_end == 0:
            logger.debug(f"  ⚠️ StandardMention 位置未设置 (0,0)，使用 replace 降级标记: '{mention_text}'")
            return context.replace(mention_text, f"[*]{mention_text}[/*]", 1)

        if char_start < 0 or char_end > len(context) or char_start > char_end:
            logger.warning(f"  ⚠️ 位置越界: start={char_start}, end={char_end}, len={len(context)}，使用 replace 降级")
            return context.replace(mention_text, f"[*]{mention_text}[/*]", 1)

        actual_text = context[char_start:char_end]
        if actual_text != mention_text:
            logger.warning(f"  ⚠️ 位置文本不匹配: '{actual_text}' != '{mention_text}'，使用 replace 降级")
            return context.replace(mention_text, f"[*]{mention_text}[/*]", 1)

        # ✅ 精确插入标记
        marked = context[:char_start] + f"[*]{mention_text}[/*]" + context[char_end:]
        logger.debug(f"  📍 精确标记: '{mention_text}' at [{char_start}:{char_end}]")

        return marked

    def _build_query(self, mention: Union[str, StandardMention], context: str = "") -> str:
        """
        构建查询文本：仅返回带 [*] 和 [/*] 标记的上下文

        Args:
            mention: StandardMention 对象或字符串
            context: 上下文文本（如果 mention 是 StandardMention，可从其 metadata 获取）

        Returns:
            带标记的上下文，如 "[*]苹果[/*]公司今天发布了新iPhone"
        """
        # 提取上下文
        if isinstance(mention, StandardMention):
            if not context and mention.metadata.get("context"):
                context = mention.metadata.get("context", "")
        # 如果 context 为空，尝试从 mention 对象获取
        if not context and isinstance(mention, StandardMention):
            context = mention.metadata.get("context", "")

        # 如果 context 为空，返回空字符串
        if not context or not context.strip():
            return context

        # 标记 mention
        marked_context = self._mark_mention_in_context(context, mention)

        return marked_context

    def _build_passage(self, entity: StandardEntity) -> str:
        """
        构建候选实体描述文本：直接拼接 metadata，不进行字段判断

        Args:
            entity: StandardEntity 对象

        Returns:
            拼接后的描述文本
        """
        parts = []

        # 1. 基础信息
        parts.append(f"实体ID：{entity.entity_id}")
        parts.append(f"标准名称：{entity.standard_name}")
        if entity.aliases:
            parts.append(f"别名：{entity.aliases}")
        if entity.description:
            parts.append(f"描述：{entity.description}")
        # 2. 直接拼接 metadata 中的所有字段
        for key, value in entity.metadata.items():
            if value is None:
                continue
            if isinstance(value, list):
                value_str = "、".join(str(v) for v in value)
            else:
                value_str = str(value)
            parts.append(f"{key}：{value_str}")

        return "；".join(parts)

    # ============================================================
    # 统一的预测方法
    # ============================================================

    def _predict_reranker(self, pairs: List[List[str]]) -> List[float]:
        """统一的 Reranker 预测方法（懒加载）"""
        if not self.enable_reranker:
            return [0.0] * len(pairs)

        # 确保模型已加载
        self._ensure_reranker()

        import torch

        if self.reranker_mode == "original" and self._reranker is not None:
            scores = self._reranker.predict(pairs)
            if hasattr(scores, 'tolist'):
                return scores.tolist()
            return list(scores)

        elif self.reranker_mode == "finetuned" and self._reranker_model is not None:
            scores = []
            for query, doc in pairs:
                inputs = self._reranker_tokenizer(
                    query,
                    doc,
                    truncation=True,
                    padding='max_length',
                    max_length=512,
                    return_tensors='pt'
                )

                if torch.cuda.is_available():
                    inputs = {k: v.cuda() for k, v in inputs.items()}

                with torch.no_grad():
                    logits = self._reranker_model(**inputs).logits
                    if logits.dim() == 2 and logits.size(1) == 1:
                        score = logits.item()
                    else:
                        score = logits.flatten().item()
                    scores.append(score)
            return scores

        else:
            logger.warning("⚠️ Reranker 未就绪，返回 0 分")
            return [0.0] * len(pairs)

    # ============================================================
    # 增强的语义构建方法
    # ============================================================

    TYPE_DISPLAY = {
        "ORG": "组织机构",
        "GPE": "地理政治实体（国家/城市/地区）",
        "PERSON": "人物",
        "LOC": "地理位置（山川/河流/景点）",
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
        return self.TYPE_DISPLAY.get(entity_type, entity_type)

    def _extract_context_keywords(self, context: str, mention_text: str) -> str:
        """从上下文中提取关键语义信息"""
        if not context or not context.strip():
            return ""

        mention_pos = context.find(mention_text)
        if mention_pos == -1:
            return ""

        start = max(0, mention_pos - 50)
        end = min(len(context), mention_pos + len(mention_text) + 50)

        keywords = []
        import re

        key_terms = []
        for term in ["成立", "发布", "宣布", "推出", "设立", "组建", "运营", "管理", "服务", "生产", "销售"]:
            if term in context:
                key_terms.append(term)

        if key_terms:
            keywords.append(f"动作/状态：{'、'.join(key_terms[:3])}")

        date_pattern = r'(\d{4}年|\d{1,2}月|\d{1,2}日|近期|最近|此前)'
        dates = re.findall(date_pattern, context)
        if dates:
            keywords.append(f"时间：{dates[0]}")

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

        if keywords:
            return f"上下文关键信息：{'；'.join(keywords)}"

        return ""

    def _build_enhanced_query(self, mention: Union[str, StandardMention], context: str = "",
                              mention_type: str = "") -> str:
        """
        构建增强的查询文本

        🔥 核心：使用 _mark_mention_in_context 在上下文中精确添加 [*] 和 [/*] 标记

        Args:
            mention: StandardMention 对象或字符串
            context: 上下文文本
            mention_type: 实体类型（备用）

        Returns:
            带标记的 query 字符串
        """
        # 提取信息
        if isinstance(mention, StandardMention):
            mention_text = mention.mention
            mention_type = mention.mention_type if mention.mention_type != "UNKNOWN" else mention_type
            if not context and mention.metadata.get("context"):
                context = mention.metadata.get("context", "")
        else:
            mention_text = mention

        # ============================================================
        # 🔥 核心：利用字符位置精确添加 [*] 和 [/*] 标记
        # ============================================================
        marked_context = self._mark_mention_in_context(context, mention)

        parts = []

        # 1. 基础信息：提及和类型
        if mention_type and mention_type != "UNKNOWN":
            type_desc = self._get_type_display(mention_type)
            parts.append(f"需要消歧的实体指称：“{mention_text}”（类型提示：{type_desc}）")
        else:
            parts.append(f"需要消歧的实体指称：“{mention_text}”")

        # 2. 🔥 带标记的上下文
        if marked_context and marked_context.strip():
            # 截取避免过长
            context_text = marked_context[:500]
            parts.append(f"所属上下文：{context_text}")

        # 3. 提取的关键语义信息（使用原始上下文，避免标记干扰）
        key_info = self._extract_context_keywords(context, mention_text)
        if key_info:
            parts.append(key_info)

        # 4. 明确任务指示
        parts.append(f"请判断该实体指称“{mention_text}”对应哪个标准实体")

        return "；".join(parts)

    def _build_enhanced_passage(self, entity: StandardEntity) -> str:
        """构建增强的候选实体描述文本"""
        parts = []

        parts.append(f"实体ID：{entity.entity_id}")
        parts.append(f"标准名称：{entity.standard_name}")

        if entity.aliases:
            aliases_str = "、".join(entity.aliases)
            parts.append(f"别名/简称：{aliases_str}")

        if entity.entity_type and entity.entity_type != "UNKNOWN":
            type_desc = self._get_type_display(entity.entity_type)
            parts.append(f"实体类型：{type_desc}")

        if entity.description:
            desc = entity.description[:200]
            parts.append(f"实体描述：{desc}")

        industry = entity.metadata.get("industry", "")
        if industry:
            parts.append(f"所属行业/领域：{industry}")

        tags = entity.metadata.get("tags", [])
        if tags:
            tags_str = "、".join(tags[:5])
            parts.append(f"标签/关键词：{tags_str}")

        abbreviation = entity.metadata.get("abbreviation", "")
        if abbreviation:
            parts.append(f"缩写：{abbreviation}")

        source = entity.metadata.get("source", "")
        if source:
            parts.append(f"数据来源：{source}")

        if entity.description and entity.entity_type:
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

    def _build_reranker_pairs(self, mention: Union[str, StandardMention], candidates: List[Candidate],
                              context: str = "", mention_type: str = "") -> List[List[str]]:
        """构建 Reranker 输入对"""
        pairs = []
        query = self._build_query(mention, context)

        for cand in candidates:
            passage = self._build_passage(cand.entity)
            pairs.append([query, passage])

        return pairs

    def _build_single_pair(self, mention: Union[str, StandardMention], entity: StandardEntity,
                           context: str = "", mention_type: str = "") -> List[str]:
        """构建单个候选的Reranker输入对"""
        query = self._build_query(mention, context)
        passage = self._build_passage(entity)
        return [query, passage]

    # ============================================================
    # 精排核心方法
    # ============================================================

    def _rerank(self, mention: Union[str, StandardMention], candidates: List[Candidate],
                context: str = "", mention_type: str = "") -> List[Candidate]:
        """使用 Reranker 对候选进行精排"""
        if not self.enable_reranker or not candidates or len(candidates) <= 1:
            return candidates

        self.stats["reranker_calls"] += 1
        self.stats["reranker_used"] += 1

        top_k = min(self.reranker_top_k, len(candidates))
        top_candidates = candidates[:top_k]

        pairs = self._build_reranker_pairs(mention, top_candidates, context, mention_type)

        try:
            rerank_scores = self._predict_reranker(pairs)

            for i, cand in enumerate(top_candidates):
                combined = self.bge_weight * cand.score + self.reranker_weight * rerank_scores[i]
                cand.score = float(combined)

            top_candidates.sort(key=lambda c: c.score, reverse=True)
            candidates[:top_k] = top_candidates

            logger.debug(f"  🔄 Reranker精排完成: {len(top_candidates)} 个候选")

        except Exception as e:
            logger.warning(f"⚠️ Reranker精排失败: {e}，使用BGE分数")

        return candidates

    def _process_single_candidate(self, mention: Union[str, StandardMention], candidates: List[Candidate],
                                  context: str = "", mention_type: str = "") -> Dict[str, Any]:
        """处理单个候选的情况"""
        if len(candidates) != 1:
            return None

        cand = candidates[0]

        if self.enable_reranker:
            pair = self._build_single_pair(mention, cand.entity, context, mention_type)
            try:
                rerank_score = self._predict_reranker([pair])[0]
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
            if gap < 0.05 and top.score < 0.65:
                logger.info(f"  📊 NIL判定: 最高分 {top.score:.3f}, 次高分 {second.score:.3f}, 差距 {gap:.3f} < 0.01")
                return True

        return False

    # ============================================================
    # LLM 兜底
    # ============================================================

    def _build_llm_prompt(self, mention: Union[str, StandardMention], candidates: List[Candidate],
                          context: str = "", mention_type: str = "") -> tuple:
        """构建LLM提示词"""
        if isinstance(mention, StandardMention):
            mention_text = mention.mention
            mention_type = mention.mention_type if mention.mention_type != "UNKNOWN" else mention_type
            if not context and mention.metadata.get("context"):
                context = mention.metadata.get("context", "")
        else:
            mention_text = mention

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

        type_hint = f"（类型提示：{self._get_type_display(mention_type)}）" if mention_type and mention_type != "UNKNOWN" else ""

        user_prompt = f"""【待消歧的提及】
'{mention_text}' {type_hint}

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

    # ============================================================
    # 🔥 修改 _llm_disambiguate 方法，使用 LLM 抽象层
    # ============================================================

    def _llm_disambiguate(self, mention: Union[str, StandardMention], candidates: List[Candidate],
                          context: str = "", mention_type: str = "") -> Dict:
        """使用 LLM 抽象层进行消歧"""
        # 提取信息
        if isinstance(mention, StandardMention):
            mention_text = mention.mention
            mention_type = mention.mention_type if mention.mention_type != "UNKNOWN" else mention_type
            if not context and mention.metadata.get("context"):
                context = mention.metadata.get("context", "")
        else:
            mention_text = mention

        # 检查 LLM 是否启用
        if not self.llm_client.is_enabled():
            return {
                "entity": None,
                "score": 0.0,
                "method": "llm_disabled",
                "evidence": "LLM 未启用"
            }

        # 构建查询
        query = f"需要消歧的实体指称：\"{mention_text}\""

        # 构建候选列表
        candidate_list = []
        for cand in candidates[:10]:
            entity = cand.entity
            candidate_list.append({
                "entity_id": entity.entity_id,
                "standard_name": entity.standard_name,
                "description": entity.description,
                "entity_type": entity.entity_type,
                "score": cand.score
            })

        # 调用 LLM 抽象层
        try:
            result = self.llm_client.disambiguate(
                query=query,
                candidates=candidate_list,
                context=context[:500],
                mention_type=mention_type
            )

            entity_id = result.get("entity_id", "NIL")
            reason = result.get("reason", "")
            confidence = result.get("confidence", 0.5)

            if entity_id == "NIL":
                self.stats["nil_by_llm"] += 1
                return {
                    "entity": None,
                    "score": 0.0,
                    "method": "llm_nil",
                    "evidence": f"LLM判定NIL: {reason}"
                }
            else:
                found = next((c for c in candidates if c.entity.entity_id == entity_id), None)
                if found:
                    return {
                        "entity": found.entity,
                        "score": confidence,
                        "method": "llm",
                        "evidence": f"LLM选择: {reason}"
                    }
                else:
                    self.stats["nil_by_llm"] += 1
                    return {
                        "entity": None,
                        "score": 0.0,
                        "method": "llm_nil",
                        "evidence": f"LLM返回无效ID: {entity_id}"
                    }

        except Exception as e:
            logger.warning(f"  ⚠️ LLM 消歧失败: {e}")
            return {
                "entity": None,
                "score": 0.0,
                "method": "llm_failed",
                "evidence": f"LLM调用失败: {e}"
            }

    # ============================================================
    # 新增：LLM 开关控制方法
    # ============================================================

    def enable_llm(self):
        """启用 LLM"""
        self.llm_client.set_enabled(True)

    def disable_llm(self):
        """禁用 LLM"""
        self.llm_client.set_enabled(False)

    def is_llm_enabled(self) -> bool:
        """检查 LLM 是否启用"""
        return self.llm_client.is_enabled()

    def get_llm_stats(self) -> Dict:
        """获取 LLM 统计信息"""
        return self.llm_client.get_stats()

    def clear_llm_cache(self):
        """清空 LLM 缓存"""
        self.llm_client.clear_cache()

    # ============================================================
    # 修改主入口，使用 llm_client
    # ============================================================

    def disambiguate(self,
                     mention: Union[str, StandardMention],
                     candidates: List[Candidate],
                     context: str = "",
                     mention_type: str = "") -> Dict[str, Any]:
        """
        消歧精排主入口

        Args:
            mention: StandardMention 对象或字符串
            candidates: 候选列表
            context: 上下文（如果 mention 是 StandardMention，可省略）
            mention_type: 实体类型（如果 mention 是 StandardMention，可省略）

        Returns:
            {
                "entity": StandardEntity or None,
                "score": float,
                "method": str,
                "evidence": str
            }
        """
        # 提取信息
        if isinstance(mention, StandardMention):
            mention_text = mention.mention
            mention_type = mention.mention_type if mention.mention_type != "UNKNOWN" else mention_type
            if not context and mention.metadata.get("context"):
                context = mention.metadata.get("context", "")
        else:
            mention_text = mention

        # 边界检查
        if not mention_text or not mention_text.strip():
            return {"entity": None, "score": 0.0, "method": "nil", "evidence": "空mention → NIL"}

        if not candidates:
            return {"entity": None, "score": 0.0, "method": "nil", "evidence": "无候选 → NIL"}

        # 单候选
        if len(candidates) == 1:
            return self._process_single_candidate(mention, candidates, context, mention_type)

        # 多候选：精排
        if self.enable_reranker:
            candidates = self._rerank(mention, candidates, context, mention_type)

        top = candidates[0]

        logger.info(f"  📊 消歧: '{mention_text}' → {top.entity.standard_name} (分数: {top.score:.3f})")
        if len(candidates) > 1:
            logger.info(f"      次优: {candidates[1].entity.standard_name} (分数: {candidates[1].score:.3f})")

        # NIL 检测
        if self._check_nil(candidates):
            self.stats["nil_by_score"] += 1
            nil_reason = f"NIL: 最高分 {top.score:.3f}"
            if len(candidates) > 1:
                nil_reason += f", 次高分 {candidates[1].score:.3f}"

            if self.is_llm_enabled() and top.score < self.llm_trigger_threshold:
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

        # LLM兜底（使用新的 LLM 抽象层）
        if self.is_llm_enabled() and top.score < self.llm_trigger_threshold:
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
            elif llm_result.get("method") == "llm_failed":
                logger.info(f"  ⚠️ LLM 失败，回退到 BGE 结果")
                # 继续使用 BGE 结果

        method = "reranker" if self.enable_reranker else "bge"
        return {
            "entity": top.entity,
            "score": top.score,
            "method": method,
            "evidence": f"{method.upper()} 精排: {top.score:.3f}"
        }

    def get_stats(self) -> Dict:
        """获取统计信息"""
        cache_size=len(self._cache)
        return {
            "reranker_calls": self.stats["reranker_calls"],
            "llm_calls": self.stats["llm_calls"],
            "llm_cache_hits": self.stats["llm_cache_hits"],
            "llm_errors": self.stats["llm_errors"],
            "avg_llm_time": self.stats["avg_llm_time"],
            "nil_by_score": self.stats["nil_by_score"],
            "nil_by_llm": self.stats["nil_by_llm"],
            "reranker_used": self.stats["reranker_used"],
            "cache_size": cache_size
        }

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("💾 缓存已清空")