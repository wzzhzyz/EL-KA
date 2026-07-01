# src/core/candidate.py
from typing import List, Dict, Any
from src.models.entity import StandardEntity
from src.models.candidate import Candidate
from src.knowledge.kb_manager import KnowledgeBase
from src.knowledge.vector_index import VectorIndex
from src.utils.logger import logger


class CandidateGenerator:
    """
    候选实体生成器：精确别名匹配 + 向量检索

    注意：别名匹配只是候选生成的一种方式，不应直接作为最终结果。
    所有候选（包括别名匹配结果）都会进入消歧模块进行排序。
    """

    def __init__(self, kb: KnowledgeBase, vector_index: VectorIndex):
        self.kb = kb
        self.vector_index = vector_index

    def generate(self, mention: str, top_k: int = 10) -> List[Candidate]:
        """
        生成候选实体列表

        Args:
            mention: 实体指称文本
            top_k: 向量检索返回的候选数量

        Returns:
            List[Candidate]: 候选实体列表（包含别名匹配和向量检索结果）
        """
        candidates = []
        seen_entity_ids = set()

        # ============================================================
        # 1. 别名精确匹配（所有匹配的实体，支持歧义）
        # ============================================================
        alias_entities = self.kb.get_entities_by_alias(mention)
        if alias_entities:
            logger.info(f"  📌 别名精确匹配: {mention} → {len(alias_entities)} 个实体")
            for entity in alias_entities:
                candidates.append(
                    Candidate(
                        entity=entity,
                        score=0.95,
                        method="alias_exact",
                        metadata={
                            "match_type": "alias_exact",
                            "alias": mention,
                            "priority": "high"
                        }
                    )
                )
                seen_entity_ids.add(entity.entity_id)

        # ============================================================
        # 2. 别名模糊匹配（包含关系）
        # ============================================================
        fuzzy_entities = self.kb.get_entities_by_alias_fuzzy(mention, max_results=5)
        if fuzzy_entities:
            added = 0
            for entity in fuzzy_entities:
                if entity.entity_id not in seen_entity_ids:
                    candidates.append(
                        Candidate(
                            entity=entity,
                            score=0.85,
                            method="alias_fuzzy",
                            metadata={
                                "match_type": "alias_fuzzy",
                                "alias": mention,
                                "priority": "medium"
                            }
                        )
                    )
                    seen_entity_ids.add(entity.entity_id)
                    added += 1
            if added > 0:
                logger.info(f"  📌 别名模糊匹配: {mention} → {added} 个实体")

        # ============================================================
        # 3. 向量检索（语义匹配）
        # ============================================================
        # 如果候选已经很多，减少向量检索数量
        remaining = max(1, top_k - len(candidates))
        vector_results = self.vector_index.search(mention, top_k=remaining)

        vector_added = 0
        for r in vector_results:
            entity = r.get("entity")
            score = r.get("score", 0.0)
            if entity and entity.entity_id not in seen_entity_ids:
                candidates.append(
                    Candidate(
                        entity=entity,
                        score=score,
                        method="vector",
                        metadata={
                            "match_type": "vector",
                            "rank": len(candidates) + 1
                        }
                    )
                )
                seen_entity_ids.add(entity.entity_id)
                vector_added += 1

        if vector_added > 0:
            logger.info(f"  🔍 向量检索: {mention} → {vector_added} 个候选")

        # ============================================================
        # 4. 记录日志
        # ============================================================
        if candidates:
            logger.info(f"  📊 候选总数: {mention} → {len(candidates)} 个")
            # 打印前3个候选
            for c in candidates[:3]:
                logger.info(f"      - {c.entity.standard_name} ({c.method}, 分数: {c.score:.3f})")
        else:
            logger.info(f"  ❌ 未找到候选: {mention}")

        return candidates

    def generate_with_priority(self, mention: str, top_k: int = 5) -> List[Candidate]:
        """
        生成候选实体列表（按优先级排序）

        排序规则: alias_exact > alias_fuzzy > vector
        """
        candidates = self.generate(mention, top_k)

        # 按 method 优先级排序
        method_priority = {
            "alias_exact": 0,
            "alias_fuzzy": 1,
            "vector": 2
        }
        candidates.sort(key=lambda c: (method_priority.get(c.method, 3), -c.score))

        return candidates