# src/knowledge/vector_index.py
import numpy as np
import faiss
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from src.utils.logger import logger
from src.utils.config import resolve_path


class VectorIndex:
    def __init__(self, model_path: str):
        # 确保路径存在
        self.model_path = resolve_path(model_path)
        self.model = None
        self.index = None
        self.entities = []

    def _load_model(self):
        if self.model is None:
            logger.info(f"📦 加载 BGE 模型: {self.model_path}")
            self.model = SentenceTransformer(self.model_path)
            logger.info("✅ BGE 模型加载完成")

    def build(self, entities: List[Dict]):
        self._load_model()
        self.entities = entities

        if not entities:
            return

        texts = []
        for e in entities:
            text = e["standard_name"]
            if e.get("aliases"):
                text += " " + " ".join(e["aliases"][:3])
            if e.get("description"):
                text += " " + e["description"]
            texts.append(text)

        logger.info(f"📦 构建向量索引: {len(texts)} 个实体")
        embeddings = self.model.encode(texts, normalize_embeddings=True)

        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings.astype(np.float32))
        logger.info(f"✅ 向量索引完成: {self.index.ntotal} 个向量")

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if self.index is None or self.index.ntotal == 0:
            return []

        self._load_model()
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