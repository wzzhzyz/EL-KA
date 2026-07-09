# src/knowledge/adapters/json_adapter.py
import json
from typing import List, Dict
from src.models.entity import StandardEntity, TYPE_MAPPING
from .base import KnowledgeAdapter


class JSONAdapter(KnowledgeAdapter):
    """JSON 知识库适配器 - 支持新版 energy_entities.json 和旧版格式"""

    def __init__(self, path: str):
        self.path = path

    def load(self) -> List[StandardEntity]:
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 判断格式
        if isinstance(data, dict) and ("schema_version" in data or "entities" in data):
            return self._load_new_format(data)
        else:
            return self._load_old_format(data)

    def _load_new_format(self, data: dict) -> List[StandardEntity]:
        """加载新版格式（含 schema_version / entities）"""
        entities = []
        for e in data.get("entities", []):
            # 提取别名（支持对象数组或字符串列表）
            aliases = []
            for a in e.get("aliases", []):
                if isinstance(a, dict):
                    name = a.get("name", "")
                    if name:
                        aliases.append(name)
                elif isinstance(a, str):
                    aliases.append(a)

            # 类型映射
            raw_type = e.get("entity_type", "UNKNOWN")
            entity_type = TYPE_MAPPING.get(raw_type, raw_type)

            # 构建完整的 metadata
            metadata = {
                # 基础信息
                "entity_type_display": e.get("entity_type_display", ""),
                "industry": e.get("industry", ""),
                "abbreviation": e.get("abbreviation", ""),

                # 描述与业务
                "summary": e.get("summary", ""),
                "business": e.get("business", ""),

                # 位置信息
                "location": e.get("location", {}),

                # 关键词
                "keywords": e.get("keywords", []),

                # 来源信息
                "source": e.get("source", {}),

                # 标签
                "tags": e.get("tags", []),

                # 关系
                "relations": e.get("relations", []),

                # 消歧信息
                "ambiguity_level": e.get("ambiguity_level", "base"),
                "shared_aliases": e.get("shared_aliases", []),

                # 时间戳
                "update_time": e.get("update_time", ""),

                # 证据（如果有）
                "evidence": e.get("evidence", {}),
            }

            entity = StandardEntity(
                entity_id=e.get("entity_id", ""),
                standard_name=e.get("entity_name", ""),
                aliases=aliases,
                entity_type=entity_type,
                description=e.get("summary", ""),  # 使用 summary 作为描述
                metadata=metadata
            )
            entities.append(entity)

        return entities

    def _load_old_format(self, data: list) -> List[StandardEntity]:
        """加载旧版简单格式（兼容）"""
        entities = []
        for e in data:
            raw_type = e.get("type", "UNKNOWN")
            entity_type = TYPE_MAPPING.get(raw_type, raw_type)

            entity = StandardEntity(
                entity_id=e.get("entity_id", ""),
                standard_name=e.get("standard_name", ""),
                aliases=e.get("aliases", []),
                entity_type=entity_type,
                description=e.get("description", ""),
                metadata={}
            )
            entities.append(entity)

        return entities

    def get_stats(self) -> Dict:
        return {"type": "json", "path": self.path}