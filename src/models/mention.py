# src/models/mention.py
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class StandardMention:
    """
    内部标准 Mention 模型

    所有 NER 适配器的统一输出格式
    """
    mention: str  # 实体指称文本（必填）
    mention_type: str = "UNKNOWN"  # 实体类型（ORG/GPE/PERSON/PRON等）
    char_start: int = 0  # 在原文中的字符起始位置
    char_end: int = 0  # 在原文中的字符结束位置（不含）
    confidence: float = 1.0  # NER 识别的置信度
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展信息

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "mention": self.mention,
            "type": self.mention_type,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "confidence": self.confidence,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardMention":
        """从字典创建 Mention（兼容旧字段名）"""
        return cls(
            mention=data.get("mention", ""),
            mention_type=data.get("type", data.get("mention_type", "UNKNOWN")),
            char_start=data.get("char_start", data.get("start", 0)),
            char_end=data.get("char_end", data.get("end", 0)),
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {})
        )

    def to_link_result(self, entity_id: str, standard_name: str,
                       confidence: float, evidence: str,
                       is_nil: bool = False,
                       is_coreference: bool = False,
                       resolved_from: str = None) -> Dict:
        """转换为链接结果字典（用于输出）"""
        result = {
            "mention": self.mention,
            "type": self.mention_type,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "entity_id": entity_id,
            "standard_entity": standard_name,
            "confidence": confidence,
            "is_nil": is_nil,
            "evidence": evidence
        }
        if is_coreference:
            result["is_coreference"] = True
            result["resolved_from"] = resolved_from
        return result


# ============================================================
# 标准类型定义
# ============================================================

# 可链接的实体类型
LINKABLE_TYPES = {"ORG", "GPE", "PERSON", "LOC"}

# 代词类型
PRONOUN_TYPES = {"PRON", "NOUN"}

# 所有类型
ALL_TYPES = LINKABLE_TYPES | PRONOUN_TYPES

# ============================================================
# 类型映射（HanLP → 标准类型）
# ============================================================

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