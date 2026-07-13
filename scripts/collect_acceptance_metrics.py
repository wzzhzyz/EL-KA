#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logging.disable(logging.CRITICAL)
os.environ["ELKA_LOG_LEVEL"] = "CRITICAL"
os.environ["PYTHONWARNINGS"] = "ignore"

from entity_linker.pipeline import EntityLinkingPipeline

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    pipeline = EntityLinkingPipeline(
        config={
            "kb_path": "data/kb/energy_entities.json",
            "nil_threshold": 0.90,
            "bge_llm_trigger_threshold": 0.65,
        }
    )

    candidate_dataset = load_json(ROOT / "data/eval/candidate_retrieval_test.json")
    disambiguation_dataset = load_json(ROOT / "data/eval/disambiguation_test.json")

    candidate_hits = 0
    candidate_total = 0
    for sample in candidate_dataset.get("samples", []):
        gold_entity = sample.get("gold_entity")
        if not gold_entity:
            continue
        generated = pipeline.candidate_gen.generate(sample["mention"], top_k=10)
        generated_ids = {candidate.entity.entity_id for candidate in generated}
        candidate_total += 1
        if gold_entity in generated_ids:
            candidate_hits += 1

    disambiguation_correct = 0
    disambiguation_total = 0
    for sample in disambiguation_dataset.get("samples", []):
        gold_entity = sample.get("gold_entity")
        expected_nil = bool(sample.get("expected_nil"))
        generated = pipeline.candidate_gen.generate(sample["mention"], top_k=10)
        if not generated:
            disambiguation_total += 1
            if expected_nil:
                disambiguation_correct += 1
            continue

        decision = pipeline.disambiguator.disambiguate(
            sample["mention"], generated, context=sample["text"]
        )
        entity_id = decision["entity"].entity_id if decision["entity"] else None
        disambiguation_total += 1
        if expected_nil:
            if entity_id is None:
                disambiguation_correct += 1
        else:
            if entity_id == gold_entity:
                disambiguation_correct += 1

    report = {
        "alias_recall": round(candidate_hits / candidate_total, 4)
        if candidate_total
        else 0.0,
        "disambiguation_accuracy": round(
            disambiguation_correct / disambiguation_total, 4
        )
        if disambiguation_total
        else 0.0,
        "candidate_hits": candidate_hits,
        "candidate_total": candidate_total,
        "disambiguation_correct": disambiguation_correct,
        "disambiguation_total": disambiguation_total,
    }

    output_path = ROOT / "reports" / "acceptance_aux_metrics.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
