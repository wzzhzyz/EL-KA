"""实体链接各模块的端口/契约定义。"""

from __future__ import annotations

from typing import Any, Dict, List, Protocol, Sequence, runtime_checkable

from .models import Candidate, StandardEntity, StandardMention


@runtime_checkable
class NERPort(Protocol):
    """NER 输入/输出端口。"""

    def extract(self, text: str) -> List[StandardMention]: ...


@runtime_checkable
class KnowledgeBasePort(Protocol):
    """知识库访问端口。"""

    def get_entities_by_alias(self, alias: str) -> List[StandardEntity]: ...

    def get_entities_by_alias_fuzzy(
        self, alias: str, max_results: int = 5
    ) -> List[StandardEntity]: ...

    def get_all_entities(self) -> List[StandardEntity]: ...


@runtime_checkable
class CandidateGeneratorPort(Protocol):
    """候选生成端口。"""

    def generate(
        self, mention: str, top_k: int = 50, context: str = ""
    ) -> List[Candidate]: ...


@runtime_checkable
class DisambiguatorPort(Protocol):
    """BGE/LLM 消歧端口。"""

    nil_threshold: float

    def disambiguate(
        self,
        mention: str,
        candidates: Sequence[Candidate],
        context: str = "",
    ) -> Dict[str, Any]: ...


DisambiguationDict = Dict[str, Any]
"""统一消歧结果字典约定：
{
    'entity': StandardEntity | None,
    'score': float,
    'method': str,
    'evidence': str,
    '...': optional fields
}
"""
