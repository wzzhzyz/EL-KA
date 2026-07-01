# src/knowledge/kb_manager.py
from typing import List, Dict, Optional, Tuple
import numpy as np
from src.models.entity import StandardEntity
from src.knowledge.adapters.factory import AdapterFactory
from src.utils.logger import logger


class KnowledgeBase:
    """
    知识库管理 - 只管理已转换为内部标准格式的实体

    职责：
    1. 通过适配器加载知识库 → 内部标准实体
    2. 构建索引（别名 → entity_id, entity_id → entity）
    3. 提供查询接口
    4. 管理实体向量缓存（供向量检索和候选生成使用）
    """

    def __init__(self, config: Dict):
        # 通过适配器加载
        self.adapter = AdapterFactory.create(config)
        self.entities: List[StandardEntity] = self.adapter.load()

        # 索引
        self.alias_index: Dict[str, str] = {}  # alias → entity_id
        self.entity_map: Dict[str, StandardEntity] = {}  # entity_id → StandardEntity

        # ============================================================
        # 向量缓存（供消歧、候选生成等模块复用）
        # ============================================================
        self._embeddings: Optional[np.ndarray] = None  # 所有实体的向量矩阵
        self._entity_id_to_index: Dict[str, int] = {}  # entity_id → 向量矩阵中的索引
        self._is_embeddings_built: bool = False

        self._build_index()

        logger.info(f"✅ 知识库加载完成: {len(self.entities)} 个实体, {len(self.alias_index)} 个别名索引")

    def _build_index(self):
        """构建索引"""
        self.alias_index.clear()
        self.entity_map.clear()
        self._entity_id_to_index.clear()

        for idx, entity in enumerate(self.entities):
            eid = entity.entity_id
            self.entity_map[eid] = entity
            self._entity_id_to_index[eid] = idx

            # 标准名称作为别名
            if entity.standard_name:
                self.alias_index[entity.standard_name] = eid

            # 所有别名
            for alias in entity.aliases:
                if alias:
                    self.alias_index[alias] = eid

    # ============================================================
    # 实体向量管理
    # ============================================================

    # src/knowledge/kb_manager.py (添加向量构建方法)

    def build_embeddings(self, embedding_model) -> np.ndarray:
        """
        使用指定的编码模型构建所有实体的向量（使用结构化提示）
        """
        if self._is_embeddings_built and self._embeddings is not None:
            logger.info("📦 实体向量已存在，直接返回缓存")
            return self._embeddings

        if not self.entities:
            logger.warning("⚠️ 知识库为空，无法构建向量")
            self._embeddings = np.array([])
            self._is_embeddings_built = True
            return self._embeddings

        logger.info(f"📦 构建实体向量: {len(self.entities)} 个实体 (使用结构化 passage 提示)")

        # 构建实体表示文本（结构化提示）
        texts = []
        for entity in self.entities:
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

            texts.append(f"passage: {text}")

        # 批量编码
        embeddings = embedding_model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=True
        )

        self._embeddings = embeddings
        self._is_embeddings_built = True

        logger.info(f"✅ 实体向量构建完成: {self._embeddings.shape}")
        return self._embeddings

    def get_entity_by_vector_index(self, idx: int) -> Optional[StandardEntity]:
        """
        根据向量索引获取实体

        Args:
            idx: 向量矩阵中的索引

        Returns:
            Optional[StandardEntity]: 对应的实体
        """
        if idx < 0 or idx >= len(self.entities):
            return None
        return self.entities[idx]

    # ============================================================
    # 查询接口
    # ============================================================

    def get_entity_by_id(self, entity_id: str) -> Optional[StandardEntity]:
        return self.entity_map.get(entity_id)

    def get_entity_by_alias(self, alias: str) -> Optional[StandardEntity]:
        """精确别名匹配（只匹配完全相同的别名）"""
        eid = self.alias_index.get(alias)
        return self.entity_map.get(eid) if eid else None

    def get_entities_by_alias(self, alias: str) -> List[StandardEntity]:
        """
        别名精确匹配：返回所有匹配该别名的实体
        """
        results = []
        # 一个别名可能对应多个实体（同名异指）
        for eid, entity in self.entity_map.items():
            # 检查标准名称
            if entity.standard_name == alias:
                results.append(entity)
            # 检查别名列表
            elif alias in entity.aliases:
                results.append(entity)
        return results

    def get_entities_by_alias_fuzzy(self, alias: str, max_results: int = 5) -> List[StandardEntity]:
        """
        别名模糊匹配：返回包含该别名的实体
        用于处理别名是实体名称的一部分的情况
        """
        results = []
        alias_lower = alias.lower()

        for entity in self.entities:
            # 检查标准名称是否包含
            if alias_lower in entity.standard_name.lower():
                results.append(entity)
                continue
            # 检查别名列表
            for a in entity.aliases:
                if alias_lower in a.lower():
                    results.append(entity)
                    break

        # 限制返回数量
        return results[:max_results] if len(results) > max_results else results

    def get_all_entities(self) -> List[StandardEntity]:
        return self.entities

    def get_all_entities_dict(self) -> List[Dict]:
        return [e.to_dict() for e in self.entities]

    def reload(self, new_config: Dict = None):
        """热插拔：重新加载知识库"""
        if new_config:
            self.adapter = AdapterFactory.create(new_config)

        self.entities = self.adapter.load()
        self.alias_index.clear()
        self.entity_map.clear()
        self._entity_id_to_index.clear()
        self._embeddings = None
        self._is_embeddings_built = False

        self._build_index()
        logger.info("🔄 知识库已热更新，请重新构建向量")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        type_counts = {}
        for e in self.entities:
            etype = e.entity_type or "UNKNOWN"
            type_counts[etype] = type_counts.get(etype, 0) + 1

        return {
            "total_entities": len(self.entities),
            "total_aliases": len(self.alias_index),
            "type_counts": type_counts,
            "has_embeddings": self._is_embeddings_built,
            "embedding_shape": str(self._embeddings.shape) if self._embeddings is not None else None
        }

    # src/knowledge/kb_manager.py - 添加向量缓存管理方法
    # 在原有代码基础上添加以下方法

    # ============================================================
    # 向量缓存管理（供 VectorIndex 和 CandidateGenerator 使用）
    # ============================================================

    def set_embeddings(self, embeddings: np.ndarray, entities: List[StandardEntity] = None):
        """
        设置实体向量缓存（由 VectorIndex 调用）

        Args:
            embeddings: 向量矩阵 (N, dim)
            entities: 对应的实体列表（可选，用于校验）
        """
        if entities is not None and len(entities) != len(embeddings):
            logger.warning(f"⚠️ 实体数量({len(entities)})与向量数量({len(embeddings)})不匹配")

        self._embeddings = embeddings
        self._is_embeddings_built = True

        # 重建 entity_id → 索引映射
        self._entity_id_to_index.clear()
        for idx, entity in enumerate(self.entities):
            self._entity_id_to_index[entity.entity_id] = idx

        logger.info(f"✅ KB向量缓存已设置: {embeddings.shape}")

    def get_embedding(self, entity_id: str) -> Optional[np.ndarray]:
        """获取单个实体的向量"""
        if self._embeddings is None:
            logger.warning("⚠️ 实体向量未构建")
            return None

        idx = self._entity_id_to_index.get(entity_id)
        if idx is None:
            return None

        return self._embeddings[idx]

    def get_embeddings(self, entity_ids: List[str]) -> np.ndarray:
        """批量获取实体向量"""
        if self._embeddings is None:
            logger.warning("⚠️ 实体向量未构建")
            return np.array([])

        indices = []
        for eid in entity_ids:
            idx = self._entity_id_to_index.get(eid)
            if idx is not None:
                indices.append(idx)

        if not indices:
            return np.array([])

        return self._embeddings[indices]

    def get_all_embeddings(self) -> Optional[np.ndarray]:
        """获取所有实体的向量"""
        return self._embeddings

    def has_embeddings(self) -> bool:
        """检查是否已构建向量"""
        return self._is_embeddings_built and self._embeddings is not None

    def clear_embeddings(self):
        """清除向量缓存"""
        self._embeddings = None
        self._is_embeddings_built = False
        self._entity_id_to_index.clear()
        logger.info("🔄 KB向量缓存已清除")