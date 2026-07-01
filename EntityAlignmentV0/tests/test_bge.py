from sentence_transformers import SentenceTransformer, util
import faiss
import numpy as np

# 加载模型（推荐 large）
model = SentenceTransformer("BAAI/bge-small-en")

# 文档样本（添加 "passage: " 前缀）
docs = [
    "passage: GPT compresses prompts by removing redundancy.",
    "passage: You can use instruction tuning to save tokens.",
    "passage: Prompt engineering affects model efficiency.",
]

doc_embeddings = model.encode(docs, normalize_embeddings=True)

# 构建索引
index = faiss.IndexFlatIP(doc_embeddings.shape[1])
index.add(doc_embeddings)

# 查询（添加 "query: " 前缀）
query = "query: How to reduce token usage in GPT?"
query_emb = model.encode(query, normalize_embeddings=True)

scores, indices = index.search(np.array([query_emb]), k=2)
for i in indices[0]:
    print(docs[i])