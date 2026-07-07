#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(dataset: Dict[str, Any]) -> Dict[str, Any]:
    from entity_linker.coreference import RuleBasedCoreferenceResolver

    resolver = RuleBasedCoreferenceResolver(nil_threshold=0.55)
    cases: List[Dict[str, Any]] = []
    total = 0
    correct = 0

    for sample in dataset.get("samples", []):
        mentions = sample.get("mentions", [])
        resolutions = resolver.resolve(mentions)
        for expected in sample.get("expected_coreferences", []):
            total += 1
            mention_index = int(expected["mention_index"])
            predicted = resolutions[mention_index]
            expected_id = expected.get("entity_id")
            expected_nil = bool(expected.get("is_nil", expected_id is None))
            predicted_id = predicted.entity_id
            predicted_nil = predicted.is_nil
            ok = (
                (expected_nil and predicted_nil)
                or (not expected_nil and predicted_id == expected_id)
            )
            if ok:
                correct += 1
            cases.append(
                {
                    "sample_id": sample.get("id"),
                    "mention_index": mention_index,
                    "mention": mentions[mention_index].get("mention"),
                    "expected_entity_id": expected_id,
                    "expected_nil": expected_nil,
                    "predicted_entity_id": predicted_id,
                    "predicted_nil": predicted_nil,
                    "confidence": predicted.confidence,
                    "rule": predicted.rule,
                    "evidence": predicted.evidence,
                    "is_correct": ok,
                }
            )

    wrong_cases = [item for item in cases if not item["is_correct"]]
    return {
        "dataset_name": dataset.get("dataset_name"),
        "samples": len(dataset.get("samples", [])),
        "total_coreference_cases": total,
        "correct": correct,
        "wrong": len(wrong_cases),
        "accuracy": correct / total if total else 0.0,
        "cases": cases,
        "wrong_cases": wrong_cases,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default="data/eval/coreference_long_text_test.json",
        help="Coreference long-text evaluation dataset.",
    )
    parser.add_argument(
        "--output",
        default="reports/coreference_eval_summary.json",
        help="Path to write detailed evaluation results.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    dataset = load_json(ROOT / args.dataset)
    summary = evaluate(dataset)
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Coreference Evaluation Summary")
    print(f"  dataset: {summary['dataset_name']}")
    print(f"  samples: {summary['samples']}")
    print(f"  total_coreference_cases: {summary['total_coreference_cases']}")
    print(f"  correct: {summary['correct']}")
    print(f"  wrong: {summary['wrong']}")
    print(f"  accuracy: {summary['accuracy']:.4f}")
    print(f"  output: {output_path}")
    if summary["wrong_cases"]:
        print("\nWrong cases:")
        for item in summary["wrong_cases"]:
            print(
                f"  - {item['sample_id']} {item['mention']}: "
                f"expected={item['expected_entity_id']} predicted={item['predicted_entity_id']}"
            )
    return 0 if summary["wrong"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
