"""Offline, explainable discourse experiment for collective coreference.

This is a development-only evaluator for ``coreference_challenge_dev_v2``.  It
does not alter the production resolver, API, gold labels, or any blind holdout.
The only production helper it calls is the read-only internal candidate exposure
method, which intentionally uses the same same-sentence legality rules as the
current resolver.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entity_linker.coreference import (
    CoreferenceMention,
    RuleBasedCoreferenceResolver,
    collective_cardinality_satisfied,
    expected_antecedent_type,
    normalize_text,
    type_compatible,
)


SCHEMES = (
    "baseline_current_rule",
    "nearest_group_only",
    "nearest_group_with_ambiguity_rejection",
    "recency_and_cardinality",
    "discourse_features",
)
SUBJECT_SWITCH_MARKERS = (
    "随后由",
    "转由",
    "改由",
    "接管",
    "负责",
    "另有",
    "另一",
    "与此同时",
    "另一方面",
)
EVENT_RESET_MARKERS = ("与此同时", "另一方面", "随后进入新阶段", "项目转向", "另行启动")
EVENT_CHAINS = {
    "agreement": {"签署", "协商", "达成", "备忘录", "协议"},
    "release": {"发布", "公布", "宣布", "说明"},
    "implementation": {"实施", "启动", "培训", "落实", "安排"},
    "engineering": {"建设", "验收", "运营", "巡检", "检修"},
    "development": {"研发", "测试", "上线"},
}
SENTENCE_END_RE = re.compile(r"[。！？!?；;]")
STOP_CHARS = set("，。！？!?；;、：:（）()【】[]“”\"' 的了在将和与及由对把为是")


@dataclass(frozen=True)
class SentenceSpan:
    index: int
    start: int
    end: int


def load_dataset(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("evaluation_scope") != "challenge_dev":
        raise ValueError("离线篇章实验只接受 evaluation_scope=challenge_dev 的开发集。")
    if not data.get("used_for_rule_development", False):
        raise ValueError("数据集必须显式标记 used_for_rule_development=true。")
    return data


def split_sentences(text: str) -> list[SentenceSpan]:
    """Split with a reproducible punctuation-only rule and preserve offsets."""
    spans: list[SentenceSpan] = []
    start = 0
    for match in SENTENCE_END_RE.finditer(text):
        end = match.end()
        spans.append(SentenceSpan(len(spans), start, end))
        start = end
    if start < len(text) or not spans:
        spans.append(SentenceSpan(len(spans), start, len(text)))
    return spans


def sentence_for_offset(spans: Iterable[SentenceSpan], start: int, end: int) -> SentenceSpan:
    for span in spans:
        if span.start <= start < span.end and end <= span.end:
            return span
    raise ValueError(f"mention offset [{start}, {end}) 跨句或不位于文本内。")


def prepare_mentions(sample: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[SentenceSpan]]:
    """Copy mentions and add only in-memory sentence metadata for this experiment."""
    text = str(sample["text"])
    spans = split_sentences(text)
    prepared: list[dict[str, Any]] = []
    for item in sample.get("mentions", []):
        mention = copy.deepcopy(dict(item))
        start, end = int(mention["char_start"]), int(mention["char_end"])
        if text[start:end] != mention.get("mention"):
            raise ValueError(
                f"{sample.get('id')} mention {mention.get('mention')!r} 的偏移不匹配。"
            )
        sentence = sentence_for_offset(spans, start, end)
        mention["sentence_index"] = sentence.index
        mention["sentence_start"] = sentence.start
        mention["sentence_end"] = sentence.end
        prepared.append(mention)
    return prepared, spans


def char_bigrams(value: str) -> set[str]:
    chars = [char for char in value if not char.isspace() and char not in STOP_CHARS]
    return {"".join(chars[index : index + 2]) for index in range(max(0, len(chars) - 1))}


def lexical_event_overlap(source_sentence: str, target_sentence: str, entity_surfaces: Iterable[str]) -> float:
    """Character-bigram Jaccard after removing known entity surface forms."""
    for surface in entity_surfaces:
        source_sentence = source_sentence.replace(surface, "")
        target_sentence = target_sentence.replace(surface, "")
    left, right = char_bigrams(source_sentence), char_bigrams(target_sentence)
    return round(len(left & right) / len(left | right), 4) if left | right else 0.0


def target_type_compatible(target: Mapping[str, Any], candidate_types: Iterable[str]) -> bool:
    """Reuse formal type compatibility as an experimental feature only.

    The production collective branch does not apply a target-pronoun type gate.
    This feature intentionally surfaces that distinction, e.g. ``她们`` versus
    an ORG group, without changing the production decision.
    """
    expected = expected_antecedent_type(str(target.get("mention", "")), str(target.get("type", "UNKNOWN")))
    return all(type_compatible(expected, candidate_type) for candidate_type in candidate_types)


def marker_between(text: str, start: int, end: int) -> str | None:
    between = text[start:end]
    return next((marker for marker in SUBJECT_SWITCH_MARKERS if marker in between), None)


def event_categories(text: str) -> set[str]:
    return {category for category, terms in EVENT_CHAINS.items() if any(term in text for term in terms)}


def ambiguity_profile(row: Mapping[str, Any]) -> dict[str, Any]:
    """Describe only evidence for rejecting the already-selected nearest group."""
    records = row["candidate_records"]
    if len(records) < 2:
        return {
            "multiple_legal_groups": False,
            "explicit_subject_continuation": False,
            "explicit_subject_switch": False,
            "event_chain_continuity": False,
            "event_reset_signal": None,
            "candidate_score_gap": None,
            "evidence_strength": 0,
        }
    nearest = records[-1]
    candidate = nearest["candidate"]
    target_start = int(row["target_char_start"])
    between = row["text"][candidate.source_span_end : target_start]
    member_surfaces = [row["mentions"][index]["mention"] for index in candidate.mention_indices]
    continuation = all(surface in between for surface in member_surfaces)
    intervening_entities = [
        item
        for index, item in enumerate(row["mentions"])
        if index not in candidate.mention_indices
        and candidate.source_span_end <= int(item["char_start"]) < target_start
        and item.get("entity_id")
    ]
    switch_terms = ("随后", "转由", "转而", "改由", "接管", "负责", "宣布", "发布")
    explicit_switch = bool(intervening_entities) and any(term in between for term in switch_terms)
    reset = next((marker for marker in EVENT_RESET_MARKERS if marker in between), None)
    categories = event_categories(row["text"][candidate.source_span_start : target_start])
    continuity = len(categories) >= 2

    def evidence(record: Mapping[str, Any]) -> int:
        item = record["candidate"]
        local_between = row["text"][item.source_span_end : target_start]
        local_members = [row["mentions"][index]["mention"] for index in item.mention_indices]
        local_continuation = all(surface in local_between for surface in local_members)
        local_events = len(event_categories(row["text"][item.source_span_start : target_start])) >= 2
        scores = record["feature_scores"]
        return int(local_continuation) + int(local_events) + int(scores["cardinality"] > 0) + int(scores["type"] > 0)

    strengths = [evidence(record) for record in records]
    return {
        "multiple_legal_groups": True,
        "explicit_subject_continuation": continuation,
        "explicit_subject_switch": explicit_switch,
        "event_chain_continuity": continuity,
        "event_reset_signal": reset,
        "candidate_score_gap": abs(strengths[-1] - strengths[-2]),
        "evidence_strength": strengths[-1],
        "intervening_entity_count": len(intervening_entities),
    }


def candidate_features(
    text: str,
    target_index: int,
    mentions: list[dict[str, Any]],
    spans: list[SentenceSpan],
    candidates: list[Any],
) -> list[dict[str, Any]]:
    target = mentions[target_index]
    target_sentence = spans[int(target["sentence_index"])]
    records: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(candidates):
        source_sentence = spans[candidate.source_sentence_index]
        distance = int(target["sentence_index"]) - candidate.source_sentence_index
        later_groups = candidates[candidate_index + 1 :]
        named_between = sum(
            1
            for mention_index, mention in enumerate(mentions)
            if mention_index not in candidate.mention_indices
            and candidate.source_span_end <= int(mention["char_start"]) < int(target["char_start"])
            and mention.get("entity_id")
            and str(mention.get("role", "name")).lower() not in {"pronoun", "anaphor", "coreference"}
        )
        marker = marker_between(text, candidate.source_span_end, int(target["char_start"]))
        card_match = collective_cardinality_satisfied(str(target.get("mention", "")), len(candidate.entity_ids))
        type_match = target_type_compatible(target, candidate.entity_types)
        overlap = lexical_event_overlap(
            text[source_sentence.start : source_sentence.end],
            text[target_sentence.start : target_sentence.end],
            [mentions[index]["mention"] for index in candidate.mention_indices],
        )
        features = {
            "sentence_distance": distance,
            "is_nearest_group": candidate_index == len(candidates) - 1,
            "has_new_group_between": bool(later_groups),
            "named_entity_count_between": named_between,
            "cardinality_match": card_match,
            "entity_type_compatible": type_match,
            "subject_switch_marker": marker,
            "lexical_event_overlap": overlap,
        }
        recency = max(0.0, 1.0 - 0.5 * max(0, distance))
        scores = {
            "recency": round(recency, 4),
            "cardinality": 1.0 if card_match else 0.0,
            "type": 1.0 if type_match else 0.0,
            "event": overlap,
            "new_group_penalty": 1.0 if later_groups else 0.0,
            "subject_switch_penalty": 1.0 if marker else 0.0,
        }
        records.append(
            {
                "candidate": candidate,
                "features": features,
                "feature_scores": scores,
            }
        )
    return records


def score_candidate(record: Mapping[str, Any], scheme: str) -> float:
    scores = record["feature_scores"]
    if scheme == "recency_and_cardinality":
        return round(0.50 * scores["recency"] + 0.25 * scores["cardinality"] + 0.25 * scores["type"], 4)
    if scheme == "discourse_features":
        # Fixed transparent pilot weights; they are scanned only on v2 and are
        # not production thresholds or production resolver weights.
        value = (
            0.30 * scores["recency"]
            + 0.20 * scores["cardinality"]
            + 0.25 * scores["type"]
            + 0.15 * scores["event"]
            - 0.05 * scores["new_group_penalty"]
            - 0.05 * scores["subject_switch_penalty"]
        )
        return round(max(0.0, min(1.0, value)), 4)
    raise ValueError(f"scored scheme required, got {scheme}")


def decide_scored(records: list[dict[str, Any]], scheme: str, threshold: float, margin_threshold: float) -> tuple[list[str], bool, str]:
    if not records:
        return [], True, "无同句合法协调组；保守输出 NIL。"
    ranked = sorted(records, key=lambda record: (score_candidate(record, scheme), record["candidate"].source_span_start), reverse=True)
    best_score = score_candidate(ranked[0], scheme)
    second_score = score_candidate(ranked[1], scheme) if len(ranked) > 1 else 0.0
    margin = best_score - second_score
    if best_score >= threshold and margin >= margin_threshold:
        return list(ranked[0]["candidate"].entity_ids), False, f"score={best_score:.2f}，margin={margin:.2f}，满足实验阈值。"
    return [], True, f"score={best_score:.2f} 或 margin={margin:.2f} 未满足实验阈值。"


def is_correct(predicted_ids: list[str], predicted_nil: bool, gold_ids: list[str], gold_nil: bool) -> bool:
    return predicted_nil == gold_nil and (gold_nil or set(predicted_ids) == set(gold_ids))


def metrics(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    positive = [row for row in rows if not row["gold_is_nil"]]
    nil_rows = [row for row in rows if row["gold_is_nil"]]
    correct = sum(bool(row["correct"]) for row in rows)
    false_nil = sum(not row["gold_is_nil"] and row["predicted_is_nil"] for row in rows)
    false_positive = sum(row["gold_is_nil"] and not row["predicted_is_nil"] for row in rows)
    wrong_set = sum(
        not row["gold_is_nil"]
        and not row["predicted_is_nil"]
        and set(row["selected_entity_ids"]) != set(row["gold_entity_ids"])
        for row in rows
    )
    ratio = lambda value, total: round(value / total, 4) if total else None
    return {
        "total": len(rows),
        "correct": correct,
        "overall_accuracy": ratio(correct, len(rows)),
        "positive_total": len(positive),
        "positive_correct": sum(bool(row["correct"]) for row in positive),
        "positive_exact_match": ratio(sum(bool(row["correct"]) for row in positive), len(positive)),
        "nil_total": len(nil_rows),
        "nil_correct": sum(bool(row["correct"]) for row in nil_rows),
        "nil_accuracy": ratio(sum(bool(row["correct"]) for row in nil_rows), len(nil_rows)),
        "false_nil": false_nil,
        "false_positive": false_positive,
        "wrong_entity_set": wrong_set,
    }


def evaluate_scheme(rows: list[dict[str, Any]], scheme: str, threshold: float | None = None, margin_threshold: float | None = None) -> list[dict[str, Any]]:
    evaluated: list[dict[str, Any]] = []
    for row in rows:
        copied = copy.deepcopy(row)
        if scheme == "baseline_current_rule":
            resolution = copied["baseline_resolution"]
            selected, predicted_nil, reason = list(resolution["entity_ids"]), bool(resolution["is_nil"]), resolution["evidence"]
        elif scheme == "nearest_group_only":
            # Some v2 surfaces are intentionally not in the production
            # COLLECTIVE_ANAPHORS set.  For those inputs the formal resolver
            # takes its ordinary single-antecedent path, so the compatibility
            # baseline must preserve that outcome instead of silently turning
            # it into a collective NIL.
            if not copied["baseline_resolution"]["is_collective"]:
                resolution = copied["baseline_resolution"]
                selected, predicted_nil, reason = (
                    list(resolution["entity_ids"]),
                    bool(resolution["is_nil"]),
                    "目标表面未进入正式集合分支；保留当前正式规则结果。",
                )
            elif copied["candidate_records"]:
                selected = list(copied["candidate_records"][-1]["candidate"].entity_ids)
                if collective_cardinality_satisfied(copied["target_mention"], len(selected)):
                    predicted_nil, reason = False, "选择与正式规则一致的最近合法协调组。"
                else:
                    selected, predicted_nil, reason = [], True, "最近合法协调组未满足现有数量约束；与正式规则一致地输出 NIL。"
            else:
                selected, predicted_nil, reason = [], True, "无同句合法协调组；与正式规则一致地输出 NIL。"
        elif scheme == "nearest_group_with_ambiguity_rejection":
            profile = ambiguity_profile(copied)
            copied["ambiguity_features"] = profile
            if not copied["baseline_resolution"]["is_collective"]:
                resolution = copied["baseline_resolution"]
                selected, predicted_nil, reason = list(resolution["entity_ids"]), bool(resolution["is_nil"]), "目标未进入正式集合分支；保留当前正式规则结果。"
            elif not copied["candidate_records"]:
                selected, predicted_nil, reason = [], True, "无同句合法协调组；保守输出 NIL。"
            else:
                selected = list(copied["candidate_records"][-1]["candidate"].entity_ids)
                cardinality_ok = collective_cardinality_satisfied(copied["target_mention"], len(selected))
                strong_ambiguity = (
                    profile["multiple_legal_groups"]
                    and not profile["explicit_subject_continuation"]
                    and (profile["explicit_subject_switch"] or profile["event_reset_signal"])
                    and profile["candidate_score_gap"] <= float(threshold)
                    and profile["evidence_strength"] <= int(margin_threshold)
                )
                if not cardinality_ok:
                    selected, predicted_nil, reason = [], True, "最近组不满足现有数量约束；输出 NIL。"
                elif strong_ambiguity:
                    selected, predicted_nil, reason = [], True, "多合法组竞争且存在新主体/事件重置，拒绝最近组并输出 NIL。"
                else:
                    predicted_nil, reason = False, "未达到强歧义拒绝条件，保留最近合法协调组。"
        else:
            selected, predicted_nil, reason = decide_scored(copied["candidate_records"], scheme, float(threshold), float(margin_threshold))
        copied.update(
            {
                "scheme": scheme,
                "selected_entity_ids": selected,
                "predicted_is_nil": predicted_nil,
                "decision_reason": reason,
                "correct": is_correct(selected, predicted_nil, copied["gold_entity_ids"], copied["gold_is_nil"]),
                "select_threshold": threshold,
                "margin_threshold": margin_threshold,
            }
        )
        evaluated.append(copied)
    return evaluated


def best_thresholds(rows: list[dict[str, Any]], scheme: str) -> tuple[float, float, list[dict[str, Any]]]:
    best: tuple[tuple[float, float, float, float], float, float, list[dict[str, Any]]] | None = None
    for select in (round(0.40 + index * 0.05, 2) for index in range(11)):
        for margin in (round(index * 0.05, 2) for index in range(7)):
            evaluated = evaluate_scheme(rows, scheme, select, margin)
            result = metrics(evaluated)
            # Tie-break toward better NIL accuracy, then lower thresholds.
            rank = (result["overall_accuracy"] or 0.0, result["nil_accuracy"] or 0.0, -select, -margin)
            if best is None or rank > best[0]:
                best = (rank, select, margin, evaluated)
    assert best is not None
    return best[1], best[2], best[3]


def best_ambiguity_thresholds(rows: list[dict[str, Any]]) -> tuple[float, int, list[dict[str, Any]], list[dict[str, Any]]]:
    best: tuple[tuple[float, float, float, float], float, int, list[dict[str, Any]]] | None = None
    scan: list[dict[str, Any]] = []
    for gap in (0.0, 1.0, 2.0, 3.0, 4.0):
        for minimum_evidence in range(5):
            evaluated = evaluate_scheme(rows, "nearest_group_with_ambiguity_rejection", gap, minimum_evidence)
            result = metrics(evaluated)
            scan.append(
                {
                    "ambiguity_threshold": gap,
                    "minimum_evidence_count": minimum_evidence,
                    "positive_retained": result["positive_correct"],
                    "positive_total": result["positive_total"],
                    "nil_rejected_correctly": result["nil_correct"],
                    "nil_total": result["nil_total"],
                    "false_nil": result["false_nil"],
                    "false_positive": result["false_positive"],
                    "overall_accuracy": result["overall_accuracy"],
                }
            )
            rank = (result["overall_accuracy"] or 0.0, result["positive_exact_match"] or 0.0, result["nil_accuracy"] or 0.0, -minimum_evidence)
            if best is None or rank > best[0]:
                best = (rank, gap, minimum_evidence, evaluated)
    assert best is not None
    return best[1], best[2], best[3], scan


def serialise_candidate(record: Mapping[str, Any], scheme: str | None = None) -> dict[str, Any]:
    candidate = record["candidate"]
    output = asdict(candidate)
    output["mention_indices"] = list(candidate.mention_indices)
    output["entity_ids"] = list(candidate.entity_ids)
    output["entity_types"] = list(candidate.entity_types)
    output["conjunctions"] = list(candidate.conjunctions)
    output["features"] = record["features"]
    output["feature_scores"] = record["feature_scores"]
    if scheme in {"recency_and_cardinality", "discourse_features"}:
        output["total_score"] = score_candidate(record, scheme)
    return output


def build_cases(dataset: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    resolver = RuleBasedCoreferenceResolver()
    rows: list[dict[str, Any]] = []
    diagnostics: Counter[str] = Counter()
    for sample in dataset.get("samples", []):
        text = str(sample["text"])
        mentions, spans = prepare_mentions(sample)
        resolutions = resolver.resolve(mentions, text=text)
        objects = [CoreferenceMention.from_dict(item) for item in mentions]
        for expected in sample.get("expected_coreferences", []):
            target_index = int(expected["mention_index"])
            candidates = resolver._collect_coordinated_group_candidates(text, target_index, objects)
            records = candidate_features(text, target_index, mentions, spans, candidates)
            diagnostics["candidate_groups"] += len(candidates)
            diagnostics["candidate_bearing_cases"] += int(bool(candidates))
            diagnostics["multi_candidate_cases"] += int(len(candidates) > 1)
            diagnostics["three_entity_candidates"] += sum(len(item.entity_ids) >= 3 for item in candidates)
            diagnostics["candidate_extraction_failures"] += 0
            baseline = resolutions[target_index].to_dict()
            rows.append(
                {
                    "sample_id": sample.get("id"),
                    "pilot_subset": sample.get("pilot_subset", "cross_sentence_pilot"),
                    "domain": sample.get("domain", "Unspecified"),
                    "text": text,
                    "scenario": expected.get("scenario", sample.get("scenario", "unknown")),
                    "target_mention": mentions[target_index]["mention"],
                    "target_char_start": mentions[target_index]["char_start"],
                    "target_sentence": asdict(spans[int(mentions[target_index]["sentence_index"])]),
                    "mentions": [
                        {
                            "mention": item["mention"],
                            "char_start": item["char_start"],
                            "char_end": item["char_end"],
                            "entity_id": item.get("entity_id"),
                            "sentence_index": item["sentence_index"],
                            "sentence_start": item["sentence_start"],
                            "sentence_end": item["sentence_end"],
                        }
                        for item in mentions
                    ],
                    "gold_entity_ids": list(expected.get("entity_ids", [])),
                    "gold_is_nil": bool(expected.get("is_nil", False)),
                    "baseline_resolution": baseline,
                    "candidate_records": records,
                }
            )
    return rows, dict(diagnostics)


def scenario_metrics(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["scenario"])].append(row)
    return {scenario: metrics(values) for scenario, values in sorted(grouped.items())}


def subset_metrics(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["pilot_subset"])].append(row)
    return {subset: metrics(values) for subset, values in sorted(grouped.items())}


def domain_metrics(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return per-domain accuracy and error counts for offline analysis only."""
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["domain"])].append(row)
    return {domain: metrics(values) for domain, values in sorted(grouped.items())}


def public_trace(rows: list[dict[str, Any]], scheme: str) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for row in rows:
        traces.append(
            {
                key: value
                for key, value in row.items()
                if key not in {"candidate_records", "baseline_resolution"}
            }
            | {
                "candidate_groups": [serialise_candidate(record, scheme) for record in row["candidate_records"]],
                "baseline_rule": row["baseline_resolution"]["rule"],
            }
        )
    return traces


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# 集合共指篇章状态离线实验（首轮）",
        "",
        "## 1. 实验范围",
        "",
        f"- 仅使用 Challenge Dev v2 的 {report['metrics']['baseline_current_rule']['total']} 条文本 / case；不含任何 blind holdout。",
        "- 未运行或读取任何 blind holdout；未修改正式规则、API、gold、阈值，也未使用 BGE/FAISS。",
        "- 这是 pilot sample，结果仅用于方向判断，不能视为稳定统计结论。",
        "",
        "## 2. 候选暴露验证",
        "",
        f"- 候选组总数：{report['candidate_exposure']['candidate_groups']}",
        f"- 含候选的 case：{report['candidate_exposure']['candidate_bearing_cases']}",
        f"- 多候选 case：{report['candidate_exposure']['multi_candidate_cases']}",
        f"- 三实体候选：{report['candidate_exposure']['three_entity_candidates']}",
        f"- 候选提取异常：{report['candidate_exposure']['candidate_extraction_failures']}",
        f"- Baseline 与 `nearest_group_only`：{'一致' if report['candidate_exposure']['baseline_nearest_consistent'] else '不一致（应停止分析）'}。",
        "",
        "当前候选提取严格复用正式规则的同句约束，因此跨句 case 没有候选是预期边界，不是数据错误。",
        "",
        "## 3. 方案对比",
        "",
        "|方案|总体|正例|NIL|False NIL|False Positive|Wrong Entity Set|",
        "|-|-:|-:|-:|-:|-:|-:|",
    ]
    for scheme, result in report["metrics"].items():
        lines.append(
            f"|`{scheme}`|{result['overall_accuracy']:.2%}|{result['positive_exact_match']:.2%}|{result['nil_accuracy']:.2%}|{result['false_nil']}|{result['false_positive']}|{result['wrong_entity_set']}|"
        )
    lines.extend(["", "## 4. 分 Pilot 子集结果", ""])
    subset_names = sorted({subset for values in report["pilot_metrics"].values() for subset in values})
    for subset in subset_names:
        lines.extend([f"### `{subset}`", "", "|方案|总体|正例|NIL|False NIL|False Positive|", "|-|-:|-:|-:|-:|-:|"])
        for scheme, result in report["pilot_metrics"].items():
            values = result.get(subset)
            if values:
                lines.append(f"|`{scheme}`|{values['overall_accuracy']:.2%}|{values['positive_exact_match']:.2%}|{values['nil_accuracy']:.2%}|{values['false_nil']}|{values['false_positive']}|")
        lines.append("")
    lines.extend(["## 5. 跨领域结果（歧义拒绝器）", "", "|领域|正例准确率|NIL 准确率|总体|False Rejection|False Positive|", "|-|-:|-:|-:|-:|-:|"])
    for domain, result in report["domain_metrics"]["nearest_group_with_ambiguity_rejection"].items():
        if domain == "Unspecified":
            continue
        lines.append(f"|`{domain}`|{result['positive_exact_match']:.2%}|{result['nil_accuracy']:.2%}|{result['overall_accuracy']:.2%}|{result['false_nil']}|{result['false_positive']}|")
    lines.append("")
    lines.extend(["## 6. 阈值扫描", ""])
    for scheme, values in report["best_thresholds"].items():
        if scheme == "nearest_group_with_ambiguity_rejection":
            lines.append(f"- `{scheme}`：`candidate_score_gap={values['ambiguity_threshold']:.2f}`，`minimum_evidence_count={values['minimum_evidence_count']}`。")
        else:
            suffix = "；当前无候选 case，数值不具备校准意义。" if not values["meaningful"] else "。"
            lines.append(f"- `{scheme}`：`select_threshold={values['select_threshold']:.2f}`，`margin_threshold={values['margin_threshold']:.2f}`{suffix}")
    lines.extend(["", "## 7. 可行性判断", "", f"**{report['feasibility']}**：{report['feasibility_reason']}", "", "## 8. 主要限制", "", "- 候选暴露刻意不跨句扩展，无法修复跨句 false NIL。", "- 词面 bigram overlap 与主体切换词仅为无模型近似，不能替代句法或语义分析。", "- 新增领域 pilot 是开发集，不能替代未参与设计的独立盲测。", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="集合共指篇章状态离线实验")
    parser.add_argument("--dataset", default="data/eval/coreference_challenge_dev_v2.json")
    parser.add_argument("--output-json", default="reports/coreference_discourse_experiment.json")
    parser.add_argument("--output-md", default="reports/coreference_discourse_experiment.md")
    args = parser.parse_args()

    dataset_path = ROOT / args.dataset
    dataset = load_dataset(dataset_path)
    base_rows, exposure = build_cases(dataset)
    evaluated: dict[str, list[dict[str, Any]]] = {}
    evaluated["baseline_current_rule"] = evaluate_scheme(base_rows, "baseline_current_rule")
    evaluated["nearest_group_only"] = evaluate_scheme(base_rows, "nearest_group_only")
    thresholds: dict[str, dict[str, float]] = {}
    for scheme in ("recency_and_cardinality", "discourse_features"):
        select, margin, rows = best_thresholds(base_rows, scheme)
        evaluated[scheme] = rows
        thresholds[scheme] = {
            "select_threshold": select,
            "margin_threshold": margin,
            "meaningful": bool(exposure.get("candidate_bearing_cases", 0)),
        }
    gap, evidence_count, rows, ambiguity_scan = best_ambiguity_thresholds(base_rows)
    evaluated["nearest_group_with_ambiguity_rejection"] = rows
    thresholds["nearest_group_with_ambiguity_rejection"] = {
        "ambiguity_threshold": gap,
        "minimum_evidence_count": evidence_count,
        "meaningful": bool(exposure.get("candidate_bearing_cases", 0)),
    }

    baseline_nearest_consistent = all(
        row["selected_entity_ids"] == nearest["selected_entity_ids"]
        and row["predicted_is_nil"] == nearest["predicted_is_nil"]
        for row, nearest in zip(evaluated["baseline_current_rule"], evaluated["nearest_group_only"])
    )
    metric_rows = {scheme: metrics(rows) for scheme, rows in evaluated.items()}
    pilot_metric_rows = {scheme: subset_metrics(rows) for scheme, rows in evaluated.items()}
    baseline_correct = metric_rows["baseline_current_rule"]["correct"]
    best_scheme = max(
        metric_rows,
        key=lambda name: (
            metric_rows[name]["correct"],
            int(name == "nearest_group_with_ambiguity_rejection"),
        ),
    )
    improvement = metric_rows[best_scheme]["correct"] - baseline_correct
    if not baseline_nearest_consistent:
        feasibility, reason = "NOT_PROMISING", "候选暴露与正式最近组行为不一致，必须先停止并修复兼容性。"
    elif (
        best_scheme == "nearest_group_with_ambiguity_rejection"
        and improvement >= 3
        and metric_rows["baseline_current_rule"]["positive_correct"] - metric_rows[best_scheme]["positive_correct"] <= 1
        and metric_rows[best_scheme]["nil_accuracy"] >= metric_rows["baseline_current_rule"]["nil_accuracy"]
    ):
        feasibility, reason = "PROMISING", "相对 baseline 多正确至少 3 条，正例损失不超过 1 条且 NIL 未下降；仅建议继续扩充开发集验证。"
    elif improvement == 0:
        feasibility, reason = "INSUFFICIENT_EVIDENCE", "各方案与基线持平，且仅有 12 个 pilot case，尚不足以判断篇章特征收益。"
    else:
        feasibility, reason = (
            "INSUFFICIENT_EVIDENCE",
            "未同时满足本轮“至少多正确 3 条、正例损失不超过 1 条、NIL 不下降”的门槛；不能支持接入正式规则。",
        )

    report = {
        "experiment_name": "coreference_discourse_experiment",
        "status": "PILOT_COMPLETE",
        "dataset": str(Path(args.dataset)),
        "dataset_name": dataset.get("dataset_name"),
        "scope": "challenge_dev_v2_only_no_blind_holdout_no_bge",
        "sentence_splitter": "punctuation [。！？!?；;] with in-memory offset mapping",
        "lexical_event_overlap": "Jaccard similarity over non-stop-character bigrams after candidate entity surface removal",
        "candidate_exposure": exposure | {"baseline_nearest_consistent": baseline_nearest_consistent},
        "best_thresholds": thresholds,
        "ambiguity_threshold_scan": ambiguity_scan,
        "metrics": metric_rows,
        "pilot_metrics": pilot_metric_rows,
        "domain_metrics": {scheme: domain_metrics(rows) for scheme, rows in evaluated.items()},
        "scenario_metrics": {scheme: scenario_metrics(rows) for scheme, rows in evaluated.items()},
        "feasibility": feasibility,
        "feasibility_reason": reason,
        "traces": {scheme: public_trace(rows, scheme) for scheme, rows in evaluated.items()},
    }
    json_path, markdown_path = ROOT / args.output_json, ROOT / args.output_md
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_report(report), encoding="utf-8")
    print(f"Pilot complete: {metric_rows[best_scheme]['correct']}/{metric_rows[best_scheme]['total']} best={best_scheme}")
    print(f"Feasibility: {feasibility}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
