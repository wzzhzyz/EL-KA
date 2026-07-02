#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端测试脚本：
- 读取 `data/batch_ground_truth.json` 和 `data/batch_texts.txt`
- 使用 `entity_linker.EntityLinkingPipeline` 批量运行
- 将 pipeline 输出与 ground truth 对齐并统计准确率 / NIL 检测

用法示例：
    python scripts/e2e_from_ground_truth.py \
        --ground-truth data/batch_ground_truth.json \
        --texts data/batch_texts.txt \
        --trace-prefix test

可选：
    --use-ea --bge-model-path D:\path\to\bge-small-zh

"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# ensure repo root is on sys.path when running this script directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_ground_truth(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_texts(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


def normalize_entity_id(eid: Optional[str]) -> Optional[str]:
    if eid is None:
        return None
    if isinstance(eid, str):
        v = eid.strip()
        return v if v else None
    return str(eid)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", default="data/batch_ground_truth.json")
    parser.add_argument("--texts", default="data/batch_texts.txt")
    parser.add_argument("--trace-prefix", default="gt")
    parser.add_argument(
        "--use-ea", action="store_true", help="尝试使用 EntityAlignmentV0 (需模型目录)"
    )
    parser.add_argument(
        "--bge-model-path", default=None, help="BGE 模型目录(如果使用 EA)"
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    gt = load_ground_truth(Path(args.ground_truth))
    texts = load_texts(Path(args.texts))

    # build test samples list according to text_idx
    entries = gt.get("entries", [])
    samples = []
    for e in entries:
        idx = int(e.get("text_idx", -1))
        if idx < 0 or idx >= len(texts):
            print(
                f"[WARN] text_idx {idx} out of range for texts file, skipping sample: {e.get('scenario', '')}"
            )
            continue
        samples.append(
            {
                "text": texts[idx],
                "expected_entities": e.get("expected_entities", []),
                "meta": e,
            }
        )

    # lazy import pipeline to avoid heavy imports if not running
    from entity_linker.pipeline import EntityLinkingPipeline

    config = {}
    if args.use_ea and args.bge_model_path:
        config["bge_model_path"] = args.bge_model_path
    pipeline = (
        EntityLinkingPipeline(config=config) if config else EntityLinkingPipeline()
    )

    print("Running pipeline, backend=", pipeline.backend)

    texts_to_run = [s["text"] for s in samples]
    results = pipeline.run_batch(
        texts_to_run, options={}, trace_id_prefix=args.trace_prefix
    )

    # Evaluate
    total_mentions = 0
    correct_links = 0
    nil_total = 0
    nil_correct = 0
    missing_predictions = 0

    for i, sample in enumerate(samples):
        expected = sample["expected_entities"]
        pred = results[i]
        pred_results = pred.get("results", [])
        # map by mention text
        pred_map = {r.get("mention"): r for r in pred_results}

        for exp in expected:
            total_mentions += 1
            gold_id = normalize_entity_id(exp.get("entity_id"))
            mention = exp.get("mention")
            if gold_id is None:
                nil_total += 1
            pr = pred_map.get(mention)
            if pr is None:
                missing_predictions += 1
                if args.verbose:
                    print(
                        f"[MISSING] text_idx={i} mention={mention} expected={gold_id}"
                    )
                continue
            predicted_id = normalize_entity_id(pr.get("entity_id"))
            predicted_nil = bool(pr.get("is_nil", False) or predicted_id is None)

            if gold_id is None:
                if predicted_nil:
                    nil_correct += 1
                    correct_links += 1
                else:
                    # false positive link
                    pass
            else:
                if predicted_id == gold_id:
                    correct_links += 1
                else:
                    if args.verbose:
                        print(
                            f"[WRONG] text_idx={i} mention={mention} gold={gold_id} pred={predicted_id}"
                        )

    accuracy = correct_links / total_mentions if total_mentions else 0.0
    nil_precision = nil_correct / (nil_total if nil_total else 1)

    print("\nE2E Evaluation Summary")
    print(f"  samples: {len(samples)}")
    print(f"  total_mentions: {total_mentions}")
    print(f"  correct_links: {correct_links}")
    print(f"  accuracy: {accuracy:.4f}")
    print(
        f"  nil_total: {nil_total}, nil_correct: {nil_correct}, nil_precision: {nil_precision:.4f}"
    )
    print(f"  missing_predictions: {missing_predictions}")

    # Optionally, save detailed results


if __name__ == "__main__":
    main()
