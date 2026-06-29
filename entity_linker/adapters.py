from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .models import TYPE_MAPPING, StandardEntity, StandardMention


def normalize_mentions(mentions: Iterable[Dict[str, Any]]) -> List[StandardMention]:
    """把外部 mention 字典列表归一化为 StandardMention 列表。"""
    normalized: List[StandardMention] = []
    for mention in mentions:
        if isinstance(mention, dict):
            normalized.append(StandardMention.from_dict(mention))
    return normalized


def normalize_entity(data: Dict[str, Any]) -> StandardEntity:
    """把外部实体记录转换为 StandardEntity。兼容多种 JSON 字段格式。"""
    aliases = []
    for alias in data.get("aliases", []):
        if isinstance(alias, dict):
            alias_name = alias.get("name")
            if alias_name:
                aliases.append(alias_name)
        elif isinstance(alias, str):
            aliases.append(alias)

    entity_type = data.get("entity_type", data.get("type", "UNKNOWN"))
    if isinstance(entity_type, str):
        entity_type = TYPE_MAPPING.get(entity_type, entity_type)

    return StandardEntity(
        entity_id=data.get("entity_id", ""),
        standard_name=data.get("standard_name", data.get("entity_name", "")),
        aliases=aliases,
        entity_type=entity_type,
        description=data.get("description", ""),
        metadata={
            "industry": data.get("industry", ""),
            "abbreviation": data.get("abbreviation", ""),
            "source": data.get("source", ""),
            "tags": data.get("tags", []),
            **data.get("metadata", {}),
        },
    )


def normalize_entities(records: Iterable[Dict[str, Any]]) -> List[StandardEntity]:
    return [normalize_entity(record) for record in records]
