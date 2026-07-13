"""Evaluate alias normalization with the project's local candidate-generation path."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from entity_linker.pipeline import _FallbackCandidateGenerator, _LocalKnowledgeBase

DATA_PATH = ROOT / "data" / "eval" / "alias_normalization_test.json"
KB_PATH = ROOT / "data" / "kb" / "energy_entities.json"
REPORT_PATH = ROOT / "docs" / "alias_normalization_evaluation.md"


def rate(rows: list[dict]) -> str:
    total = len(rows)
    hit = sum(row["correct"] for row in rows)
    return f"{hit}/{total} ({hit / total:.2%})" if total else "0/0 (n/a)"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate alias normalization against the local KB candidate path.")
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    samples = data.get("samples", [])
    kb = _LocalKnowledgeBase(KB_PATH)
    generator = _FallbackCandidateGenerator(kb)
    rows = []
    for sample in samples:
        candidates = generator.generate(sample["mention"], top_k=10)
        candidate_ids = [candidate.entity.entity_id for candidate in candidates]
        predicted_id = candidate_ids[0] if candidate_ids else None
        expected_id = sample["expected_entity"]["entity_id"]
        rows.append({
            "id": sample["id"],
            "correct": predicted_id == expected_id,
            "expected_id": expected_id,
            "predicted_id": predicted_id,
            "candidate_ids": candidate_ids,
            "alias_type": sample["alias_type"],
            "difficulty": sample["difficulty"],
            "entity_type": sample["entity_type"],
            "mention": sample["mention"],
            "is_negative": bool(sample.get("is_negative")),
            "is_ambiguous": bool(sample.get("is_ambiguous")),
            "has_candidate_pressure": bool(sample.get("candidate_entities")),
        })
    by_alias: dict[str, list[dict]] = defaultdict(list)
    by_difficulty: dict[str, list[dict]] = defaultdict(list)
    by_entity: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_alias[row["alias_type"]].append(row)
        by_difficulty[row["difficulty"]].append(row)
        by_entity[row["entity_type"]].append(row)
    positives = [row for row in rows if not row["is_negative"]]
    negatives = [row for row in rows if row["is_negative"]]
    ambiguous = [row for row in positives if row["is_ambiguous"] and row["has_candidate_pressure"]]
    for row in negatives:
        # A negative is correct only if the local candidate path refuses to return a KB entity.
        row["correct"] = row["predicted_id"] is None
    badcases = [row for row in rows if not row["correct"]]
    positive_recall = sum(row["correct"] for row in positives) / len(positives) if positives else 0.0
    negative_precision = sum(row["correct"] for row in negatives) / len(negatives) if negatives else 0.0
    ambiguous_accuracy = sum(row["correct"] for row in ambiguous) / len(ambiguous) if ambiguous else 0.0
    overall = sum(row["correct"] for row in rows) / len(rows) if rows else 0.0
    lines = [
        "# Alias Normalization Evaluation", "",
        "## Evaluation setup", "",
        "- Dataset: `data/eval/alias_normalization_test.json`",
        "- Runtime path: `entity_linker.pipeline._LocalKnowledgeBase` + `_FallbackCandidateGenerator`",
        "- Positive Recall: positive samples whose Top-1 predicted entity ID equals the gold entity ID.",
        "- Negative Precision: negative samples for which the local candidate path returns no KB entity.",
        "- Ambiguous Accuracy: positive `is_ambiguous=true` samples with an explicit candidate list whose Top-1 prediction equals gold.",
        "- Scope: evaluates the project local KB alias lookup/candidate path. Candidate lists are acceptance metadata; this fallback path does not use context to rerank them.", "",
        "## Overall result", "",
        f"- Total samples: {len(rows)}",
        f"- Positive Recall: {positive_recall:.2%} ({sum(row['correct'] for row in positives)}/{len(positives)})",
        f"- Negative Precision: {negative_precision:.2%} ({sum(row['correct'] for row in negatives)}/{len(negatives)})",
        f"- Ambiguous Accuracy: {ambiguous_accuracy:.2%} ({sum(row['correct'] for row in ambiguous)}/{len(ambiguous)})",
        f"- Overall Accuracy: {overall:.2%} ({sum(row['correct'] for row in rows)}/{len(rows)})", "",
        "## By alias type", "", "|alias_type|result|", "|-|-|",
    ]
    lines += [f"|{key}|{rate(value)}|" for key, value in sorted(by_alias.items())]
    lines += ["", "## By difficulty", "", "|difficulty|result|", "|-|-|"]
    lines += [f"|{key}|{rate(value)}|" for key, value in sorted(by_difficulty.items())]
    lines += ["", "## By entity type", "", "|entity_type|result|", "|-|-|"]
    lines += [f"|{key}|{rate(value)}|" for key, value in sorted(by_entity.items())]
    lines += ["", "## Badcase analysis", ""]
    if badcases:
        lines += [f"- `{row['id']}`: mention `{row['mention']}`, expected `{row['expected_id']}`, predicted `{row['predicted_id']}`, candidates `{row['candidate_ids']}`" for row in badcases]
    else:
        lines += ["- No badcases in the local candidate path. This verifies KB alias coverage and negative rejection under its current matching behavior."]
    lines += ["", "## Current limitations", "", "- The positive set deliberately uses only KB-recorded aliases; typo_alias is a supported schema value but has no sample because the running KB contains no verified typo aliases.", "- The running KB has no multi-owner alias. Candidate-pressure samples reuse real candidates and context from existing LLM datasets, but the local fallback candidate generator does not consume context to rerank candidates."]
    output = Path(args.output)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Alias Normalization Evaluation")
    print(f"  Total Samples: {len(rows)}")
    print(f"  Positive Recall: {positive_recall:.2%}")
    print(f"  Negative Precision: {negative_precision:.2%}")
    print(f"  Ambiguous Accuracy: {ambiguous_accuracy:.2%}")
    print(f"  Overall Accuracy: {overall:.2%}")
    for key, value in sorted(by_alias.items()):
        print(f"  {key}: {rate(value)}")
    print(f"  report={output}")
    return 0 if positive_recall >= 0.85 and negative_precision >= 0.80 else 1


if __name__ == "__main__":
    raise SystemExit(main())
