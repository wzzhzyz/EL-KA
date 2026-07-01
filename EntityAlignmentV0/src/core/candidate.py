# src/core/candidate.py
from typing import List, Dict, Any, Optional
import numpy as np
from src.models.entity import StandardEntity
from src.models.candidate import Candidate
from src.knowledge.kb_manager import KnowledgeBase
from src.knowledge.vector_index import VectorIndex
from src.utils.logger import logger


class CandidateGenerator:
    """
    候选实体生成器：精确别名匹配 + 向量检索
    向量缓存由 KnowledgeBase 统一管理
    """

    def __init__(self, kb: KnowledgeBase, vector_index: VectorIndex):
        self.kb = kb
        self.vector_index = vector_index

        # 别名匹配的权重（略大于1，使别名匹配优先于纯向量检索）
        self.alias_weight = 1.05

        # 确保知识库向量已构建
        if not self.kb.has_embeddings():
            logger.info("📦 知识库向量未构建，正在构建...")
            self.kb.build_embeddings(self.vector_index.model)

        logger.info("✅ 候选生成器初始化完成")

    def _build_query_text(self, mention: str, context: str = "") -> str:
        """
        构建结构化的 query 文本

        Args:
            mention: 实体指称
            context: 上下文文本

        Returns:
            结构化的 query 字符串
        """
        if context and context.strip():
            return f"query: 上下文中的mention指的是什么？上下文：{context[:200]}，mention：{mention}"
        else:
            return f"query: 实体指称 {mention} 指的是什么？"

    def _build_passage_text(self, entity: StandardEntity) -> str:
        """
        构建结构化的 passage 文本

        Args:
            entity: 标准实体

        Returns:
            结构化的 passage 字符串
        """
        # 基础部分：标准实体名
        text = f"标准实体名：{entity.standard_name}"

        # 添加别名
        if entity.aliases:
            aliases_str = "、".join(entity.aliases[:5])
            text += f"，别名：{aliases_str}"

        # 添加实体类型
        if entity.entity_type and entity.entity_type != "UNKNOWN":
            text += f"，类型：{entity.entity_type}"

        # 添加描述
        if entity.description:
            text += f"，描述：{entity.description}"

        # 添加行业信息（从metadata中获取）
        industry = entity.metadata.get("industry", "")
        if industry:
            text += f"，所属行业：{industry}"

        # 添加标签信息
        tags = entity.metadata.get("tags", [])
        if tags:
            tags_str = "、".join(tags[:5])
            text += f"，标签：{tags_str}"

        return f"passage: {text}"

    def _compute_batch_bge_scores(self, mention: str, entities: List[StandardEntity],
                                  context: str = "") -> List[float]:
        """
        批量计算一个 mention 与多个实体的 BGE 分数
        使用结构化提示
        """
        if not entities:
            return []

        # 从KB获取缓存的向量
        entity_ids = [e.entity_id for e in entities]
        entity_embs = self.kb.get_embeddings(entity_ids)

        if len(entity_embs) == 0:
            logger.warning("⚠️ 部分实体向量不在缓存中，回退到逐个计算")
            return [self._compute_bge_score_realtime(mention, e, context) for e in entities]

        # 构建结构化的 query
        query_text = self._build_query_text(mention, context)
        query_emb = self.vector_index.model.encode(
            [query_text],
            normalize_embeddings=True
        )

        # 批量计算相似度
        scores = np.dot(entity_embs, query_emb.T).flatten()
        return scores.tolist()

    def _compute_bge_score_realtime(self, mention: str, entity: StandardEntity,
                                    context: str = "") -> float:
        """
        实时计算 BGE 语义相似度（兜底方案）
        """
        query_text = self._build_query_text(mention, context)
        passage_text = self._build_passage_text(entity)

        query_emb = self.vector_index.model.encode([query_text], normalize_embeddings=True)
        passage_emb = self.vector_index.model.encode([passage_text], normalize_embeddings=True)

        score = float(np.dot(query_emb, passage_emb.T)[0][0])
        return score

    def generate(self, mention: str, top_k: int = 50, context: str = "") -> List[Candidate]:
        """
        生成候选实体列表（使用KB缓存的向量）

        Args:
            mention: 实体指称
            top_k: 最大候选数量
            context: 上下文文本（用于结构化 query）
        """
        candidates = []
        seen_entity_ids = set()

        # ============================================================
        # 1. 别名精确匹配
        # ============================================================
        alias_entities = self.kb.get_entities_by_alias(mention)
        if alias_entities:
            logger.info(f"  📌 别名精确匹配: {mention} → {len(alias_entities)} 个实体")

            # 批量计算 BGE 分数（使用结构化提示）
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
        # 2. 别名模糊匹配
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
        # 3. 向量检索
        # ============================================================
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