# src/core/disambiguate.py
import numpy as np
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from src.models.entity import StandardEntity
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

    def _bge_rank(self, mention: str, candidates: List[Dict], context: str = "") -> List[Dict]:
        """使用 BGE 计算语义相似度并排序"""
        if not candidates:
            return []

        # 构建 mention 的表示（加入上下文）
        mention_text = f"{context} {mention}" if context else mention

        # 构建候选文本
        candidate_texts = []
        for cand in candidates:
            entity = cand["entity"]  # StandardEntity
            text = entity.standard_name
            if entity.description:
                text += "：" + entity.description
            candidate_texts.append(text)

        # 编码
        mention_emb = self.bge_model.encode([mention_text], normalize_embeddings=True)
        cand_embs = self.bge_model.encode(candidate_texts, normalize_embeddings=True)

        # 计算余弦相似度（内积，因为已归一化）
        scores = np.dot(cand_embs, mention_emb.T).flatten()

        # 排序
        results = []
        for i, cand in enumerate(candidates):
            results.append({
                "entity": cand["entity"],
                "score": float(scores[i]),
                "method": cand.get("method", "vector")
            })
        results.sort(key=lambda x: x["score"], reverse=True)

        return results

    def disambiguate(self, mention: str, candidates: List[Dict], context: str = "") -> Dict:
        """
        消歧主入口

        Returns:
            {"entity": StandardEntity or None, "score": 0.85, "method": "bge", "evidence": "..."}
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
                "entity": candidates[0]["entity"],
                "score": candidates[0].get("score", 1.0),
                "method": candidates[0].get("method", "direct"),
                "evidence": "唯一候选"
            }

        # BGE 排序
        bge_results = self._bge_rank(mention, candidates, context)
        if not bge_results:
            return {
                "entity": None,
                "score": 0.0,
                "method": "none",
                "evidence": "BGE 计算失败"
            }

        top = bge_results[0]

        return {
            "entity": top["entity"],
            "score": top["score"],
            "method": top.get("method", "bge"),
            "evidence": f"BGE 语义相似度: {top['score']:.3f}"
        }