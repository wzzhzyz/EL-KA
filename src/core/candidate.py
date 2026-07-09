# src/core/candidate.py - 优化版本
from typing import List, Dict, Any, Optional
import numpy as np
from src.models.entity import StandardEntity
from src.models.candidate import Candidate
from src.knowledge.kb_manager import KnowledgeBase
from src.knowledge.vector_index import VectorIndex
from src.utils.logger import logger
from src.utils.lazy_loader import lazy_load


class CandidateGenerator:
    """
    候选实体生成器：精确别名匹配 + 向量检索
    使用懒加载机制，按需初始化
    """

    def __init__(self, kb: KnowledgeBase, vector_index: VectorIndex):
        self.kb = kb
        self.vector_index = vector_index

        # 别名匹配的权重（略大于1，使别名匹配优先于纯向量检索）
        self.alias_weight = 1.05

        # 懒加载标志：不主动构建向量
        self._embeddings_built = False

        logger.info("✅ 候选生成器初始化完成（懒加载模式）")

    def _ensure_embeddings(self):
        """确保向量已构建（懒加载）"""
        if self._embeddings_built:
            return

        if not self.kb.has_embeddings():
            logger.info("📦 懒加载：构建知识库向量...")
            # 获取向量索引的模型（懒加载）
            model = self.vector_index._get_model()
            self.kb.build_embeddings(model)

        self._embeddings_built = True
        logger.info("✅ 向量构建完成")

    def _build_query_text(self, mention: str, context: str = "") -> str:
        """
        构建结构化的 query 文本
        """
        if context and context.strip():
            return f"query: 上下文中的实体“{mention}”指的是什么？上下文：{context[:500]}。上下文中的实体“{mention}”是什么？"
        else:
            return f"query: 实体指称 “{mention}” 指的是什么？"

    def _build_passage_text(self, entity: StandardEntity) -> str:
        """
        构建结构化的 passage 文本
        """
        text = f"标准实体名：{entity.standard_name}"

        if entity.aliases:
            aliases_str = "、".join(entity.aliases[:5])
            text += f"，别名：{aliases_str}"

        if entity.entity_type and entity.entity_type != "UNKNOWN":
            text += f"，类型：{entity.entity_type}"

        if entity.description:
            text += f"，描述：{entity.description}"

        industry = entity.metadata.get("industry", "")
        if industry:
            text += f"，所属行业：{industry}"

        tags = entity.metadata.get("tags", [])
        if tags:
            tags_str = "、".join(tags[:5])
            text += f"，标签：{tags_str}"

        return f"passage: {text}"

    def _compute_batch_bge_scores(self, mention: str, entities: List[StandardEntity],
                                  context: str = "") -> List[float]:
        """
        批量计算一个 mention 与多个实体的 BGE 分数
        """
        if not entities:
            return []

        # 确保向量已构建（懒加载）
        self._ensure_embeddings()

        # 从KB获取缓存的向量
        entity_ids = [e.entity_id for e in entities]
        entity_embs = self.kb.get_embeddings(entity_ids)

        if len(entity_embs) < len(entities):
            logger.warning("⚠️ 部分实体向量不在缓存中，回退到逐个计算")
            model = self.vector_index._get_model()
            return [self._compute_bge_score_realtime(mention, e, context, model) for e in entities]

        # 构建结构化的 query
        query_text = self._build_query_text(mention, context)
        model = self.vector_index._get_model()
        query_emb = model.encode(
            [query_text],
            normalize_embeddings=True
        )

        # 批量计算相似度
        scores = np.dot(entity_embs, query_emb.T).flatten()
        return scores.tolist()

    def _compute_bge_score_realtime(self, mention: str, entity: StandardEntity,
                                    context: str = "", model=None) -> float:
        """
        实时计算 BGE 语义相似度（兜底方案）
        """
        if model is None:
            model = self.vector_index._get_model()

        query_text = self._build_query_text(mention, context)
        passage_text = self._build_passage_text(entity)

        query_emb = model.encode([query_text], normalize_embeddings=True)
        passage_emb = model.encode([passage_text], normalize_embeddings=True)

        score = float(np.dot(query_emb, passage_emb.T)[0][0])
        return score

    def generate(self, mention: str, top_k: int = 50, context: str = "") -> List[Candidate]:
        """
        生成候选实体列表（使用懒加载）
        """
        candidates = []
        seen_entity_ids = set()

        # ============================================================
        # 1. 别名精确匹配（不需要向量）
        # ============================================================
        alias_entities = self.kb.get_entities_by_alias(mention)
        if alias_entities:
            logger.info(f"  📌 别名精确匹配: {mention} → {len(alias_entities)} 个实体")

            # 批量计算 BGE 分数（会触发懒加载）
            bge_scores = self._compute_batch_bge_scores(mention, alias_entities, context)

            for entity, bge_score in zip(alias_entities, bge_scores):
                final_score = min(bge_score * self.alias_weight, 1.0)

                candidates.append(
                    Candidate(
                        entity=entity,
                        score=final_score,
                        method="alias_exact",
                        metadata={
                            "match_type": "alias_exact",
                            "alias": mention,
                            "bge_score": bge_score,
                            "weight": self.alias_weight,
                            "priority": "high"
                        }
                    )
                )
                seen_entity_ids.add(entity.entity_id)

        # ============================================================
        # 2. 别名模糊匹配（不需要向量）
        # ============================================================
        fuzzy_entities = self.kb.get_entities_by_alias_fuzzy(mention, max_results=5)
        if fuzzy_entities:
            new_entities = [e for e in fuzzy_entities if e.entity_id not in seen_entity_ids]

            if new_entities:
                bge_scores = self._compute_batch_bge_scores(mention, new_entities, context)

                for entity, bge_score in zip(new_entities, bge_scores):
                    final_score = min(bge_score * (self.alias_weight - 0.02), 1.0)

                    candidates.append(
                        Candidate(
                            entity=entity,
                            score=final_score,
                            method="alias_fuzzy",
                            metadata={
                                "match_type": "alias_fuzzy",
                                "alias": mention,
                                "bge_score": bge_score,
                                "weight": self.alias_weight - 0.02,
                                "priority": "medium"
                            }
                        )
                    )
                    seen_entity_ids.add(entity.entity_id)

                logger.info(f"  📌 别名模糊匹配: {mention} → {len(new_entities)} 个实体")

        # ============================================================
        # 3. 向量检索（需要模型，懒加载）
        # ============================================================
        remaining = max(1, top_k - len(candidates))
        query = self._build_query_text(mention, context=context)

        # 使用 vector_index 的 search 方法（内部会懒加载模型）
        vector_results = self.vector_index.search(query, top_k=remaining)

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
        # 4. 排序
        # ============================================================
        candidates.sort(key=lambda c: c.score, reverse=True)

        if candidates:
            logger.info(f"  📊 候选总数: {mention} → {len(candidates)} 个")
            for c in candidates[:3]:
                bge_info = c.metadata.get("bge_score", "N/A")
                logger.info(f"      - {c.entity.standard_name} ({c.method}, 分数: {c.score:.4f})")
        else:
            logger.info(f"  ❌ 未找到候选: {mention}")

        return candidates

    def generate_with_priority(self, mention: str, top_k: int = 5, context: str = "") -> List[Candidate]:
        """按方法优先级排序"""
        candidates = self.generate(mention, top_k, context)

        method_priority = {
            "alias_exact": 0,
            "alias_fuzzy": 1,
            "vector": 2
        }
        candidates.sort(key=lambda c: (method_priority.get(c.method, 3), -c.score))

        return candidates