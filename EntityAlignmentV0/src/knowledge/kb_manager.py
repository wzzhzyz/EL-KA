# src/knowledge/kb_manager.py
import json
from typing import List, Dict, Optional
from src.utils.logger import logger


class KnowledgeBase:
    """知识库管理 - 支持热插拔"""

    def __init__(self, kb_type: str = "json", path: str = None):
        self.kb_type = kb_type
        self.path = path
        self.entities: List[Dict] = []
        self.alias_index: Dict[str, str] = {}  # alias → entity_id
        self.entity_map: Dict[str, Dict] = {}  # entity_id → entity
        self._load()

    def _load(self):
        """加载知识库"""
        if self.kb_type == "json":
            with open(self.path, "r", encoding="utf-8") as f:
                self.entities = json.load(f)
        else:
            raise ValueError(f"不支持的知识库类型: {self.kb_type}")

        # 构建索引
        for entity in self.entities:
            eid = entity["entity_id"]
            self.entity_map[eid] = entity

            # 标准名称也作为别名
            self.alias_index[entity["standard_name"]] = eid

            # 所有别名
            for alias in entity.get("aliases", []):
                self.alias_index[alias] = eid

        logger.info(f"✅ 知识库加载完成: {len(self.entities)} 个实体, {len(self.alias_index)} 个别名索引")

    def get_entity_by_id(self, entity_id: str) -> Optional[Dict]:
        """根据ID获取实体"""
        return self.entity_map.get(entity_id)

    def get_entity_by_alias(self, alias: str) -> Optional[Dict]:
        """根据别名获取实体（精确匹配）"""
        eid = self.alias_index.get(alias)
        if eid:
            return self.entity_map.get(eid)
        return None

    def get_all_entities(self) -> List[Dict]:
        """获取所有实体"""
        return self.entities

    def reload(self, new_path: str = None):
        """热插拔：重新加载知识库"""
        if new_path:
            self.path = new_path
        self.alias_index.clear()
        self.entity_map.clear()
        self._load()
        logger.info(f"🔄 知识库已热更新: {self.path}")