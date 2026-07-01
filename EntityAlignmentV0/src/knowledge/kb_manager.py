# src/knowledge/kb_manager.py
import json
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
        self.adapter = AdapterFactory.create(config)
        self.entities: List[StandardEntity] = self.adapter.load()

        # 索引
        self.alias_index: Dict[str, str] = {}  # alias → entity_id (精确匹配用)
        self.alias_multi_index: Dict[str, List[str]] = {}  # alias → [entity_id1, entity_id2, ...] (歧义别名)
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
                self._add_to_alias_index(entity.standard_name, eid)

            # 所有别名
            for alias in entity.aliases:
                if alias:
                    self._add_to_alias_index(alias, eid)

    def _add_to_alias_index(self, alias: str, entity_id: str):
        """添加别名到索引（支持歧义）"""
        # 精确匹配索引（保留第一个，兼容旧接口）
        if alias not in self.alias_index:
            self.alias_index[alias] = entity_id

        # 多值索引（支持歧义）
        if alias not in self.alias_multi_index:
            self.alias_multi_index[alias] = []
        if entity_id not in self.alias_multi_index[alias]:
            self.alias_multi_index[alias].append(entity_id)

    def get_entity_by_alias(self, alias: str) -> Optional[StandardEntity]:
        """根据别名获取实体（精确匹配）- 返回第一个匹配（保留兼容性）"""
        eid = self.alias_index.get(alias)
        if eid:
            return self.entity_map.get(eid)
        return None

    def get_entities_by_alias(self, alias: str) -> List[StandardEntity]:
        """
        根据别名获取所有匹配的实体（精确匹配）

        同一个别名可能对应多个标准实体（歧义）
        例如："国网" → 国家电网有限公司, 国网通信技术有限公司, ...
        """
        results = []
        eids = self.alias_multi_index.get(alias, [])
        for eid in eids:
            entity = self.entity_map.get(eid)
            if entity:
                results.append(entity)
        return results

    def get_entities_by_alias_fuzzy(self, alias: str, max_results: int = 5) -> List[StandardEntity]:
        """
        模糊匹配别名（包含关系）

        例如："国网" → 匹配 "国网", "国家电网", "国网公司" 等
        """
        results = []
        seen_ids = set()

        for a, eids in self.alias_multi_index.items():
            if alias in a or a in alias:  # 包含关系
                for eid in eids:
                    if eid not in seen_ids:
                        entity = self.entity_map.get(eid)
                        if entity:
                            results.append(entity)
                            seen_ids.add(eid)
                            if len(results) >= max_results:
                                return results
        return results

    def get_entity_by_id(self, entity_id: str) -> Optional[StandardEntity]:
        return self.entity_map.get(entity_id)

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
        self.alias_multi_index.clear()
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
        }# src/knowledge/kb_manager.py
import json
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
        self.adapter = AdapterFactory.create(config)
        self.entities: List[StandardEntity] = self.adapter.load()

        # 索引
        self.alias_index: Dict[str, str] = {}   # alias → entity_id (精确匹配用)
        self.alias_multi_index: Dict[str, List[str]] = {}  # alias → [entity_id1, entity_id2, ...] (歧义别名)
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
                self._add_to_alias_index(entity.standard_name, eid)

            # 所有别名
            for alias in entity.aliases:
                if alias:
                    self._add_to_alias_index(alias, eid)

    def _add_to_alias_index(self, alias: str, entity_id: str):
        """添加别名到索引（支持歧义）"""
        # 精确匹配索引（保留第一个，兼容旧接口）
        if alias not in self.alias_index:
            self.alias_index[alias] = entity_id

        # 多值索引（支持歧义）
        if alias not in self.alias_multi_index:
            self.alias_multi_index[alias] = []
        if entity_id not in self.alias_multi_index[alias]:
            self.alias_multi_index[alias].append(entity_id)

    def get_entity_by_alias(self, alias: str) -> Optional[StandardEntity]:
        """根据别名获取实体（精确匹配）- 返回第一个匹配（保留兼容性）"""
        eid = self.alias_index.get(alias)
        if eid:
            return self.entity_map.get(eid)
        return None

    def get_entities_by_alias(self, alias: str) -> List[StandardEntity]:
        """
        根据别名获取所有匹配的实体（精确匹配）

        同一个别名可能对应多个标准实体（歧义）
        例如："国网" → 国家电网有限公司, 国网通信技术有限公司, ...
        """
        results = []
        eids = self.alias_multi_index.get(alias, [])
        for eid in eids:
            entity = self.entity_map.get(eid)
            if entity:
                results.append(entity)
        return results

    def get_entities_by_alias_fuzzy(self, alias: str, max_results: int = 5) -> List[StandardEntity]:
        """
        模糊匹配别名（包含关系）

        例如："国网" → 匹配 "国网", "国网公司" 等
        """
        results = []
        seen_ids = set()

        for a, eids in self.alias_multi_index.items():
            if alias in a or a in alias:  # 包含关系
                for eid in eids:
                    if eid not in seen_ids:
                        entity = self.entity_map.get(eid)
                        if entity:
                            results.append(entity)
                            seen_ids.add(eid)
                            if len(results) >= max_results:
                                return results
        return results

    def get_entity_by_id(self, entity_id: str) -> Optional[StandardEntity]:
        return self.entity_map.get(entity_id)

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
        self.alias_multi_index.clear()
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