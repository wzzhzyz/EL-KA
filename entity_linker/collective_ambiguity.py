"""Shared, opt-in collective ambiguity guard used by runtime and shadow tests."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Sequence

SWITCH = ("随后", "转由", "转而", "改由", "接管", "负责", "宣布", "发布")
RESET = ("与此同时", "另一方面", "项目转向", "另行启动", "转而", "改由")
FROZEN_EVIDENCE_MAX = 2


def evaluate_collective_ambiguity(
    text: str, target: Any, mentions: Sequence[Any], candidates: Sequence[Any], cardinality_ok: bool
) -> dict[str, Any]:
    """Return frozen shadow-equivalent metadata; never ranks candidates."""
    trace: dict[str, Any] = {
        "candidate_group_count": len(candidates),
        "candidate_groups": [asdict(item) for item in candidates],
        "threshold": {"max_evidence_strength": FROZEN_EVIDENCE_MAX},
        "rejection_decision": False,
        "rejection_reason": "not_applicable",
    }
    if len(candidates) < 2 or not cardinality_ok:
        return trace
    nearest = candidates[-1]
    between = text[nearest.source_span_end : target.char_start]
    surfaces = [mentions[index].mention for index in nearest.mention_indices]
    continuation = all(surface in between for surface in surfaces)
    intervening = [
        item for item in mentions
        if item.entity_id and item.char_start >= nearest.source_span_end and item.char_end <= target.char_start
        and item.mention not in surfaces and item is not target
    ]
    switch = bool(intervening) and any(term in between for term in SWITCH)
    reset = next((term for term in RESET if term in between), None)
    evidence = int(cardinality_ok) + 1 + int(continuation)
    reject = not continuation and (switch or reset is not None) and evidence <= FROZEN_EVIDENCE_MAX
    trace.update({
        "nearest_group": list(nearest.entity_ids),
        "alternative_groups": [list(item.entity_ids) for item in candidates[:-1]],
        "explicit_subject_continuation": continuation,
        "explicit_subject_switch": switch,
        "event_chain_continuity": False,
        "event_reset_signal": reset,
        "candidate_score_gap": 0,
        "evidence_strength": evidence,
        "rejection_decision": reject,
        "rejection_reason": "strong_ambiguity" if reject else "keep_nearest_group",
    })
    return trace
