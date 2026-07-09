# src/models/entity.py
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class StandardEntity:
    """内部标准实体模型 - 所有知识库适配器的统一输出格式"""

    entity_id: str  # 全局唯一ID（必填）
    standard_name: str  # 标准名称/全称（必填）
    aliases: List[str] = field(default_factory=list)  # 别名列表
    entity_type: str = "UNKNOWN"  # 实体类型（ORG/GPE/PERSON等）
    description: str = ""  # 实体描述（可选，用于消歧）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展字段

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "entity_id": self.entity_id,
            "standard_name": self.standard_name,
            "aliases": self.aliases,
            "entity_type": self.entity_type,
            "description": self.description,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardEntity":
        """从字典创建实体"""
        return cls(
            entity_id=data.get("entity_id", ""),
            standard_name=data.get("standard_name", ""),
            aliases=data.get("aliases", []),
            entity_type=data.get("entity_type", "UNKNOWN"),
            description=data.get("description", ""),
            metadata=data.get("metadata", {})
        )


# 类型映射：HanLP 类型 → 标准类型
TYPE_MAPPING = {
    "ORGANIZATION": "ORG",
    "ORG": "ORG",
    "nt": "ORG",
    "PERSON": "PERSON",
    "nr": "PERSON",
    "LOCATION": "GPE",
    "LOC": "GPE",
    "ns": "GPE",
    "GPE": "GPE",
}