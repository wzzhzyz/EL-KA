"""
共指消解模块
整合：复数代词分类器 + Sentence-BERT 嵌入 + DBSCAN 聚类 + 多链归属
"""

import torch
import numpy as np
from typing import List, Dict, Tuple
import warnings

warnings.filterwarnings("ignore")

# ============ 1. 导入依赖 ============
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances

# 复数代词分类器
from src.models.XLMRobertaForPronounClassification import (
    XLMRobertaForPronounClassification,
    predict_pronoun
)


# ============ 2. 工具函数 ============

def mark_mention_in_context(doc: str, start: int, end: int, window: int = 100) -> str:
    """用 【mention】 标记 mention 在上下文中的位置"""
    mention_text = doc[start:end]
    ctx_start = max(0, start - window)
    ctx_end = min(len(doc), end + window)
    context = doc[ctx_start:ctx_end]
    mention_start = start - ctx_start
    mention_end = end - ctx_start
    return context[:mention_start] + f"【{mention_text}】" + context[mention_end:]


# ============ 3. 主共指消解类 ============

class CoreferenceResolver:
    """
    共指消解器
    整合：复数代词分类器 + Sentence-BERT 嵌入 + DBSCAN 聚类 + 多链归属
    """

    def __init__(
            self,
            embedding_model_path: str = './models_cache/finetuned_paraphase',
            pronoun_classifier_path: str = './models_cache/plural_pron_cls0',
            threshold: float = 0.65,
            device: str = None
    ):
        """
        初始化共指消解器

        Args:
            embedding_model_path: Sentence-BERT 模型路径（微调后的）
            pronoun_classifier_path: 复数代词分类器路径（训练好的）
            threshold: DBSCAN 聚类阈值 (0.5-0.75)，值越大聚类越严格
            device: 'cuda' 或 'cpu'
        """
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.threshold = threshold

        # ========== 1. 加载复数代词分类器 ==========
        print(f"📂 加载复数代词分类器: {pronoun_classifier_path}")
        self.pronoun_model = XLMRobertaForPronounClassification.from_pretrained(
            pronoun_classifier_path,
            device=self.device
        )
        self.pronoun_tokenizer = self.pronoun_model.tokenizer
        print(f"✅ 复数代词分类器加载成功 (设备: {self.device})")

        # ========== 2. 加载句子嵌入模型 ==========
        print(f"📂 加载嵌入模型: {embedding_model_path}")
        self.embedding_model = SentenceTransformer(embedding_model_path)
        if torch.cuda.is_available():
            self.embedding_model = self.embedding_model.to(self.device)
        print(f"✅ 嵌入模型加载成功")

        # ========== 3. 复数代词词表（兜底） ==========
        self.plural_pronouns = {
            "它们", "他们", "她们", "我们", "咱们",
            "你们", "这些", "那些", "两者", "二者",
            "双方", "各家", "诸位"
        }
        self.singular_pronouns = {
            "它", "他", "她", "我", "你", "这", "那", "其"
        }

    def is_plural_pronoun(
            self,
            text: str,
            char_start: int,
            char_end: int,
            mention_text: str = None
    ) -> Tuple[bool, float]:
        """
        判断指定位置的代词是否为复数
        优先使用分类器，兜底使用词表
        """
        if mention_text is None:
            mention_text = text[char_start:char_end]

        # 先用词表快速判断
        if mention_text in self.plural_pronouns:
            return True, 1.0
        if mention_text in self.singular_pronouns:
            return False, 1.0

        # 用分类器判断
        try:
            result = predict_pronoun(
                text=text,
                char_start=char_start,
                char_end=char_end,
                model=self.pronoun_model,
                tokenizer=self.pronoun_tokenizer,
                device=self.device
            )
            return result['label'] == 1, result['confidence']
        except Exception as e:
            print(f"⚠️ 分类器预测失败: {e}")
            return False, 0.0

    def encode_with_context(
            self,
            doc: str,
            char_start: int,
            char_end: int,
            window: int = 100
    ) -> np.ndarray:
        """编码带上下文的 mention"""
        marked = mark_mention_in_context(doc, char_start, char_end, window)
        return self.embedding_model.encode(marked, convert_to_numpy=True)

    def resolve(
            self,
            doc: str,
            mentions: List[Dict],
            return_pairwise: bool = False
    ) -> Dict:
        """
        共指消解主方法

        Args:
            doc: 原文
            mentions: mention 列表，每个元素包含 char_start, char_end, name
            return_pairwise: 是否返回 pairwise 距离

        Returns:
            {
                "clusters": [[mention1, mention2], [mention3]],
                "plural_results": [{"pronoun": "它们", "referents": ["华为", "腾讯"]}],
                "mention_classifications": [
                    {"text": "它们", "is_plural": True, "confidence": 0.98}
                ],
                "pairwise_distances": [...],  # 可选
                "mention_texts": [...]
            }
        """
        if len(mentions) < 2:
            return {
                "clusters": [[m] for m in mentions],
                "plural_results": [],
                "mention_classifications": [],
                "pairwise_distances": [],
                "mention_texts": [doc[m['char_start']:m['char_end']] for m in mentions]
            }

        mention_texts = [doc[m['char_start']:m['char_end']] for m in mentions]

        # ========== 步骤1: 判断哪些是复数代词 ==========
        mention_classifications = []
        plural_indices = []

        for i, mention in enumerate(mentions):
            is_plural, conf = self.is_plural_pronoun(
                doc,
                mention['char_start'],
                mention['char_end'],
                mention_texts[i]
            )
            mention_classifications.append({
                'index': i,
                'text': mention_texts[i],
                'char_start': mention['char_start'],
                'char_end': mention['char_end'],
                'is_plural': is_plural,
                'confidence': conf
            })
            if is_plural:
                plural_indices.append(i)

        # ========== 步骤2: 编码所有 mention ==========
        embeddings = [
            self.encode_with_context(doc, m['char_start'], m['char_end'])
            for m in mentions
        ]
        embeddings = np.array(embeddings)

        # ========== 步骤3: 实体聚类（排除复数代词） ==========
        non_plural_indices = [i for i in range(len(mentions)) if i not in plural_indices]

        if len(non_plural_indices) < 2:
            clusters = [[m] for m in mentions]
        else:
            non_plural_embs = embeddings[non_plural_indices]
            clustering = DBSCAN(eps=1 - self.threshold, min_samples=1, metric='cosine')
            labels = clustering.fit_predict(non_plural_embs)

            clusters_dict = {}
            for idx, label in zip(non_plural_indices, labels):
                if label != -1:
                    clusters_dict.setdefault(str(label), []).append(mentions[idx])
            clusters = list(clusters_dict.values())

        # ========== 步骤4: 分配复数代词到簇 ==========
        for p_idx in plural_indices:
            pronoun_emb = embeddings[p_idx]
            assigned_clusters = []

            for cluster in clusters:
                max_sim = 0.0
                for mention in cluster:
                    m_idx = mentions.index(mention)
                    sim = 1 - cosine_distances([pronoun_emb], [embeddings[m_idx]])[0][0]
                    max_sim = max(max_sim, sim)

                if max_sim >= self.threshold:
                    assigned_clusters.append(cluster)

            if assigned_clusters:
                for cluster in assigned_clusters:
                    if mentions[p_idx] not in cluster:
                        cluster.append(mentions[p_idx])
            else:
                clusters.append([mentions[p_idx]])

        # ========== 步骤5: 去重 ==========(无需，因为复数代词多链归属)
        #clusters = self._deduplicate_clusters(clusters)

        # ========== 步骤6: 提取复数代词映射 ==========
        plural_results = []
        for cluster in clusters:
            cluster_texts = [doc[m['char_start']:m['char_end']] for m in cluster]
            for p in self.plural_pronouns:
                if p in cluster_texts:
                    referents = [
                        doc[m['char_start']:m['char_end']] for m in cluster
                        if doc[m['char_start']:m['char_end']] != p
                    ]
                    if referents:
                        plural_results.append({
                            "pronoun": p,
                            "referents": referents
                        })

        # ========== 步骤7: Pairwise 距离（可选） ==========
        pairwise_distances = []
        if return_pairwise and len(mentions) >= 2:
            for i in range(len(mentions)):
                for j in range(i + 1, len(mentions)):
                    dist = cosine_distances([embeddings[i]], [embeddings[j]])[0][0]
                    pairwise_distances.append({
                        "mention_i": mention_texts[i],
                        "mention_j": mention_texts[j],
                        "distance": float(dist),
                        "similarity": float(1 - dist)
                    })
            pairwise_distances.sort(key=lambda x: x["distance"])

        return {
            "clusters": clusters,
            "plural_results": plural_results,
            "mention_classifications": mention_classifications,
            "pairwise_distances": pairwise_distances,
            "mention_texts": mention_texts
        }

    def _deduplicate_clusters(self, clusters: List[List[Dict]]) -> List[List[Dict]]:
        """去重：确保同一个实体不在多个簇中"""
        seen = set()
        result = []

        for cluster in clusters:
            clean_cluster = []
            for mention in cluster:
                key = (mention['char_start'], mention['char_end'])
                if key not in seen:
                    seen.add(key)
                    clean_cluster.append(mention)
            if clean_cluster:
                result.append(clean_cluster)

        return result


# ============ 4. 便捷函数 ============

def resolve_coreference(
        doc: str,
        mentions: List[Dict],
        embedding_model_path: str = './models_cache/finetuned_paraphase',
        pronoun_classifier_path: str = './models_cache/plural_pron_cls0',
        threshold: float = 0.65,
        return_pairwise: bool = False
) -> Dict:
    """
    便捷调用函数
    """
    resolver = CoreferenceResolver(
        embedding_model_path=embedding_model_path,
        pronoun_classifier_path=pronoun_classifier_path,
        threshold=threshold
    )
    return resolver.resolve(doc, mentions, return_pairwise)


# ============ 5. 测试 ============

if __name__ == "__main__":
    # 测试数据
    test_doc = "漓江是闻名遐迩的旅游胜地。这条河流风景秀丽，它每年吸引大量游客前来。这位教授李强也慕名前往这片水域采风，他在这里停留了整整一周。"
    test_mentions = [
        {"name": "漓江", "char_start": 0, "char_end": 2},
        {"name": "这条河流", "char_start": 13, "char_end": 17},
        {"name": "它", "char_start": 22, "char_end": 23},
        {"name": "这片水域", "char_start": 45, "char_end": 49},
        {"name": "这位教授李强", "char_start": 34, "char_end": 40},
        {"name": "他", "char_start": 52, "char_end": 53}
    ]

    print("=" * 60)
    print("共指消解测试")
    print("=" * 60)
    print(f"文档: {test_doc}")
    print(f"Mentions: {[m['name'] for m in test_mentions]}")

    # 执行共指消解
    resolver = CoreferenceResolver(
        embedding_model_path='../../models_cache/finetuned_paraphase',
        pronoun_classifier_path='../../models_cache/plural_pron_cls0',
        threshold=0.65
    )

    result = resolver.resolve(test_doc, test_mentions, return_pairwise=True)

    print("\n" + "=" * 60)
    print("复数代词分类结果")
    print("=" * 60)
    for item in result['mention_classifications']:
        status = "✅ 复数" if item['is_plural'] else "❌ 单数"
        print(f"  {item['text']}: {status} (置信度: {item['confidence']:.4f})")

    print("\n" + "=" * 60)
    print("共指簇")
    print("=" * 60)
    for i, cluster in enumerate(result['clusters']):
        texts = [test_doc[m['char_start']:m['char_end']] for m in cluster]
        print(f"  簇 {i + 1}: {texts}")

    print("\n" + "=" * 60)
    print("复数代词映射")
    print("=" * 60)
    for item in result['plural_results']:
        print(f"  '{item['pronoun']}' -> {item['referents']}")

    if result['pairwise_distances']:
        print("\n" + "=" * 60)
        print("Pairwise 距离（最近的前10对）")
        print("=" * 60)
        for item in result['pairwise_distances'][:10]:
            print(f"  {item['mention_i']} - {item['mention_j']}: {item['distance']:.4f}")