from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence
from .collective_ambiguity import evaluate_collective_ambiguity


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
    "两者",
    "该二者",
    "三方",
    "各方",
    "上述单位",
    "两人",
    "两地",
    "两款应用",
    "它们",
    "他们",
    "她们",
}

# These are textual coordination markers between antecedent mentions.  They
# intentionally exclude collective anaphors such as “双方” and “两家机构”.
COORDINATE_CONJUNCTIONS = {"和", "与", "及", "以及", "、", "同", "跟", "连同", "会同"}

# Collective surfaces have different cardinality semantics.  These constraints
# are evaluated only after a same-sentence, explicitly coordinated, linked and
# homogeneous group has been extracted; they do not expand the search window.
EXACT_TWO_COLLECTIVE_ANAPHORS = {
    "双方",
    "二者",
    "两者",
    "该二者",
    "两家公司",
    "两家企业",
    "两家机构",
    "两家央企",
    "两家高校",
    "两所高校",
    "两所大学",
    "两人",
    "两地",
    "两款应用",
}
EXACT_THREE_COLLECTIVE_ANAPHORS = {"三方"}


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


def collective_cardinality_satisfied(surface: str, entity_count: int) -> bool:
    """Apply lexical cardinality without guessing a partial entity set."""
    normalized = normalize_text(surface)
    if normalized in EXACT_TWO_COLLECTIVE_ANAPHORS:
        return entity_count == 2
    if normalized in EXACT_THREE_COLLECTIVE_ANAPHORS:
        return entity_count == 3
    return entity_count >= 2


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
    # Backward-compatible multi-antecedent fields.  ``entity_id`` remains the
    # legacy single-target field; a successful collective resolution instead
    # uses ``entity_ids`` while keeping ``entity_id=None``.
    entity_ids: List[str] = field(default_factory=list)
    antecedent_mentions: List[str] = field(default_factory=list)
    antecedent_indices: List[int] = field(default_factory=list)
    is_collective: bool = False
    debug_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Populate collection fields for legacy single-entity resolutions."""
        if not self.is_nil and self.entity_id and not self.entity_ids:
            self.entity_ids = [self.entity_id]
        if self.antecedent and not self.antecedent_mentions:
            self.antecedent_mentions = [self.antecedent]
        if self.antecedent_index is not None and not self.antecedent_indices:
            self.antecedent_indices = [self.antecedent_index]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mention": self.mention,
            "entity_id": self.entity_id,
            "entity_ids": list(self.entity_ids),
            "entity_name": self.entity_name,
            "antecedent": self.antecedent,
            "antecedent_index": self.antecedent_index,
            "antecedent_mentions": list(self.antecedent_mentions),
            "antecedent_indices": list(self.antecedent_indices),
            "confidence": self.confidence,
            "evidence": self.evidence,
            "rule": self.rule,
            "is_nil": self.is_nil,
            "is_collective": self.is_collective,
            "debug_metadata": dict(self.debug_metadata),
        }


@dataclass(frozen=True)
class CoordinatedGroupCandidate:
    """Internal, read-only representation of an explicit coordination group.

    The production resolver continues to select the nearest legal group.  This
    structure exists so offline experiments can inspect every group that the
    existing extraction logic considers legal without changing that decision.
    """

    mention_indices: tuple[int, ...]
    entity_ids: tuple[str, ...]
    entity_types: tuple[str, ...]
    source_sentence_index: int
    source_span_start: int
    source_span_end: int
    group_text: str
    conjunctions: tuple[str, ...]
    extraction_rule: str
    evidence: str


class RuleBasedCoreferenceResolver:
    """中文轻量规则共指解析器。

    设计边界：
    - 只处理已识别 mention 中的代词/名词性指代；
    - 先行词仅来自已经链接到标准实体的 mention；
    - 集合指代和无先行词场景返回 NIL；
    - 输出带 evidence，方便 trace 和人工复核。
    """

    def __init__(self, nil_threshold: float = 0.3, max_sentence_gap: int = 3, enable_collective_ambiguity_rejection: bool = True):
        self.nil_threshold = nil_threshold
        self.max_sentence_gap = max_sentence_gap
        self.enable_collective_ambiguity_rejection = enable_collective_ambiguity_rejection

    def resolve(
        self,
        mentions: Sequence[CoreferenceMention | Dict[str, Any]],
        text: str = "",
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

            resolution = self._resolve_anaphor(
                index,
                mention,
                active_entities,
                normalized_mentions,
                text,
            )
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

    @staticmethod
    def _is_collective_entity_type(mention: CoreferenceMention) -> bool:
        """Only homogeneous ORG/PERSON groups are safe collective antecedents."""
        return normalize_type(mention.mention_type) in {"ORG", "PERSON"}

    @staticmethod
    def _has_coordinate_conjunction(
        text: str,
        left: CoreferenceMention,
        right: CoreferenceMention,
    ) -> bool:
        if not text or right.char_start < left.char_end:
            return False
        between = text[left.char_end : right.char_start]
        return any(marker in between for marker in COORDINATE_CONJUNCTIONS)

    def _collect_coordinated_group_candidates(
        self,
        text: str,
        current_index: int,
        mentions: Sequence[CoreferenceMention],
    ) -> List[CoordinatedGroupCandidate]:
        """Return all legal same-sentence explicit coordination groups in order.

        This is intentionally an internal inspection helper.  It extracts the
        same groups and applies the same legality filters as
        :meth:`find_collective_antecedents`; it does not score, rank, or resolve
        a collective anaphor.
        """
        if not text or current_index <= 0 or current_index >= len(mentions):
            return []
        current = mentions[current_index]
        named_mentions = [
            (index, item)
            for index, item in enumerate(mentions[:current_index])
            if item.sentence_index == current.sentence_index
            and item.char_end <= current.char_start
            and not is_anaphor(item.mention, item.mention_type, item.role)
        ]
        if len(named_mentions) < 2:
            return []

        groups: List[List[tuple[int, CoreferenceMention]]] = []
        active_group: List[tuple[int, CoreferenceMention]] = []
        for item in named_mentions:
            if not active_group:
                active_group = [item]
                continue
            previous = active_group[-1][1]
            if self._has_coordinate_conjunction(text, previous, item[1]):
                active_group.append(item)
            else:
                if len(active_group) >= 2:
                    groups.append(active_group)
                active_group = [item]
        if len(active_group) >= 2:
            groups.append(active_group)

        candidates: List[CoordinatedGroupCandidate] = []
        for group in groups:
            members = [item for _, item in group]
            if not all(member.entity_id for member in members):
                continue
            normalized_types = {normalize_type(member.mention_type) for member in members}
            if len(normalized_types) != 1 or not all(
                self._is_collective_entity_type(member) for member in members
            ):
                continue
            entity_ids: List[str] = []
            seen_ids: set[str] = set()
            for member in members:
                if member.entity_id and member.entity_id not in seen_ids:
                    entity_ids.append(member.entity_id)
                    seen_ids.add(member.entity_id)
            if len(entity_ids) < 2:
                continue
            conjunctions: List[str] = []
            for (_, left), (_, right) in zip(group, group[1:]):
                between = text[left.char_end : right.char_start]
                conjunctions.extend(
                    marker
                    for marker in sorted(COORDINATE_CONJUNCTIONS, key=lambda value: (-len(value), value))
                    if marker in between
                )
            start = members[0].char_start
            end = members[-1].char_end
            candidates.append(
                CoordinatedGroupCandidate(
                    mention_indices=tuple(index for index, _ in group),
                    entity_ids=tuple(entity_ids),
                    entity_types=tuple(normalize_type(member.mention_type) for member in members),
                    source_sentence_index=current.sentence_index,
                    source_span_start=start,
                    source_span_end=end,
                    group_text=text[start:end],
                    conjunctions=tuple(conjunctions),
                    extraction_rule="explicit_same_sentence_coordination",
                    evidence=(
                        "同句、目标前、显式连接、已链接且同质的协调实体组："
                        + "、".join(member.mention for member in members)
                    ),
                )
            )
        return candidates

    def find_collective_antecedents(
        self,
        text: str,
        current_index: int,
        mentions: Sequence[CoreferenceMention],
    ) -> List[tuple[int, CoreferenceMention]]:
        """Find the nearest explicit, fully linked coordination group.

        This helper deliberately does *not* select the nearest two entities.  A
        group must be in the same sentence, connected by explicit conjunctions,
        homogeneous (all ORG or all PERSON), and contain no unlinked member.
        """
        candidates = self._collect_coordinated_group_candidates(
            text=text,
            current_index=current_index,
            mentions=mentions,
        )
        if not candidates:
            return []
        return [
            (index, mentions[index])
            for index in candidates[-1].mention_indices
        ]

    def resolve_link_results(
        self,
        results: Sequence[Dict[str, Any]],
        text: str = "",
    ) -> List[Dict[str, Any]]:
        mentions = [CoreferenceMention.from_dict(item) for item in results]
        resolutions = self.resolve(mentions, text=text)
        merged: List[Dict[str, Any]] = []
        for item, resolution in zip(results, resolutions):
            updated = dict(item)
            if item.get("is_nil", False) and not resolution.is_nil:
                updated["entity_id"] = resolution.entity_id
                updated["standard_entity"] = resolution.entity_name
                updated["confidence"] = resolution.confidence
                updated["is_nil"] = False
                updated["is_coreference"] = True
                updated["resolved_from"] = resolution.antecedent
                updated["evidence"] = resolution.evidence
                updated["method"] = "coreference_rule"
                updated["entity_ids"] = list(resolution.entity_ids)
                updated["antecedent_mentions"] = list(
                    resolution.antecedent_mentions
                )
                updated["antecedent_indices"] = list(resolution.antecedent_indices)
                updated["is_collective"] = resolution.is_collective
            updated["coreference"] = resolution.to_dict()
            merged.append(updated)
        return merged

    def _resolve_anaphor(
        self,
        index: int,
        mention: CoreferenceMention,
        active_entities: Sequence[tuple[int, CoreferenceMention]],
        all_mentions: Sequence[CoreferenceMention],
        text: str,
    ) -> CoreferenceResolution:
        if normalize_text(mention.mention) in COLLECTIVE_ANAPHORS:
            candidates = self._collect_coordinated_group_candidates(
                text=text,
                current_index=index,
                mentions=all_mentions,
            )
            antecedents = [
                (item_index, all_mentions[item_index])
                for item_index in candidates[-1].mention_indices
            ] if candidates else []
            entity_ids: List[str] = []
            seen_ids: set[str] = set()
            for _, antecedent in antecedents:
                if antecedent.entity_id and antecedent.entity_id not in seen_ids:
                    entity_ids.append(antecedent.entity_id)
                    seen_ids.add(antecedent.entity_id)
            cardinality_ok = collective_cardinality_satisfied(mention.mention, len(entity_ids))
            trace = evaluate_collective_ambiguity(
                text, mention, all_mentions, candidates, cardinality_ok
            )
            trace["ambiguity_rejection_enabled"] = self.enable_collective_ambiguity_rejection
            if self.enable_collective_ambiguity_rejection and trace["rejection_decision"]:
                return CoreferenceResolution(
                    mention=mention.mention, entity_id=None, entity_name="", antecedent=None,
                    antecedent_index=None, confidence=0.0,
                    evidence="集合协调组存在强歧义，实验分支输出 NIL",
                    rule="collective_ambiguity_rejection_experimental", is_nil=True,
                    is_collective=True, debug_metadata=trace,
                )
            if cardinality_ok:
                antecedent_mentions = [antecedent.mention for _, antecedent in antecedents]
                antecedent_indices = [antecedent_index for antecedent_index, _ in antecedents]
                return CoreferenceResolution(
                    mention=mention.mention,
                    entity_id=None,
                    entity_name="",
                    antecedent=None,
                    antecedent_index=None,
                    confidence=0.9,
                    evidence=(
                        f"{mention.mention}回指由显式并列连接词连接的"
                        f"{len(entity_ids)}个已链接实体：{'、'.join(antecedent_mentions)}"
                    ),
                    rule="collective_coordinated_antecedents",
                    is_nil=False,
                    entity_ids=entity_ids,
                    antecedent_mentions=antecedent_mentions,
                    antecedent_indices=antecedent_indices,
                    is_collective=True,
                    debug_metadata=trace if self.enable_collective_ambiguity_rejection else {},
                )
            required = (
                "恰好2个"
                if normalize_text(mention.mention) in EXACT_TWO_COLLECTIVE_ANAPHORS
                else "恰好3个"
                if normalize_text(mention.mention) in EXACT_THREE_COLLECTIVE_ANAPHORS
                else "至少2个"
            )
            return CoreferenceResolution(
                mention=mention.mention,
                entity_id=None,
                entity_name="",
                antecedent=None,
                antecedent_index=None,
                confidence=0.0,
                evidence=(
                    f"未找到满足{required}唯一实体数量、由显式并列结构连接的"
                    "已链接集合前件"
                ),
                rule="collective_unresolved",
                is_nil=True,
                is_collective=True,
                debug_metadata=trace if self.enable_collective_ambiguity_rejection else {},
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
