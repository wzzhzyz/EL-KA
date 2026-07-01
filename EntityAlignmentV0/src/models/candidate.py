# src/models/candidate.py
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from src.models.entity import StandardEntity


@dataclass
class Candidate:
    """候选实体结构，统一各模块数据交互的实体对象。"""

    entity: StandardEntity
    score: float = 0.0
    method: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, entity_as_dict: bool = False) -> Dict[str, Any]:
        return {
            "entity": self.entity.to_dict() if entity_as_dict else self.entity,
            "score": self.score,
            "method": self.method,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Candidate":
        entity = data.get("entity")
        if isinstance(entity, dict):
            entity = StandardEntity.from_dict(entity)
        return cls(
            entity=entity,
            score=float(data.get("score", 0.0)),
            method=data.get("method", "unknown"),
            metadata=data.get("metadata", {}),
        )

    def __lt__(self, other: "Candidate") -> bool:
        """用于排序：分数高的排在前面"""
        if not isinstance(other, Candidate):
            return NotImplemented
        return self.score > other.score

    def __eq__(self, other) -> bool:
        """判断是否为同一候选（基于实体ID）"""
        if not isinstance(other, Candidate):
            return False
        return self.entity.entity_id == other.entity.entity_id

    def __hash__(self) -> int:
        """用于 set/dict 去重（基于实体ID）"""
        return hash(self.entity.entity_id)