# src/core/candidate.py
from typing import List, Dict
from src.utils.logger import logger


class CandidateGenerator:
    """候选实体生成器：精确匹配 + 向量检索"""

    def __init__(self, kb, vector_index):
        self.kb = kb
        self.vector_index = vector_index

    def generate(self, mention: str, top_k: int = 5) -> List[Dict]:
        """
        生成候选实体列表
        返回: [{"entity": {...}, "score": 0.95, "method": "exact"}, ...]
        """
        # 1. 精确匹配（最高优先级）
        exact_entity = self.kb.get_entity_by_alias(mention)
        if exact_entity:
            logger.info(f"  ✅ 精确匹配: {mention} → {exact_entity['standard_name']}")
            return [{
                "entity": exact_entity,
                "score": 1.0,
                "method": "exact"
            }]

        # 2. 向量检索（精确匹配未命中）
        results = self.vector_index.search(mention, top_k=top_k)
        for r in results:
            r["method"] = "vector"

        if results:
            logger.info(f"  🔍 向量检索: {mention} → {len(results)} 个候选, 最高分: {results[0]['score']:.3f}")
        else:
            logger.info(f"  ❌ 未找到候选: {mention}")

        return results