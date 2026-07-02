"""BGE 消歧对齐所需的轻量契约与归一化工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence

from .models import Candidate, StandardEntity


@dataclass
class BGERankingInput:
    """BGE 排序输入结构。"""

    mention: str
    candidates: Sequence[Candidate]
    context: str = ""


@dataclass
class BGERankingOutput:
    """BGE 排序输出结构。"""

    entity: StandardEntity | None
    score: float = 0.0
    method: str = "bge"
    evidence: str = ""
    raw: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "score": self.score,
            "method": self.method,
            "evidence": self.evidence,
            "raw": self.raw or {},
        }


def build_query_text(mention: str, context: str = "") -> str:
    """与同事 BGE 消歧保持一致的 query 文本拼装。"""
    if context and context.strip():
        return f"query: 上下文中的mention指的是什么？上下文：{context[:300]}，mention：{mention}"
    return f"query: 实体指称 {mention} 指的是什么？"


def build_passage_text(entity: StandardEntity) -> str:
    """与同事 BGE 消歧保持一致的 passage 文本拼装。"""
    text = f"标准实体名：{entity.standard_name}"
    if entity.aliases:
        text += f"，别名：{'、'.join(entity.aliases[:5])}"
    if entity.entity_type and entity.entity_type != "UNKNOWN":
        text += f"，类型：{entity.entity_type}"
    if entity.description:
        text += f"，描述：{entity.description}"
    industry = entity.metadata.get("industry", "")
    if industry:
        text += f"，所属行业：{industry}"
    tags = entity.metadata.get("tags", [])
    if tags:
        text += f"，标签：{'、'.join(tags[:5])}"
    return f"passage: {text}"


def normalize_bge_result(
    result: Dict[str, Any], candidates: Sequence[Candidate]
) -> BGERankingOutput:
    """把同事侧的消歧返回统一成我们这边的结果结构。"""
    entity = result.get("entity")
    if isinstance(entity, dict):
        entity = StandardEntity.from_dict(entity)
    if entity is None:
        entity_id = result.get("entity_id")
        if entity_id and entity_id != "NIL":
            for cand in candidates:
                if cand.entity.entity_id == entity_id:
                    entity = cand.entity
                    break
    return BGERankingOutput(
        entity=entity,
        score=float(result.get("score", 0.0)),
        method=result.get("method", "bge"),
        evidence=result.get("evidence", ""),
        raw=result,
    )
