# src/knowledge/vector_index.py - 优化版本
from typing import Dict, List

import faiss
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from src.models.entity import StandardEntity
from src.utils.config import resolve_path
from src.utils.lazy_loader import lazy_load
from src.utils.logger import logger


class VectorIndex:
    """
    FAISS 向量索引 - 使用懒加载模式
    """

    def __init__(self, model_path: str, kb=None):
        self.model_path = resolve_path(model_path)
        self._model = None  # 懒加载
        self.index = None
        self.entities: List[StandardEntity] = []
        self.kb = kb
        self._is_built = False

        logger.info("✅ 向量索引初始化完成（懒加载模式）")

    def _get_model(self) -> SentenceTransformer:
        """懒加载模型"""
        if self._model is None:

            def load_model():
                logger.info(f"📦 懒加载 BGE 模型: {self.model_path}")
                if torch.cuda.is_available():
                    model = SentenceTransformer(self.model_path, device="cuda")
                    logger.info("✅ BGE 模型加载完成，设备：CUDA")
                else:
                    model = SentenceTransformer(self.model_path, device="cpu")
                    logger.info("✅ BGE 模型加载完成，设备：CPU")
                return model

            self._model = lazy_load("bge_model", load_model)
        return self._model

    def _build_passage_text(self, entity: StandardEntity) -> str:
        """构建结构化的 passage 文本"""
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

    def _build_query_text(self, mention: str, context: str = "") -> str:
        """构建结构化的 query 文本"""
        if context and context.strip():
            return f"query: 上下文中的实体“{mention}”指的是什么？上下文：{context[:500]}。上下文中的实体“{mention}”是什么？"
        else:
            return f"query: 实体指称 “{mention}” 指的是什么？"

    def build(self, entities: List[StandardEntity]):
        """构建向量索引（仅构建FAISS索引，不加载模型）"""
        self.entities = entities

        if not entities:
            logger.warning("⚠️ 实体列表为空，跳过索引构建")
            return

        # 策略1：如果 KB 有缓存，直接使用
        if self.kb and self.kb.has_embeddings():
            logger.info("📦 使用 KnowledgeBase 缓存的向量构建 FAISS 索引")
            embeddings = self.kb.get_all_embeddings()

            if embeddings is not None and len(embeddings) > 0:
                if len(embeddings) == len(entities):
                    dim = embeddings.shape[1]
                    self.index = faiss.IndexFlatIP(dim)
                    self.index.add(embeddings.astype(np.float32))
                    self._is_built = True
                    logger.info(
                        f"✅ 向量索引完成: {self.index.ntotal} 个向量 (使用KB缓存)"
                    )
                    return
                else:
                    logger.warning(
                        f"⚠️ KB缓存向量数量({len(embeddings)})与实体数量({len(entities)})不一致，重新计算"
                    )

        # 策略2：标记为未构建，等待懒加载
        logger.info("📦 向量索引待构建（懒加载模式），首次检索时自动构建")
        self._is_built = False

    def _ensure_index_built(self):
        """确保索引已构建（懒加载）"""
        if self._is_built and self.index is not None:
            return

        if not self.entities:
            logger.warning("⚠️ 实体列表为空，无法构建索引")
            return

        logger.info("📦 懒加载：构建向量索引...")
        model = self._get_model()

        # 构建向量
        texts = [self._build_passage_text(e) for e in self.entities]
        embeddings = model.encode(texts, normalize_embeddings=True)

        # 缓存到KB
        if self.kb:
            self.kb.set_embeddings(embeddings, self.entities)

        # 构建FAISS索引
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings.astype(np.float32))
        self._is_built = True
        logger.info(f"✅ 向量索引构建完成: {self.index.ntotal} 个向量")

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """检索最相似的实体（懒加载）"""
        # 确保索引已构建
        self._ensure_index_built()

        if self.index is None or self.index.ntotal == 0:
            return []

        model = self._get_model()
        query_emb = model.encode([query], normalize_embeddings=True)

        scores, indices = self.index.search(query_emb.astype(np.float32), top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.entities):
                results.append({"entity": self.entities[idx], "score": float(score)})
        return results

    def reload(self, entities: List[StandardEntity]):
        """重新构建索引"""
        self.entities = []
        self.index = None
        self._is_built = False
        self.build(entities)
        logger.info("🔄 向量索引已重新构建")
