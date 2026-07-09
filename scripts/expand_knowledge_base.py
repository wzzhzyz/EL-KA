#!/usr/bin/env python3
"""Batch helper for expanding entity-linking knowledge base.

Supported operations:
1. Add new entities to data/kb/energy_entities.json.
2. Add aliases to existing entities.
3. Validate duplicate entity_id and duplicate aliases before writing.

Input example:

{
  "new_entities": [
    {
      "entity_id": "ENT_GEN_1001",
      "entity_name": "示例科技有限公司",
      "entity_type": "TECH_COMPANY",
      "entity_type_display": "科技企业",
      "industry": "人工智能",
      "summary": "示例实体。",
      "aliases": ["示例科技", {"name": "Example Tech", "alias_type": "英文"}],
      "tags": ["科技"]
    }
  ],
  "alias_updates": [
    {
      "entity_id": "ENT_GEN_0053",
      "aliases": ["腾讯公司", {"name": "Tencent", "alias_type": "英文"}]
    }
  ]
}
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KB = ROOT / "data" / "kb" / "energy_entities.json"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_alias(alias: str | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(alias, str):
        return {
            "name": alias,
            "alias_type": "补充别名",
            "priority": 0.7,
            "confidence": 0.9,
        }
    if isinstance(alias, dict):
        name = str(alias.get("name", "")).strip()
        if not name:
            raise ValueError(f"alias missing name: {alias}")
        return {
            "name": name,
            "alias_type": alias.get("alias_type", "补充别名"),
            "priority": float(alias.get("priority", 0.7)),
            "confidence": float(alias.get("confidence", 0.9)),
        }
    raise TypeError(f"unsupported alias type: {alias!r}")


def alias_names(aliases: Iterable[Any]) -> set[str]:
    names: set[str] = set()
    for alias in aliases:
        if isinstance(alias, dict):
            name = str(alias.get("name", "")).strip()
        else:
            name = str(alias).strip()
        if name:
            names.add(name)
    return names


def build_indexes(entities: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    entity_index: Dict[str, Dict[str, Any]] = {}
    alias_index: Dict[str, str] = {}
    for entity in entities:
        entity_id = entity.get("entity_id")
        if not entity_id:
            raise ValueError(f"entity missing entity_id: {entity}")
        if entity_id in entity_index:
            raise ValueError(f"duplicate entity_id in KB: {entity_id}")
        entity_index[entity_id] = entity
        for name in alias_names([entity.get("entity_name", ""), *entity.get("aliases", [])]):
            alias_index.setdefault(name, entity_id)
    return entity_index, alias_index


def normalize_new_entity(record: Dict[str, Any]) -> Dict[str, Any]:
    required = ["entity_id", "entity_name", "entity_type"]
    missing = [field for field in required if not record.get(field)]
    if missing:
        raise ValueError(f"new entity missing fields {missing}: {record}")

    aliases = [normalize_alias(alias) for alias in record.get("aliases", [])]
    return {
        "entity_id": record["entity_id"],
        "entity_name": record["entity_name"],
        "aliases": aliases,
        "abbreviation": record.get("abbreviation", ""),
        "entity_type": record["entity_type"],
        "entity_type_display": record.get("entity_type_display", record["entity_type"]),
        "industry": record.get("industry", ""),
        "summary": record.get("summary", ""),
        "business": record.get("business", ""),
        "location": record.get(
            "location",
            {"country": "", "province": "", "city": "", "address": ""},
        ),
        "keywords": record.get("keywords", []),
        "source": record.get(
            "source",
            {
                "source_name": "人工补充",
                "publisher": "欧小红",
                "url": "",
                "crawl_time": str(date.today()),
                "license": "课程项目内部整理",
                "confidence": 0.8,
            },
        ),
        "relations": record.get("relations", []),
        "tags": record.get("tags", []),
        "evidence": record.get("evidence", {}),
        "update_time": record.get("update_time", str(date.today())),
        "ambiguity_level": record.get("ambiguity_level", "base"),
        "shared_aliases": record.get("shared_aliases", []),
    }


def apply_expansion(kb: Dict[str, Any], expansion: Dict[str, Any]) -> Dict[str, Any]:
    updated = copy.deepcopy(kb)
    entities = updated.setdefault("entities", [])
    entity_index, alias_index = build_indexes(entities)
    report = {
        "added_entities": [],
        "updated_aliases": [],
        "warnings": [],
    }

    for record in expansion.get("new_entities", []):
        entity = normalize_new_entity(record)
        entity_id = entity["entity_id"]
        if entity_id in entity_index:
            raise ValueError(f"new entity_id already exists: {entity_id}")
        duplicate_aliases = sorted(
            name for name in alias_names([entity["entity_name"], *entity["aliases"]])
            if name in alias_index
        )
        if duplicate_aliases:
            report["warnings"].append(
                {
                    "type": "alias_already_exists",
                    "entity_id": entity_id,
                    "aliases": duplicate_aliases,
                }
            )
        entities.append(entity)
        entity_index[entity_id] = entity
        for name in alias_names([entity["entity_name"], *entity["aliases"]]):
            alias_index.setdefault(name, entity_id)
        report["added_entities"].append(entity_id)

    for update in expansion.get("alias_updates", []):
        entity_id = update.get("entity_id")
        if entity_id not in entity_index:
            raise ValueError(f"alias update target not found: {entity_id}")
        entity = entity_index[entity_id]
        existing_names = alias_names(entity.get("aliases", []))
        added = []
        skipped = []
        for alias in update.get("aliases", []):
            normalized = normalize_alias(alias)
            name = normalized["name"]
            if name in existing_names:
                skipped.append(name)
                continue
            if name in alias_index and alias_index[name] != entity_id:
                report["warnings"].append(
                    {
                        "type": "alias_belongs_to_other_entity",
                        "alias": name,
                        "current_entity_id": entity_id,
                        "existing_entity_id": alias_index[name],
                    }
                )
            entity.setdefault("aliases", []).append(normalized)
            existing_names.add(name)
            alias_index.setdefault(name, entity_id)
            added.append(name)
        report["updated_aliases"].append(
            {"entity_id": entity_id, "added": added, "skipped": skipped}
        )

    updated.setdefault("config_alignment", {})["last_expansion_report"] = report
    return updated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批量扩充知识库实体与别名")
    parser.add_argument("--kb", default=str(DEFAULT_KB), help="知识库 JSON 路径")
    parser.add_argument("--input", required=True, help="扩充数据 JSON 路径")
    parser.add_argument("--output", default=None, help="输出路径；默认覆盖 --kb")
    parser.add_argument("--dry-run", action="store_true", help="只校验和打印报告，不写文件")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    kb_path = Path(args.kb)
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else kb_path

    kb = load_json(kb_path)
    expansion = load_json(input_path)
    updated = apply_expansion(kb, expansion)
    report = updated.get("config_alignment", {}).get("last_expansion_report", {})

    print("Knowledge Base Expansion Summary")
    print(f"  kb: {kb_path}")
    print(f"  input: {input_path}")
    print(f"  output: {output_path}")
    print(f"  added_entities: {len(report.get('added_entities', []))}")
    print(
        "  added_aliases: "
        f"{sum(len(item.get('added', [])) for item in report.get('updated_aliases', []))}"
    )
    print(f"  warnings: {len(report.get('warnings', []))}")

    if args.dry_run:
        print("  mode: dry-run, no file written")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    write_json(output_path, updated)
    print("  mode: written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
