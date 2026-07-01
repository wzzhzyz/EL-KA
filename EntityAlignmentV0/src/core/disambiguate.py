# src/core/disambiguate.py
import numpy as np
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from src.models.entity import StandardEntity
from src.models.candidate import Candidate
from src.utils.logger import logger


class Disambiguator:
    """消歧排序：BGE 语义相似度 + LLM 兜底（可选）"""

    def __init__(self, config):
        bge_path = config.get("bge_model_path", "./models_cache/bge-small-zh")
        self.bge_model = SentenceTransformer(bge_path)

        self.nil_threshold = config.get("disambiguator", {}).get("nil_threshold", 0.65)
        self.llm_trigger_threshold = config.get("disambiguator", {}).get("bge_llm_trigger_threshold", 0.65)

        # LLM 兜底配置（默认关闭）
        self.enable_llm = config.get("llm_fallback", {}).get("enabled", False)
        self.llm_api_key = config.get("llm_fallback", {}).get("api_key")

        logger.info("✅ 消歧器初始化完成")

    def _bge_rank(self, mention: str, candidates: List[Candidate], context: str = "") -> List[Candidate]:
        """
        使用 BGE 计算语义相似度并排序（使用 query/passage 前缀）
        """
        if not candidates:
            return []

        # 构建候选文本（passage 前缀）
        candidate_texts = []
        for cand in candidates:
            entity = cand.entity
            text = entity.standard_name
            if entity.description:
                text += "：" + entity.description
            # BGE 指令微调：passage 前缀
            candidate_texts.append(f"passage: {text}")

        # 构建查询文本（query 前缀）
        query_text = f"query: {mention}"
        if context:
            query_text = f"query: {context} {mention}"

        # 编码
        mention_emb = self.bge_model.encode([query_text], normalize_embeddings=True)
        cand_embs = self.bge_model.encode(candidate_texts, normalize_embeddings=True)

        # 计算余弦相似度（内积，因为已归一化）
        scores = np.dot(cand_embs, mention_emb.T).flatten()

        # 更新分数并排序
        for i, cand in enumerate(candidates):
            cand.score = float(scores[i])

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def disambiguate(self, mention: str, candidates: List[Candidate], context: str = "") -> Dict[str, Any]:
        """
        消歧主入口

        Returns:
            {
                "entity": StandardEntity or None,
                "score": float,
                "method": str,
                "evidence": str
            }
        """
        if not candidates:
            return {
                "entity": None,
                "score": 0.0,
                "method": "none",
                "evidence": "无候选实体"
            }

        # 如果只有一个候选，直接返回
        if len(candidates) == 1:
            return {
                "entity": candidates[0].entity,
                "score": candidates[0].score,
                "method": candidates[0].method,
                "evidence": f"唯一候选 (来源: {candidates[0].method})"
            }

        # BGE 排序（所有候选参与，包括别名匹配的）
        ranked = self._bge_rank(mention, candidates, context)
        if not ranked:
            return {
                "entity": None,
                "score": 0.0,
                "method": "none",
                "evidence": "BGE 计算失败"
            }

        top = ranked[0]

        # 记录消歧详情
        logger.info(f"  📊 消歧结果: {mention} → {top.entity.standard_name} (分数: {top.score:.3f}, 来源: {top.method})")
        if len(ranked) > 1:
            logger.info(f"      次优: {ranked[1].entity.standard_name} (分数: {ranked[1].score:.3f})")

        # 检查是否需要 LLM 兜底（后续实现）
        # if self.enable_llm and top.score < self.llm_trigger_threshold:
        #     llm_result = self._llm_disambiguate(mention, candidates, context)
        #     ...

        return {
            "entity": top.entity,
            "score": top.score,
            "method": top.method,
            "evidence": f"BGE 语义相似度: {top.score:.3f} (来源: {top.method})"
        }