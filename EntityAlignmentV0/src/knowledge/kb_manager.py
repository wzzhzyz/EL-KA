# src/knowledge/kb_manager.py
from typing import List, Dict, Optional
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
    """

    def __init__(self, config: Dict):
        # 通过适配器加载
        self.adapter = AdapterFactory.create(config)
        self.entities: List[StandardEntity] = self.adapter.load()

        # 索引
        self.alias_index: Dict[str, str] = {}  # alias → entity_id
        self.entity_map: Dict[str, StandardEntity] = {}  # entity_id → StandardEntity

        self._build_index()

        logger.info(f"✅ 知识库加载完成: {len(self.entities)} 个实体, {len(self.alias_index)} 个别名索引")

    def _build_index(self):
        """构建索引"""
        for entity in self.entities:
            eid = entity.entity_id
            self.entity_map[eid] = entity

            # 标准名称作为别名
            if entity.standard_name:
                self.alias_index[entity.standard_name] = eid

            # 所有别名
            for alias in entity.aliases:
                if alias:
                    self.alias_index[alias] = eid

    def get_entity_by_id(self, entity_id: str) -> Optional[StandardEntity]:
        return self.entity_map.get(entity_id)

    def get_entity_by_alias(self, alias: str) -> Optional[StandardEntity]:
        eid = self.alias_index.get(alias)
        return self.entity_map.get(eid) if eid else None

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
        self._build_index()
        logger.info(f"🔄 知识库已热更新")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        type_counts = {}
        for e in self.entities:
            etype = e.entity_type or "UNKNOWN"
            type_counts[etype] = type_counts.get(etype, 0) + 1

        return {
            "total_entities": len(self.entities),
            "total_aliases": len(self.alias_index),
            "type_counts": type_counts
        }