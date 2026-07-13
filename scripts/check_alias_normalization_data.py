"""Validate the independent alias-normalization acceptance dataset."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "eval" / "alias_normalization_test.json"
KB_PATH = ROOT / "data" / "kb" / "energy_entities.json"
REPORT_PATH = ROOT / "reports" / "alias_data_quality_report.md"
REQUIRED = {"id", "text", "mention", "mention_type", "alias_type", "entity_type", "expected_entity", "is_nil", "difficulty", "is_ambiguous", "evidence", "candidate_entities", "expected_candidate_rank", "ambiguity_type", "is_negative"}
ALIAS_TYPES = {"abbreviation", "short_name", "former_name", "english_name", "nickname", "industry_alias", "regional_alias", "typo_alias"}
DIFFICULTIES = {"easy", "medium", "hard"}
AMBIGUITY_TYPES = {"none", "same_alias", "same_type_similarity", "parent_child", "regional_confusion", "product_company_confusion"}


def alias_names(entity: dict) -> set[str]:
    values = {str(entity.get("abbreviation", "")).strip()}
    for alias in entity.get("aliases", []):
        values.add(str(alias.get("name", "")).strip() if isinstance(alias, dict) else str(alias).strip())
    return {item for item in values if item}


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read dataset: {exc}")
        return 1
    kb = json.loads(KB_PATH.read_text(encoding="utf-8"))
    entities = {item["entity_id"]: item for item in kb.get("entities", [])}
    alias_owner: dict[str, set[str]] = defaultdict(set)
    known_forms: set[str] = set()
    for entity in entities.values():
        known_forms.add(str(entity.get("entity_name", "")).strip())
        for alias in alias_names(entity):
            alias_owner[alias].add(entity["entity_id"])

    samples = data.get("samples")
    if not isinstance(samples, list):
        errors.append("root.samples must be a list")
        samples = []
    ids: set[str] = set()
    sample_keys: Counter[tuple[str, str, str | None]] = Counter()
    types: Counter[str] = Counter()
    difficulties: Counter[str] = Counter()
    templates: Counter[str] = Counter()
    for index, sample in enumerate(samples, start=1):
        label = sample.get("id", f"index-{index}") if isinstance(sample, dict) else f"index-{index}"
        if not isinstance(sample, dict):
            errors.append(f"{label}: sample must be an object")
            continue
        missing = sorted(REQUIRED - set(sample))
        if missing:
            errors.append(f"{label}: missing required fields {missing}")
            continue
        if sample["id"] in ids:
            errors.append(f"{label}: duplicate id")
        ids.add(sample["id"])
        mention = str(sample["mention"]).strip()
        if not mention:
            errors.append(f"{label}: empty mention")
        elif mention not in sample["text"]:
            errors.append(f"{label}: mention not found in text")
        expected_id = sample.get("expected_entity", {}).get("entity_id") if isinstance(sample.get("expected_entity"), dict) else None
        sample_keys[(sample["text"], mention, expected_id)] += 1
        if sample["mention_type"] != "ALIAS":
            errors.append(f"{label}: mention_type must be ALIAS")
        if sample["alias_type"] not in ALIAS_TYPES:
            errors.append(f"{label}: invalid alias_type {sample['alias_type']}")
        if sample["difficulty"] not in DIFFICULTIES:
            errors.append(f"{label}: invalid difficulty {sample['difficulty']}")
        if sample["ambiguity_type"] not in AMBIGUITY_TYPES:
            errors.append(f"{label}: invalid ambiguity_type {sample['ambiguity_type']}")
        candidates = sample["candidate_entities"]
        if not isinstance(candidates, list):
            errors.append(f"{label}: candidate_entities must be a list")
            candidates = []
        candidate_ids = []
        for candidate in candidates:
            if not isinstance(candidate, dict) or not candidate.get("entity_id") or not candidate.get("name"):
                errors.append(f"{label}: malformed candidate entity")
                continue
            candidate_entity = entities.get(candidate["entity_id"])
            if candidate_entity is None:
                errors.append(f"{label}: candidate entity_id not found in KB: {candidate['entity_id']}")
            elif candidate["name"] != candidate_entity.get("entity_name"):
                errors.append(f"{label}: candidate name does not match KB")
            candidate_ids.append(candidate["entity_id"])
        if len(candidate_ids) != len(set(candidate_ids)):
            errors.append(f"{label}: duplicate candidate entity_id")
        if sample["is_ambiguous"] and len(candidate_ids) < 2 and sample.get("source_case"):
            errors.append(f"{label}: sourced ambiguity case requires at least two candidates")
        expected = sample["expected_entity"]
        if not isinstance(expected, dict) or "entity_id" not in expected or "canonical_name" not in expected:
            errors.append(f"{label}: malformed expected_entity")
            continue
        is_negative = sample["is_negative"] is True
        if is_negative:
            if sample["is_nil"] is not True or sample.get("has_nil") is not True:
                errors.append(f"{label}: negative sample must set is_nil and has_nil to true")
            if expected["entity_id"] is not None or expected["canonical_name"] is not None:
                errors.append(f"{label}: negative sample expected_entity must be null-valued")
            if mention in known_forms or mention in alias_owner:
                errors.append(f"{label}: negative mention already exists as a KB canonical name or alias")
            if sample["expected_candidate_rank"] is not None:
                errors.append(f"{label}: negative sample expected_candidate_rank must be null")
        else:
            if sample["is_nil"] is not False or sample.get("has_nil") is not False:
                errors.append(f"{label}: positive sample must set is_nil and has_nil to false")
            entity = entities.get(expected["entity_id"])
            if entity is None:
                errors.append(f"{label}: entity_id not found in KB: {expected['entity_id']}")
                continue
            if expected["canonical_name"] != entity.get("entity_name"):
                errors.append(f"{label}: canonical_name does not match KB")
            if sample["entity_type"] != entity.get("entity_type"):
                errors.append(f"{label}: entity_type does not match KB")
            if mention not in alias_names(entity):
                errors.append(f"{label}: mention is not recorded as this entity's KB alias/abbreviation")
            owners = alias_owner.get(mention, set())
            if owners and expected["entity_id"] not in owners:
                errors.append(f"{label}: alias owner conflicts with expected entity")
            if len(owners) > 1 and not sample["is_ambiguous"]:
                warnings.append(f"{label}: KB alias is multi-owner but is_ambiguous=false")
            if candidates and expected["entity_id"] not in candidate_ids:
                errors.append(f"{label}: positive gold entity missing from candidate_entities")
            rank = sample["expected_candidate_rank"]
            if candidates and rank != 1:
                errors.append(f"{label}: candidate-pressure positive must expect final rank 1")
            if not candidates and rank is not None:
                errors.append(f"{label}: empty candidate_entities requires null expected_candidate_rank")
        compat_mentions = sample.get("mentions", [])
        compat_expected = sample.get("expected_entities", [])
        if len(compat_mentions) != 1 or len(compat_expected) != 1:
            errors.append(f"{label}: mention_linking compatibility arrays must each contain one item")
        elif compat_mentions[0].get("mention") != mention or compat_expected[0].get("entity_id") != expected["entity_id"]:
            errors.append(f"{label}: compatibility fields are inconsistent")
        types[sample["alias_type"]] += 1
        difficulties[sample["difficulty"]] += 1
        templates[sample["text"].replace(mention, "{mention}")] += 1

    exact_duplicates = [key for key, count in sample_keys.items() if count > 1]
    if exact_duplicates:
        errors.append(f"duplicate text/mention/gold records: {exact_duplicates[:3]}")
    overloaded = {template: count for template, count in templates.items() if count > 15}
    if overloaded:
        warnings.append(f"template concentration above 15 samples: {overloaded}")
    if len(types) < 5:
        warnings.append("fewer than five alias types represented")
    if max(types.values(), default=0) / max(len(samples), 1) > 0.45:
        warnings.append("one alias type exceeds 45% of samples")

    lines = [
        "# Alias Normalization Data Quality Report", "",
        f"- Dataset: `{DATA_PATH.relative_to(ROOT)}`",
        f"- Samples: {len(samples)}",
        f"- Schema errors: {len(errors)}",
        f"- Warnings: {len(warnings)}",
        f"- Result: {'PASS' if not errors else 'FAIL'}", "",
        "## Distribution", "",
        "|Dimension|Count|", "|-|-:|",
    ]
    lines += [f"|alias_type: {key}|{value}|" for key, value in sorted(types.items())]
    lines += [f"|difficulty: {key}|{value}|" for key, value in sorted(difficulties.items())]
    lines += ["", "## Errors", ""] + ([f"- {item}" for item in errors] or ["- None"])
    lines += ["", "## Warnings", ""] + ([f"- {item}" for item in warnings] or ["- None"])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Alias data quality: {'PASS' if not errors else 'FAIL'}")
    print(f"  samples={len(samples)} errors={len(errors)} warnings={len(warnings)}")
    print(f"  report={REPORT_PATH}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
