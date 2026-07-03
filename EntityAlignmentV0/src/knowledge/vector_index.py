# src/knowledge/vector_index.py
import numpy as np
import faiss
from typing import List, Dict, Optional

import torch.cuda
from sentence_transformers import SentenceTransformer
from src.models.entity import StandardEntity
from src.utils.logger import logger
from src.utils.config import resolve_path


class VectorIndex:
    """
    FAISS 向量索引 - 使用 BGE 指令前缀优化 + 结构化提示
    """

    def __init__(self, model_path: str, kb=None):
        self.model_path = resolve_path(model_path)
        self.model = None
        self.index = None
        self.entities: List[StandardEntity] = []
        self.kb = kb

    def _load_model(self):
        if self.model is None:
            logger.info(f"📦 加载 BGE 模型: {self.model_path}")
            if(torch.cuda.is_available()):
                self.model=SentenceTransformer(self.model_path,device='cuda')
                logger.info(f"✅ BGE 模型加载完成，设备：CUDA")

            else:
                self.model=SentenceTransformer(self.model_path,device='cpu')
                logger.info(f"✅ BGE 模型加载完成，设备：CPU")

    def _build_passage_text(self, entity: StandardEntity) -> str:
        """
        构建结构化的 passage 文本（与 CandidateGenerator 保持一致）
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
            return f"query: 上下文中的实体“{mention}”指的是什么？上下文：{context[:500]}。上下文中的实体“{mention}”是什么？"
        else:
            return f"query: 实体指称 “{mention}” 指的是什么？"

    def build(self, entities: List[StandardEntity]):
        """构建向量索引"""
        self._load_model()
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
                    logger.info(f"✅ 向量索引完成: {self.index.ntotal} 个向量 (使用KB缓存)")
                    return
                else:
                    logger.warning(f"⚠️ KB缓存向量数量({len(embeddings)})与实体数量({len(entities)})不一致，重新计算")

        # 策略2：自行计算向量（使用结构化提示）
        logger.info("📦 自行构建实体向量 (使用结构化 passage 提示)")

        texts = []
        for entity in entities:
            text = self._build_passage_text(entity)
            texts.append(text)

        logger.info(f"📦 构建向量索引: {len(texts)} 个实体")
        embeddings = self.model.encode(texts, normalize_embeddings=True)

        if self.kb:
            logger.info("📦 将向量缓存到 KnowledgeBase")
            self.kb.set_embeddings(embeddings, entities)

        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings.astype(np.float32))
        logger.info(f"✅ 向量索引完成: {self.index.ntotal} 个向量")
        logger.info(f"   📝 使用结构化 passage 格式: 'passage: 标准实体名：xxx，别名：xxx，描述：xxx'")

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """检索最相似的实体"""
        if self.index is None or self.index.ntotal == 0:
            return []

        self._load_model()

        # 注意，这里嵌入前没有对query进行任何加工
        query_emb = self.model.encode([query], normalize_embeddings=True)

        scores, indices = self.index.search(query_emb.astype(np.float32), top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.entities):
                results.append({
                    "entity": self.entities[idx],
                    "score": float(score)
                })
        return results

    def reload(self, entities: List[StandardEntity]):
        """重新构建索引"""
        self.entities = []
        self.index = None
        self.build(entities)
        logger.info("🔄 向量索引已重新构建")