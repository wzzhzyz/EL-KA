#!/usr/bin/env python3
"""Evaluate local rule-based coreference resolution in detail.

This script focuses on the current local rule implementation:
`entity_linker.coreference.RuleBasedCoreferenceResolver`.

Compared with `scripts/evaluate_coreference.py`, it reports richer metrics:
- overall accuracy / NIL precision-recall-F1;
- per mention surface accuracy, e.g. 该公司/它/两家企业;
- per expected target type accuracy, e.g. ORG/PERSON/NIL;
- per resolver rule accuracy;
- coverage of anaphor categories in the dataset;
- detailed wrong cases and optional JSON report.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


COLLECTIVE_SURFACES = {
    "两家公司",
    "两家企业",
    "两家机构",
    "两家央企",
    "这些企业",
    "上述企业",
    "双方",
    "二者",
    "他们",
    "她们",
}

ORG_SURFACES = {
    "该公司",
    "这家公司",
    "本公司",
    "该集团",
    "该企业",
    "这家企业",
    "该机构",
    "该单位",
    "该平台",
    "其",
    "它",
}

SCHOOL_SURFACES = {"该校"}
REGION_SURFACES = {"该市", "该地区", "当地"}
PERSON_SURFACES = {"他", "她", "本人", "该负责人", "该专家"}


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def classify_surface(mention: Mapping[str, Any]) -> str:
    text = str(mention.get("mention", "")).strip()
    mention_type = str(mention.get("type", mention.get("mention_type", ""))).upper()
    if text in COLLECTIVE_SURFACES:
        return "COLLECTIVE"
    if text in SCHOOL_SURFACES:
        return "SCHOOL_SINGLE"
    if text in REGION_SURFACES:
        return "REGION_SINGLE"
    if text in PERSON_SURFACES or mention_type == "PERSON":
        return "PERSON_SINGLE"
    if text in ORG_SURFACES or mention_type in {"PRON", "NOUN"}:
        return "ORG_SINGLE"
    return mention_type or "UNKNOWN"


def infer_expected_target_type(
    expected: Mapping[str, Any],
    entity_type_index: Mapping[str, str],
) -> str:
    if expected.get("is_nil", expected.get("entity_id") is None):
        return "NIL"
    entity_id = expected.get("entity_id")
    if isinstance(entity_id, str) and entity_id.startswith("PER_TEST_"):
        return "PERSON"
    return entity_type_index.get(str(entity_id), "UNKNOWN")


def add_bucket(
    buckets: MutableMapping[str, Counter],
    bucket_name: str,
    key: str,
    ok: bool,
) -> None:
    buckets[bucket_name][f"{key}__total"] += 1
    if ok:
        buckets[bucket_name][f"{key}__correct"] += 1


def bucket_to_rows(counter: Counter) -> List[Dict[str, Any]]:
    keys = sorted({item.rsplit("__", 1)[0] for item in counter})
    rows: List[Dict[str, Any]] = []
    for key in keys:
        total = counter.get(f"{key}__total", 0)
        correct = counter.get(f"{key}__correct", 0)
        rows.append(
            {
                "name": key,
                "total": total,
                "correct": correct,
                "wrong": total - correct,
                "accuracy": round(safe_div(correct, total), 4),
            }
        )
    return rows


def evaluate(dataset: Dict[str, Any], kb: Dict[str, Any], nil_threshold: float) -> Dict[str, Any]:
    from entity_linker.coreference import RuleBasedCoreferenceResolver

    entity_type_index = {
        item["entity_id"]: item.get("entity_type", "UNKNOWN")
        for item in kb.get("entities", [])
        if item.get("entity_id")
    }

    resolver = RuleBasedCoreferenceResolver(nil_threshold=nil_threshold)
    cases: List[Dict[str, Any]] = []
    buckets: MutableMapping[str, Counter] = defaultdict(Counter)
    anaphor_coverage = Counter()

    total = 0
    correct = 0
    nil_tp = nil_fp = nil_fn = 0
    single_total = single_correct = 0
    collective_total = collective_correct = 0
    collective_exact_total = collective_exact_correct = 0
    collective_nil_total = collective_nil_correct = 0

    for sample in dataset.get("samples", []):
        mentions = sample.get("mentions", [])
        expected_coreferences = sample.get("expected_coreferences", [])
        # Do not reinterpret legacy NIL gold as a new collective success.
        text = sample.get("text", "") if any(
            "entity_ids" in item for item in expected_coreferences
        ) else ""
        resolutions = resolver.resolve(mentions, text=text)

        for expected in expected_coreferences:
            total += 1
            mention_index = int(expected["mention_index"])
            mention = mentions[mention_index]
            predicted = resolutions[mention_index]

            expected_id = expected.get("entity_id")
            expected_nil = bool(expected.get("is_nil", expected_id is None))
            expected_ids = list(expected.get("entity_ids", []))
            expected_collective = bool(expected.get("is_collective", False))
            predicted_id = predicted.entity_id
            predicted_nil = predicted.is_nil
            predicted_ids = list(predicted.entity_ids)
            if expected_collective:
                collective_total += 1
                if expected_nil:
                    collective_nil_total += 1
                    ok = (
                        predicted_nil
                        and predicted_id is None
                        and predicted_ids == []
                        and predicted.is_collective
                    )
                    collective_nil_correct += int(ok)
                else:
                    collective_exact_total += 1
                    ok = (
                        not predicted_nil
                        and predicted.is_collective
                        and set(predicted_ids) == set(expected_ids)
                        and len(predicted_ids) == len(set(predicted_ids))
                    )
                    collective_exact_correct += int(ok)
                collective_correct += int(ok)
            else:
                single_total += 1
                ok = (expected_nil and predicted_nil) or (
                    not expected_nil and predicted_id == expected_id
                )
                single_correct += int(ok)

            if ok:
                correct += 1

            if expected_nil and predicted_nil:
                nil_tp += 1
            elif not expected_nil and predicted_nil:
                nil_fp += 1
            elif expected_nil and not predicted_nil:
                nil_fn += 1

            surface = str(mention.get("mention", ""))
            surface_class = classify_surface(mention)
            expected_target_type = infer_expected_target_type(expected, entity_type_index)
            rule = predicted.rule

            anaphor_coverage[surface_class] += 1
            add_bucket(buckets, "by_surface", surface, ok)
            add_bucket(buckets, "by_surface_class", surface_class, ok)
            add_bucket(buckets, "by_expected_target_type", expected_target_type, ok)
            add_bucket(buckets, "by_rule", rule, ok)
            add_bucket(buckets, "by_nil_expected", "NIL" if expected_nil else "NON_NIL", ok)

            cases.append(
                {
                    "sample_id": sample.get("id"),
                    "mention_index": mention_index,
                    "mention": surface,
                    "surface_class": surface_class,
                    "expected_entity_id": expected_id,
                    "expected_entity_ids": expected_ids,
                    "expected_collective": expected_collective,
                    "expected_nil": expected_nil,
                    "expected_target_type": expected_target_type,
                    "predicted_entity_id": predicted_id,
                    "predicted_entity_ids": predicted_ids,
                    "predicted_collective": predicted.is_collective,
                    "predicted_nil": predicted_nil,
                    "predicted_antecedent": predicted.antecedent,
                    "predicted_antecedent_index": predicted.antecedent_index,
                    "confidence": predicted.confidence,
                    "rule": rule,
                    "evidence": predicted.evidence,
                    "is_correct": ok,
                }
            )

    nil_precision = safe_div(nil_tp, nil_tp + nil_fp)
    nil_recall = safe_div(nil_tp, nil_tp + nil_fn)
    nil_f1 = safe_div(2 * nil_precision * nil_recall, nil_precision + nil_recall)

    wrong_cases = [item for item in cases if not item["is_correct"]]
    return {
        "dataset_name": dataset.get("dataset_name"),
        "samples": len(dataset.get("samples", [])),
        "total_coreference_cases": total,
        "correct": correct,
        "wrong": len(wrong_cases),
        "accuracy": round(safe_div(correct, total), 4),
        "nil_metrics": {
            "tp": nil_tp,
            "fp": nil_fp,
            "fn": nil_fn,
            "precision": round(nil_precision, 4),
            "recall": round(nil_recall, 4),
            "f1": round(nil_f1, 4),
        },
        "collective_metrics": {
            "single_coreference_accuracy": round(safe_div(single_correct, single_total), 4),
            "collective_coreference_accuracy": round(safe_div(collective_correct, collective_total), 4),
            "collective_exact_match": round(safe_div(collective_exact_correct, collective_exact_total), 4),
            "collective_nil_accuracy": round(safe_div(collective_nil_correct, collective_nil_total), 4),
            "single_total": single_total,
            "collective_total": collective_total,
            "collective_exact_total": collective_exact_total,
            "collective_nil_total": collective_nil_total,
        },
        "coverage": {
            "anaphor_classes": dict(sorted(anaphor_coverage.items())),
            "unique_surfaces": sorted({item["mention"] for item in cases}),
            "unique_rules": sorted({item["rule"] for item in cases}),
        },
        "breakdown": {
            "by_surface": bucket_to_rows(buckets["by_surface"]),
            "by_surface_class": bucket_to_rows(buckets["by_surface_class"]),
            "by_expected_target_type": bucket_to_rows(buckets["by_expected_target_type"]),
            "by_rule": bucket_to_rows(buckets["by_rule"]),
            "by_nil_expected": bucket_to_rows(buckets["by_nil_expected"]),
        },
        "cases": cases,
        "wrong_cases": wrong_cases,
    }


def print_table(title: str, rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    print(f"\n{title}")
    if not rows:
        print("  (none)")
        return
    print("  name | total | correct | wrong | accuracy")
    for row in rows:
        print(
            "  "
            f"{row['name']} | {row['total']} | {row['correct']} | "
            f"{row['wrong']} | {row['accuracy']:.4f}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate local rule-based coreference in detail.")
    parser.add_argument(
        "--dataset",
        default="data/eval/coreference_long_text_test.json",
        help="Coreference evaluation dataset.",
    )
    parser.add_argument(
        "--kb",
        default="data/kb/energy_entities.json",
        help="Knowledge base JSON path.",
    )
    parser.add_argument(
        "--output",
        default="reports/coreference_rule_eval_detailed.json",
        help="Detailed JSON report output path.",
    )
    parser.add_argument("--nil-threshold", type=float, default=0.55)
    parser.add_argument("--fail-on-wrong", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    dataset = load_json(ROOT / args.dataset)
    kb = load_json(ROOT / args.kb)
    report = evaluate(dataset, kb, args.nil_threshold)

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Local Rule-Based Coreference Evaluation")
    print(f"  dataset: {report['dataset_name']}")
    print(f"  samples: {report['samples']}")
    print(f"  total_cases: {report['total_coreference_cases']}")
    print(f"  correct: {report['correct']}")
    print(f"  wrong: {report['wrong']}")
    print(f"  accuracy: {report['accuracy']:.4f}")
    nil = report["nil_metrics"]
    print(
        "  NIL precision/recall/f1: "
        f"{nil['precision']:.4f}/{nil['recall']:.4f}/{nil['f1']:.4f}"
    )
    print(f"  collective_metrics: {report['collective_metrics']}")
    print(f"  output: {output_path}")

    print_table("By surface class", report["breakdown"]["by_surface_class"])
    print_table("By expected target type", report["breakdown"]["by_expected_target_type"])
    print_table("By resolver rule", report["breakdown"]["by_rule"])
    print_table("By mention surface", report["breakdown"]["by_surface"])

    if report["wrong_cases"]:
        print("\nWrong cases")
        for item in report["wrong_cases"]:
            print(
                "  - "
                f"{item['sample_id']}#{item['mention_index']} {item['mention']}: "
                f"expected={item['expected_entity_id']} nil={item['expected_nil']} "
                f"predicted={item['predicted_entity_id']} nil={item['predicted_nil']} "
                f"rule={item['rule']}"
            )

    return 1 if args.fail_on_wrong and report["wrong_cases"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
