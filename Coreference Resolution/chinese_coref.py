from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

ORG_ANAPHORS = {
    "该公司",
    "这家公司",
    "本公司",
    "该集团",
    "这个集团",
    "本集团",
    "该校",
    "这所学校",
    "该院",
    "该局",
    "该部门",
    "该机构",
    "该单位",
    "它",
    "它们",
}

PERSON_ANAPHORS = {
    "他",
    "她",
    "他们",
    "她们",
    "本人",
    "其本人",
    "此人",
    "该人",
}

NEUTRAL_ANAPHORS = {
    "其",
    "该项目",
    "该方案",
    "该产品",
}


def normalize_text(text: str) -> str:
    return "".join(ch for ch in text.strip() if not ch.isspace())


def entity_type_compatible(mention_type: str, entity_type: str) -> bool:
    mention_type = mention_type.upper()
    entity_type = entity_type.upper()
    if mention_type == "UNKNOWN" or entity_type == "UNKNOWN":
        return True
    if mention_type == entity_type:
        return True
    if mention_type == "ORG" and entity_type in {"ORG", "GPE", "LOC", "FAC"}:
        return True
    if mention_type == "PERSON" and entity_type == "PERSON":
        return True
    if mention_type == "LOC" and entity_type in {"LOC", "GPE"}:
        return True
    return False


@dataclass
class Mention:
    text: str
    entity_type: str = "UNKNOWN"
    sentence_index: int = 0
    mention_role: str = "name"
    linked_entity_id: Optional[str] = None
    aliases: Sequence[str] = field(default_factory=tuple)

    @property
    def normalized(self) -> str:
        return normalize_text(self.text)


@dataclass
class Resolution:
    mention_text: str
    antecedent_text: Optional[str]
    antecedent_entity_id: Optional[str]
    score: float
    rule: str
    evidence: str
    is_nil: bool


@dataclass
class EntityState:
    entity_id: Optional[str]
    canonical_text: str
    entity_type: str
    sentence_index: int
    mention_index: int
    aliases: set[str] = field(default_factory=set)

    def all_names(self) -> set[str]:
        names = {normalize_text(self.canonical_text)}
        names.update(normalize_text(alias) for alias in self.aliases)
        return names


class ChineseCoreferenceResolver:
    def __init__(self, nil_threshold: float = 0.55):
        self.nil_threshold = nil_threshold

    def resolve(self, mentions: Sequence[Mention]) -> List[Resolution]:
        active_entities: List[EntityState] = []
        results: List[Resolution] = []

        for index, mention in enumerate(mentions):
            match = self._resolve_mention(index, mention, active_entities)
            results.append(match)

            if not match.is_nil:
                self._register_mention(index, mention, active_entities, match)

        return results

    def _register_mention(
        self,
        mention_index: int,
        mention: Mention,
        active_entities: List[EntityState],
        resolution: Resolution,
    ) -> None:
        entity_id = resolution.antecedent_entity_id or mention.linked_entity_id
        if entity_id is None and mention.mention_role in {"pronoun", "anaphor"}:
            return

        state = EntityState(
            entity_id=entity_id,
            canonical_text=resolution.antecedent_text or mention.text,
            entity_type=mention.entity_type,
            sentence_index=mention.sentence_index,
            mention_index=mention_index,
            aliases={
                mention.normalized,
                *[normalize_text(alias) for alias in mention.aliases],
            },
        )
        active_entities.append(state)

    def _resolve_mention(
        self,
        mention_index: int,
        mention: Mention,
        active_entities: Sequence[EntityState],
    ) -> Resolution:
        normalized = mention.normalized
        mention_type = mention.entity_type.upper()
        role = mention.mention_role.lower()

        if role == "name" and mention.linked_entity_id:
            return Resolution(
                mention_text=mention.text,
                antecedent_text=mention.text,
                antecedent_entity_id=mention.linked_entity_id,
                score=1.0,
                rule="linked_name",
                evidence="name mention already linked before coreference",
                is_nil=False,
            )

        candidate_scores: List[tuple[float, EntityState, str]] = []
        for entity in reversed(active_entities):
            if not entity_type_compatible(mention_type, entity.entity_type):
                continue

            exact_alias = normalized in entity.all_names()
            distance = max(0, mention_index - entity.mention_index)
            sentence_gap = max(0, mention.sentence_index - entity.sentence_index)

            if exact_alias:
                score = 0.98
                rule = "alias_match"
            else:
                if not self._is_coref_candidate(mention):
                    continue
                base = 0.80 if role in {"pronoun", "anaphor"} else 0.62
                score = base - 0.08 * distance - 0.05 * sentence_gap
                if mention.sentence_index == entity.sentence_index:
                    score += 0.10
                elif sentence_gap == 1:
                    score += 0.04
                if mention_type == "ORG" and entity.entity_type.upper() == "ORG":
                    score += 0.03
                rule = "recency_and_type"

            candidate_scores.append((score, entity, rule))

        if not candidate_scores:
            return Resolution(
                mention_text=mention.text,
                antecedent_text=None,
                antecedent_entity_id=None,
                score=0.0,
                rule="no_candidate",
                evidence="no compatible antecedent in active entity stack",
                is_nil=True,
            )

        candidate_scores.sort(
            key=lambda item: (item[0], -item[1].mention_index), reverse=True
        )
        best_score, best_entity, best_rule = candidate_scores[0]
        if best_score < self.nil_threshold:
            return Resolution(
                mention_text=mention.text,
                antecedent_text=None,
                antecedent_entity_id=None,
                score=best_score,
                rule="below_threshold",
                evidence=f"best candidate {best_entity.canonical_text} scored {best_score:.2f}",
                is_nil=True,
            )

        return Resolution(
            mention_text=mention.text,
            antecedent_text=best_entity.canonical_text,
            antecedent_entity_id=best_entity.entity_id,
            score=best_score,
            rule=best_rule,
            evidence=f"matched {best_entity.canonical_text} by {best_rule}",
            is_nil=False,
        )

    @staticmethod
    def _is_coref_candidate(mention: Mention) -> bool:
        normalized = mention.normalized
        if mention.mention_role.lower() in {"pronoun", "anaphor"}:
            return True
        return (
            normalized in ORG_ANAPHORS
            or normalized in PERSON_ANAPHORS
            or normalized in NEUTRAL_ANAPHORS
        )


def render_resolutions(resolutions: Iterable[Resolution]) -> str:
    lines: List[str] = []
    for item in resolutions:
        if item.is_nil:
            target = "NIL"
        else:
            target = f"{item.antecedent_text} ({item.antecedent_entity_id or 'no-id'})"
        lines.append(
            f"{item.mention_text} -> {target} | score={item.score:.2f} | rule={item.rule} | {item.evidence}"
        )
    return "\n".join(lines)
