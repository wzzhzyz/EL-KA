"""Append sourced ambiguity/NIL cases without altering existing alias gold labels."""
from __future__ import annotations

import json
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "eval" / "alias_normalization_test.json"
KB_PATH = ROOT / "data" / "kb" / "energy_entities.json"
SOURCE_PATHS = (
    ROOT / "data" / "eval" / "llm_fallback_ambiguity_test.json",
    ROOT / "data" / "eval" / "llm_fallback_difficult_cases.json",
)


def alias_name(value: object) -> str:
    return str(value.get("name", "")).strip() if isinstance(value, dict) else str(value).strip()


def alias_category(entity: dict, mention: str) -> str:
    if mention == str(entity.get("abbreviation", "")).strip():
        return "abbreviation"
    for alias in entity.get("aliases", []):
        if alias_name(alias) != mention:
            continue
        kind = str(alias.get("alias_type", "")) if isinstance(alias, dict) else ""
        if kind in {"\u82f1\u6587", "\u82f1\u6587\u7f29\u5199"}:
            return "english_name"
        if kind == "\u66fe\u7528\u540d":
            return "former_name"
        if kind == "\u4fd7\u79f0":
            return "nickname"
        if entity.get("entity_type") == "REGION":
            return "regional_alias"
        if entity.get("entity_type") == "TECHNICAL_TERM":
            return "industry_alias"
    return "short_name"


def ambiguity_category(raw: str) -> str:
    value = raw.lower()
    if "parent" in value or "subsidiary" in value:
        return "parent_child"
    if "regional" in value or "region" in value or "location" in value:
        return "regional_confusion"
    if "product" in value or "company" in value:
        return "product_company_confusion"
    return "same_type_similarity"


def candidate_rows(ids: list[str], entities: dict[str, dict]) -> list[dict]:
    return [
        {"entity_id": entity_id, "name": entities[entity_id]["entity_name"]}
        for entity_id in ids
        if entity_id in entities
    ]


def source_note(path: Path, sample: dict) -> str:
    return f"来源：{path.name}/{sample['id']}；候选与上下文沿用既有 LLM 歧义/NIL 金标数据。"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replace-extension", action="store_true", help="Replace only ALIAS_HARD_* records; preserve original ALIAS_001..ALIAS_120.")
    args = parser.parse_args()
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    samples = data.get("samples", [])
    if any(str(item.get("id", "")).startswith("ALIAS_HARD_") for item in samples) and not args.replace_extension:
        raise SystemExit("hard cases already exist; refusing to overwrite existing data")
    if args.replace_extension:
        samples = [item for item in samples if not str(item.get("id", "")).startswith("ALIAS_HARD_")]
        data["samples"] = samples
    kb = json.loads(KB_PATH.read_text(encoding="utf-8"))
    entities = {item["entity_id"]: item for item in kb["entities"]}
    alias_owners: dict[str, set[str]] = {}
    known_forms: set[str] = set()
    for entity_id, entity in entities.items():
        names = {str(entity.get("abbreviation", "")).strip()}
        names.update(alias_name(value) for value in entity.get("aliases", []))
        known_forms.add(str(entity.get("entity_name", "")).strip())
        for name in filter(None, names):
            alias_owners.setdefault(name, set()).add(entity_id)

    # Schema defaults are additive only; existing gold values remain untouched.
    for item in samples:
        item.setdefault("candidate_entities", [])
        item.setdefault("expected_candidate_rank", None)
        item.setdefault("ambiguity_type", "none")
        item.setdefault("is_negative", False)

    source_samples: list[tuple[Path, dict]] = []
    for path in SOURCE_PATHS:
        source_samples.extend((path, item) for item in json.loads(path.read_text(encoding="utf-8")).get("samples", []))

    positives: list[tuple[Path, dict]] = []
    negatives: list[tuple[Path, dict]] = []
    positive_mentions: set[str] = set()
    negative_mentions: set[str] = set()
    for path, item in source_samples:
        mention = str(item.get("mention", "")).strip()
        candidate_ids = item.get("candidate_entity_ids", [])
        gold = item.get("gold_entity_id")
        if item.get("expected_nil") is False and gold in entities and gold in candidate_ids and mention in alias_owners and gold in alias_owners[mention]:
            if mention not in positive_mentions and len(candidate_rows(candidate_ids, entities)) >= 2:
                positives.append((path, item)); positive_mentions.add(mention)
        if item.get("expected_nil") is True and mention and mention not in alias_owners and mention not in known_forms and mention not in negative_mentions and len(candidate_rows(candidate_ids, entities)) >= 2:
            negatives.append((path, item)); negative_mentions.add(mention)
    if len(positives) < 20 or len(negatives) < 20:
        raise SystemExit(f"insufficient sourced cases: positives={len(positives)}, negatives={len(negatives)}")

    additions: list[dict] = []
    for index, (path, item) in enumerate(positives[:20], start=1):
        gold = item["gold_entity_id"]
        entity = entities[gold]
        mention = item["mention"]
        candidates = candidate_rows(item["candidate_entity_ids"], entities)
        additions.append({
            "id": f"ALIAS_HARD_{index:03d}",
            "text": item["text"],
            "mention": mention,
            "mention_type": "ALIAS",
            "alias_type": alias_category(entity, mention),
            "entity_type": entity["entity_type"],
            "expected_entity": {"entity_id": gold, "canonical_name": entity["entity_name"]},
            "is_nil": False,
            "has_nil": False,
            "is_negative": False,
            "difficulty": "hard",
            "is_ambiguous": True,
            "ambiguity_type": ambiguity_category(str(item.get("ambiguity_type", ""))),
            "candidate_entities": candidates,
            "expected_candidate_rank": 1,
            "evidence": f"{source_note(path, item)} 决定性证据：{'；'.join(item.get('decisive_evidence', []))}。",
            "source_case": {"dataset": path.name, "id": item["id"]},
            "mentions": [{"mention": mention, "type": entity["entity_type"], "char_start": item["text"].index(mention), "char_end": item["text"].index(mention) + len(mention), "confidence": 1.0}],
            "expected_entities": [{"mention": mention, "entity_id": gold}],
        })
    for index, (path, item) in enumerate(negatives[:20], start=21):
        mention = item["mention"]
        candidates = candidate_rows(item["candidate_entity_ids"], entities)
        alias_type = "abbreviation" if mention.isascii() and mention.isupper() else "short_name"
        additions.append({
            "id": f"ALIAS_HARD_{index:03d}",
            "text": item["text"],
            "mention": mention,
            "mention_type": "ALIAS",
            "alias_type": alias_type,
            "entity_type": "UNKNOWN",
            "expected_entity": {"entity_id": None, "canonical_name": None},
            "is_nil": True,
            "has_nil": True,
            "is_negative": True,
            "difficulty": "hard",
            "is_ambiguous": True,
            "ambiguity_type": ambiguity_category(str(item.get("ambiguity_type", ""))),
            "candidate_entities": candidates,
            "expected_candidate_rank": None,
            "evidence": f"{source_note(path, item)} 原标注 expected_nil=true，且该 mention 不存在于运行知识库 alias 索引。",
            "source_case": {"dataset": path.name, "id": item["id"]},
            "mentions": [{"mention": mention, "type": "UNKNOWN", "char_start": item["text"].index(mention), "char_end": item["text"].index(mention) + len(mention), "confidence": 1.0}],
            "expected_entities": [{"mention": mention, "entity_id": None}],
        })
    samples.extend(additions)
    data["statistics"] = {**data.get("statistics", {}), "sample_count": len(samples), "hard_case_extension": len(additions)}
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"appended {len(additions)} sourced cases: positives=20, negatives=20, total={len(samples)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
