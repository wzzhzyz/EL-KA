#!/usr/bin/env python3
"""Evaluate entity linking with mention-given input or raw-text input.

The task specification defines the primary input as:
text + recognized mentions + knowledge base.

Mention-given mode is therefore the default. Raw mode is retained as an
auxiliary end-to-end NER + linking check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_texts(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


def normalize_entity_id(entity_id: Optional[str]) -> Optional[str]:
    if entity_id is None:
        return None
    value = str(entity_id).strip()
    return value or None


def load_mention_dataset(path: Path) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    payload = load_json(path)
    samples = payload.get("samples", [])
    knowledge_base = payload.get("knowledge_base", {})
    kb_path = knowledge_base.get("path")
    if not kb_path:
        raise ValueError("dataset missing knowledge_base.path")
    resolved_kb_path = ROOT / kb_path
    if not resolved_kb_path.exists():
        raise ValueError(f"knowledge base not found: {resolved_kb_path}")
    kb_payload = load_json(resolved_kb_path)
    valid_entity_ids = {
        item.get("entity_id") for item in kb_payload.get("entities", [])
    }

    required = {"text", "mentions", "expected_entities"}
    for index, sample in enumerate(samples):
        missing = required - sample.keys()
        if missing:
            raise ValueError(f"sample[{index}] missing fields: {sorted(missing)}")
        input_mentions = []
        for mention in sample["mentions"]:
            if "entity_id" in mention:
                raise ValueError(
                    f"sample[{index}] input mention must not contain gold entity_id"
                )
            text = mention.get("mention", "")
            start = mention.get("char_start")
            end = mention.get("char_end")
            if not isinstance(start, int) or not isinstance(end, int):
                raise ValueError(f"sample[{index}] mention offsets must be integers")
            if sample["text"][start:end] != text:
                raise ValueError(f"sample[{index}] mention span mismatch: {text}")
            input_mentions.append(text)

        expected_mentions = []
        for expected in sample["expected_entities"]:
            expected_mentions.append(expected.get("mention"))
            entity_id = normalize_entity_id(expected.get("entity_id"))
            if entity_id is not None and entity_id not in valid_entity_ids:
                raise ValueError(
                    f"sample[{index}] unknown gold entity_id: {entity_id}"
                )
        if input_mentions != expected_mentions:
            raise ValueError(
                f"sample[{index}] input mentions and gold mentions are not aligned"
            )
    return samples, knowledge_base


def load_legacy_dataset(
    ground_truth_path: Path, texts_path: Path
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    ground_truth = load_json(ground_truth_path)
    texts = load_texts(texts_path)
    samples: List[Dict[str, Any]] = []
    for entry in ground_truth.get("entries", []):
        text_index = int(entry.get("text_idx", -1))
        if text_index < 0 or text_index >= len(texts):
            print(f"[WARN] skip out-of-range text_idx={text_index}")
            continue
        text = texts[text_index]
        mentions = []
        for expected in entry.get("expected_entities", []):
            mention = expected.get("mention", "")
            start = text.find(mention)
            mentions.append(
                {
                    "mention": mention,
                    "type": "UNKNOWN",
                    "char_start": max(start, 0),
                    "char_end": max(start, 0) + len(mention),
                    "confidence": 1.0,
                }
            )
        samples.append(
            {
                "id": f"LEGACY_{text_index + 1:03d}",
                "text": text,
                "mentions": mentions,
                "expected_entities": entry.get("expected_entities", []),
                "scenario": entry.get("scenario", ""),
            }
        )
    return samples, {"type": "json", "path": "data/kb/energy_entities.json"}


def evaluate(samples: List[Dict[str, Any]], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_mentions = 0
    correct = 0
    non_nil_total = 0
    non_nil_correct = 0
    gold_nil_total = 0
    nil_true_positive = 0
    nil_false_positive = 0
    missing_predictions = 0

    for sample, prediction in zip(samples, results):
        prediction_map = {
            item.get("mention"): item for item in prediction.get("results", [])
        }
        for expected in sample.get("expected_entities", []):
            total_mentions += 1
            mention = expected.get("mention")
            gold_id = normalize_entity_id(expected.get("entity_id"))
            predicted = prediction_map.get(mention)

            if gold_id is None:
                gold_nil_total += 1
            else:
                non_nil_total += 1

            if predicted is None:
                missing_predictions += 1
                continue

            predicted_id = normalize_entity_id(predicted.get("entity_id"))
            predicted_nil = bool(predicted.get("is_nil", False) or predicted_id is None)

            if gold_id is None and predicted_nil:
                nil_true_positive += 1
                correct += 1
            elif gold_id is not None and predicted_id == gold_id:
                non_nil_correct += 1
                correct += 1
            elif gold_id is not None and predicted_nil:
                nil_false_positive += 1

    nil_false_negative = gold_nil_total - nil_true_positive
    nil_precision = (
        nil_true_positive / (nil_true_positive + nil_false_positive)
        if nil_true_positive + nil_false_positive
        else 0.0
    )
    nil_recall = nil_true_positive / gold_nil_total if gold_nil_total else 0.0
    nil_f1 = (
        2 * nil_precision * nil_recall / (nil_precision + nil_recall)
        if nil_precision + nil_recall
        else 0.0
    )

    return {
        "samples": len(samples),
        "total_mentions": total_mentions,
        "correct": correct,
        "overall_accuracy": correct / total_mentions if total_mentions else 0.0,
        "non_nil_total": non_nil_total,
        "non_nil_correct": non_nil_correct,
        "linking_accuracy": (
            non_nil_correct / non_nil_total if non_nil_total else 0.0
        ),
        "gold_nil_total": gold_nil_total,
        "nil_true_positive": nil_true_positive,
        "nil_false_positive": nil_false_positive,
        "nil_false_negative": nil_false_negative,
        "nil_precision": nil_precision,
        "nil_recall": nil_recall,
        "nil_f1": nil_f1,
        "missing_predictions": missing_predictions,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default="data/eval/mention_linking_test.json",
        help="mention-given dataset containing text, mentions and gold links",
    )
    parser.add_argument(
        "--input-mode",
        choices=("mentions", "raw"),
        default="mentions",
        help="mentions: task-spec input; raw: auxiliary NER + linking input",
    )
    parser.add_argument("--ground-truth", default="data/batch_ground_truth.json")
    parser.add_argument("--texts", default="data/batch_texts.txt")
    parser.add_argument("--trace-prefix", default="gt")
    parser.add_argument("--bge-model-path", default=None)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    dataset_path = Path(args.dataset)
    if dataset_path.exists():
        samples, knowledge_base = load_mention_dataset(dataset_path)
    else:
        samples, knowledge_base = load_legacy_dataset(
            Path(args.ground_truth), Path(args.texts)
        )

    from entity_linker.pipeline import EntityLinkingPipeline
    from entity_linker.utils.trace import new_trace_id

    config: Dict[str, Any] = {}
    kb_path = knowledge_base.get("path")
    if kb_path:
        config["kb_path"] = kb_path
    if args.bge_model_path:
        config["bge_model_path"] = args.bge_model_path

    pipeline = EntityLinkingPipeline(config=config)
    results: List[Dict[str, Any]] = []

    print(f"input_mode={args.input_mode}")
    print(f"dataset={dataset_path if dataset_path.exists() else 'legacy'}")
    print(f"knowledge_base={kb_path or 'pipeline default'}")
    print(f"backend={pipeline.backend}")

    if args.input_mode == "mentions":
        options = {"linkable_types": ["ORG", "GPE", "PERSON", "LOC", "UNKNOWN"]}
        for sample in samples:
            result = pipeline.run_with_mentions(
                text=sample["text"],
                mentions=sample["mentions"],
                options=options,
                trace_id=new_trace_id(prefix=args.trace_prefix),
            )
            results.append(result)
    else:
        results = pipeline.run_batch(
            [sample["text"] for sample in samples],
            options={},
            trace_id_prefix=args.trace_prefix,
        )

    metrics = evaluate(samples, results)
    print("\nEntity Linking Evaluation Summary")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")

    if args.verbose:
        print("\nInput contract sample")
        print(json.dumps(samples[0], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
