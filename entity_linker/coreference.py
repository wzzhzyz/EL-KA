from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence


ORG_ANAPHORS = {
    "该公司",
    "这家公司",
    "本公司",
    "该集团",
    "该企业",
    "这家企业",
    "该机构",
    "该单位",
    "该校",
    "该院",
    "该局",
    "其",
    "它",
}

PERSON_ANAPHORS = {
    "他",
    "她",
    "他们",
    "她们",
    "本人",
    "该负责人",
    "该专家",
}

COLLECTIVE_ANAPHORS = {
    "两家公司",
    "两家企业",
    "两家机构",
    "两家央企",
    "两家高校",
    "两所高校",
    "两所大学",
    "这些企业",
    "这些机构",
    "多家企业",
    "多家机构",
    "上述企业",
    "上述机构",
    "上述银行",
    "双方",
    "二者",
    "两人",
    "两地",
    "两款应用",
    "它们",
    "他们",
    "她们",
}


ORDINAL_ANAPHORS = {
    "前者": 0,
    "后者": 1,
}


def normalize_text(text: str) -> str:
    return "".join(ch for ch in str(text).strip() if not ch.isspace())


def normalize_type(entity_type: str | None) -> str:
    value = (entity_type or "UNKNOWN").upper()
    if value in {"ORGANIZATION", "COMPANY", "INSTITUTION"}:
        return "ORG"
    if value in {"PER", "PERSON"}:
        return "PERSON"
    if value in {"GPE", "LOC", "LOCATION"}:
        return value
    if value == "PRON":
        return "PRON"
    return value or "UNKNOWN"


def is_anaphor(text: str, mention_type: str = "UNKNOWN", role: str = "") -> bool:
    normalized = normalize_text(text)
    return (
        role.lower() in {"pronoun", "anaphor", "coreference"}
        or mention_type.upper() in {"PRON", "NOUN"}
        or normalized in ORG_ANAPHORS
        or normalized in PERSON_ANAPHORS
        or normalized in COLLECTIVE_ANAPHORS
        or normalized in ORDINAL_ANAPHORS
    )


def expected_antecedent_type(text: str, mention_type: str = "UNKNOWN") -> str:
    normalized = normalize_text(text)
    mention_type = normalize_type(mention_type)
    if normalized in PERSON_ANAPHORS:
        return "PERSON"
    if normalized in ORG_ANAPHORS:
        return "ORG"
    if mention_type == "PERSON":
        return "PERSON"
    if mention_type in {"ORG", "PRON", "NOUN", "UNKNOWN"}:
        return "ORG"
    return mention_type


def type_compatible(expected_type: str, antecedent_type: str) -> bool:
    expected_type = normalize_type(expected_type)
    antecedent_type = normalize_type(antecedent_type)
    if expected_type in {"UNKNOWN", "PRON", "NOUN"}:
        return True
    if expected_type == antecedent_type:
        return True
    if expected_type == "ORG" and antecedent_type in {"ORG", "GPE", "LOC"}:
        return True
    if expected_type == "LOC" and antecedent_type in {"LOC", "GPE"}:
        return True
    return False


@dataclass
class CoreferenceMention:
    mention: str
    mention_type: str = "UNKNOWN"
    char_start: int = 0
    char_end: int = 0
    sentence_index: int = 0
    role: str = "name"
    entity_id: Optional[str] = None
    entity_name: str = ""
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoreferenceMention":
        metadata = data.get("metadata", {}) or {}
        return cls(
            mention=data.get("mention", data.get("text", "")),
            mention_type=data.get("type", data.get("mention_type", "UNKNOWN")),
            char_start=int(data.get("char_start", data.get("start", 0)) or 0),
            char_end=int(data.get("char_end", data.get("end", 0)) or 0),
            sentence_index=int(
                data.get(
                    "sentence_index",
                    metadata.get("sentence_index", metadata.get("sent_id", 0)),
                )
                or 0
            ),
            role=data.get("role", data.get("mention_role", metadata.get("role", "name"))),
            entity_id=data.get("entity_id") or data.get("linked_entity_id"),
            entity_name=data.get("standard_entity", data.get("entity_name", "")),
            confidence=float(data.get("confidence", 1.0) or 0.0),
            metadata=metadata,
        )

    @property
    def normalized(self) -> str:
        return normalize_text(self.mention)


@dataclass
class CoreferenceResolution:
    mention: str
    entity_id: Optional[str]
    entity_name: str
    antecedent: Optional[str]
    antecedent_index: Optional[int]
    confidence: float
    evidence: str
    rule: str
    is_nil: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mention": self.mention,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "antecedent": self.antecedent,
            "antecedent_index": self.antecedent_index,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "rule": self.rule,
            "is_nil": self.is_nil,
        }


class RuleBasedCoreferenceResolver:
    """中文轻量规则共指解析器。

    设计边界：
    - 只处理已识别 mention 中的代词/名词性指代；
    - 先行词仅来自已经链接到标准实体的 mention；
    - 集合指代和无先行词场景返回 NIL；
    - 输出带 evidence，方便 trace 和人工复核。
    """

    def __init__(self, nil_threshold: float = 0.55, max_sentence_gap: int = 3):
        self.nil_threshold = nil_threshold
        self.max_sentence_gap = max_sentence_gap

    def resolve(
        self, mentions: Sequence[CoreferenceMention | Dict[str, Any]]
    ) -> List[CoreferenceResolution]:
        normalized_mentions = [
            item if isinstance(item, CoreferenceMention) else CoreferenceMention.from_dict(item)
            for item in mentions
        ]
        active_entities: List[tuple[int, CoreferenceMention]] = []
        resolutions: List[CoreferenceResolution] = []

        for index, mention in enumerate(normalized_mentions):
            if mention.entity_id and not is_anaphor(
                mention.mention, mention.mention_type, mention.role
            ):
                active_entities.append((index, mention))
                resolutions.append(
                    CoreferenceResolution(
                        mention=mention.mention,
                        entity_id=mention.entity_id,
                        entity_name=mention.entity_name,
                        antecedent=mention.mention,
                        antecedent_index=index,
                        confidence=1.0,
                        evidence="实体名已完成链接，作为后续共指先行词",
                        rule="linked_name",
                        is_nil=False,
                    )
                )
                continue

            resolution = self._resolve_anaphor(index, mention, active_entities)
            resolutions.append(resolution)
            if not resolution.is_nil and resolution.entity_id:
                active_entities.append(
                    (
                        index,
                        CoreferenceMention(
                            mention=resolution.antecedent or mention.mention,
                            mention_type=mention.mention_type,
                            char_start=mention.char_start,
                            char_end=mention.char_end,
                            sentence_index=mention.sentence_index,
                            role="resolved_anaphor",
                            entity_id=resolution.entity_id,
                            entity_name=resolution.entity_name,
                            confidence=resolution.confidence,
                        ),
                    )
                )

        return resolutions

    def resolve_link_results(
        self, results: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        mentions = [CoreferenceMention.from_dict(item) for item in results]
        resolutions = self.resolve(mentions)
        merged: List[Dict[str, Any]] = []
        for item, resolution in zip(results, resolutions):
            updated = dict(item)
            if item.get("is_nil", False) and not resolution.is_nil:
                updated["entity_id"] = resolution.entity_id or ""
                updated["standard_entity"] = resolution.entity_name
                updated["confidence"] = resolution.confidence
                updated["is_nil"] = False
                updated["is_coreference"] = True
                updated["resolved_from"] = resolution.antecedent
                updated["evidence"] = resolution.evidence
                updated["method"] = "coreference_rule"
            updated["coreference"] = resolution.to_dict()
            merged.append(updated)
        return merged

    def _resolve_anaphor(
        self,
        index: int,
        mention: CoreferenceMention,
        active_entities: Sequence[tuple[int, CoreferenceMention]],
    ) -> CoreferenceResolution:
        if normalize_text(mention.mention) in COLLECTIVE_ANAPHORS:
            return CoreferenceResolution(
                mention=mention.mention,
                entity_id=None,
                entity_name="",
                antecedent=None,
                antecedent_index=None,
                confidence=0.0,
                evidence="集合指代可能对应多个实体，当前输出规范只允许单一entity_id",
                rule="collective_nil",
                is_nil=True,
            )

        ordinal_position = ORDINAL_ANAPHORS.get(normalize_text(mention.mention))
        if ordinal_position is not None:
            named_antecedents = [
                (antecedent_index, antecedent)
                for antecedent_index, antecedent in active_entities
                if antecedent.role != "resolved_anaphor"
            ]
            if len(named_antecedents) >= 2:
                antecedent_index, antecedent = named_antecedents[-2 + ordinal_position]
                return CoreferenceResolution(
                    mention=mention.mention,
                    entity_id=antecedent.entity_id,
                    entity_name=antecedent.entity_name,
                    antecedent=antecedent.mention,
                    antecedent_index=antecedent_index,
                    confidence=0.86,
                    evidence=f"{mention.mention}按前者/后者顺序回指{antecedent.mention}",
                    rule="ordinal_pair",
                    is_nil=False,
                )

        if not is_anaphor(mention.mention, mention.mention_type, mention.role):
            return CoreferenceResolution(
                mention=mention.mention,
                entity_id=mention.entity_id,
                entity_name=mention.entity_name,
                antecedent=mention.mention if mention.entity_id else None,
                antecedent_index=index if mention.entity_id else None,
                confidence=mention.confidence if mention.entity_id else 0.0,
                evidence="非共指mention，保留原链接结果" if mention.entity_id else "非共指mention且无链接结果",
                rule="pass_through" if mention.entity_id else "unlinked_name_nil",
                is_nil=not bool(mention.entity_id),
            )

        expected_type = expected_antecedent_type(mention.mention, mention.mention_type)
        candidates: List[tuple[float, int, CoreferenceMention, str]] = []
        for antecedent_index, antecedent in reversed(active_entities):
            if not antecedent.entity_id:
                continue
            sentence_gap = max(0, mention.sentence_index - antecedent.sentence_index)
            if sentence_gap > self.max_sentence_gap:
                continue
            if not type_compatible(expected_type, antecedent.mention_type):
                continue
            distance = max(1, index - antecedent_index)
            score = 0.82 - 0.06 * (distance - 1) - 0.05 * sentence_gap
            if sentence_gap == 0:
                score += 0.08
            if normalize_type(expected_type) == normalize_type(antecedent.mention_type):
                score += 0.05
            rule = "recency_type_sentence"
            candidates.append((score, antecedent_index, antecedent, rule))

        if not candidates:
            return CoreferenceResolution(
                mention=mention.mention,
                entity_id=None,
                entity_name="",
                antecedent=None,
                antecedent_index=None,
                confidence=0.0,
                evidence="激活实体栈中没有类型兼容的已链接先行词",
                rule="no_compatible_antecedent",
                is_nil=True,
            )

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best_score, antecedent_index, antecedent, rule = candidates[0]
        if best_score < self.nil_threshold:
            return CoreferenceResolution(
                mention=mention.mention,
                entity_id=None,
                entity_name="",
                antecedent=antecedent.mention,
                antecedent_index=antecedent_index,
                confidence=round(best_score, 4),
                evidence=f"最高候选{antecedent.mention}分数低于阈值{self.nil_threshold:.2f}",
                rule="below_nil_threshold",
                is_nil=True,
            )

        return CoreferenceResolution(
            mention=mention.mention,
            entity_id=antecedent.entity_id,
            entity_name=antecedent.entity_name,
            antecedent=antecedent.mention,
            antecedent_index=antecedent_index,
            confidence=round(best_score, 4),
            evidence=(
                f"{mention.mention}回指最近的类型兼容实体{antecedent.mention}；"
                f"sentence_gap={mention.sentence_index - antecedent.sentence_index}"
            ),
            rule=rule,
            is_nil=False,
        )


def resolve_coreferences(
    mentions: Iterable[Dict[str, Any]], nil_threshold: float = 0.55
) -> List[Dict[str, Any]]:
    resolver = RuleBasedCoreferenceResolver(nil_threshold=nil_threshold)
    return [item.to_dict() for item in resolver.resolve(list(mentions))]
