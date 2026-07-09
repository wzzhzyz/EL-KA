# src/knowledge/adapters/factory.py
from typing import Dict
from .base import KnowledgeAdapter
from .json_adapter import JSONAdapter


class AdapterFactory:
    """适配器工厂 - 根据配置选择适配器"""

    @staticmethod
    def create(config: Dict) -> KnowledgeAdapter:
        kb_type = config.get("type", "json")

        if kb_type == "json":
            return JSONAdapter(config["path"])
        elif kb_type == "neo4j":
            # 未来扩展
            raise NotImplementedError("Neo4j 适配器尚未实现")
        else:
            raise ValueError(f"不支持的知识库类型: {kb_type}")