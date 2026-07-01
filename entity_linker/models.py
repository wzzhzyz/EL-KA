from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class StandardMention:
    """内部标准 Mention 模型，兼容同事 EntityAlignmentV0 的标准格式。"""

    mention: str
    mention_type: str = "UNKNOWN"
    char_start: int = 0
    char_end: int = 0
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mention": self.mention,
            "type": self.mention_type,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardMention":
        return cls(
            mention=data.get("mention", ""),
            mention_type=data.get("type", data.get("mention_type", "UNKNOWN")),
            char_start=data.get("char_start", data.get("start", 0)),
            char_end=data.get("char_end", data.get("end", 0)),
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {}),
        )

    def to_link_result(
        self,
        entity_id: str,
        standard_name: str,
        confidence: float,
        evidence: str,
        is_nil: bool = False,
        is_coreference: bool = False,
        resolved_from: str | None = None,
    ) -> Dict[str, Any]:
        result = {
            "mention": self.mention,
            "type": self.mention_type,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "entity_id": entity_id,
            "standard_entity": standard_name,
            "confidence": confidence,
            "is_nil": is_nil,
            "evidence": evidence,
        }
        if is_coreference:
            result["is_coreference"] = True
            result["resolved_from"] = resolved_from
        return result


@dataclass
class StandardEntity:
    """内部标准实体模型，兼容同事 EntityAlignmentV0 的标准实体格式。"""

    entity_id: str
    standard_name: str
    aliases: List[str] = field(default_factory=list)
    entity_type: str = "UNKNOWN"
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "standard_name": self.standard_name,
            "aliases": self.aliases,
            "entity_type": self.entity_type,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardEntity":
        return cls(
            entity_id=data.get("entity_id", ""),
            standard_name=data.get("standard_name", data.get("entity_name", "")),
            aliases=data.get("aliases", []),
            entity_type=data.get("entity_type", data.get("type", "UNKNOWN")),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
        )


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


LINKABLE_TYPES = {"ORG", "GPE", "PERSON", "LOC"}
PRONOUN_TYPES = {"PRON", "NOUN"}
ALL_TYPES = LINKABLE_TYPES | PRONOUN_TYPES

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
