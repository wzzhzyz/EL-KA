"""Build the alias-normalization acceptance dataset from the running KB only."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB_PATH = ROOT / "data" / "kb" / "energy_entities.json"
OUT_PATH = ROOT / "data" / "eval" / "alias_normalization_test.json"

SHORT = {"\u7b80\u79f0", "\u5e38\u7528\u540d\u79f0"}
FORMER = {"\u66fe\u7528\u540d"}
ENGLISH = {"\u82f1\u6587", "\u82f1\u6587\u7f29\u5199"}
NICKNAME = {"\u4fd7\u79f0"}
INDUSTRY = {"\u4ea7\u54c1\u540d", "\u5173\u8054\u4ea7\u54c1"}

TARGETS = (
    ("industry_alias", 10),
    ("short_name", 35),
    ("abbreviation", 20),
    ("former_name", 14),
    ("english_name", 15),
    ("regional_alias", 10),
    ("nickname", 16),
)

TEXT_TEMPLATES = {
    "short_name": [
        "在公开业务材料中，{mention}发布了相关信息。",
        "本次行业交流由{mention}参与。",
        "报道提及{mention}正在推进既定项目。",
    ],
    "abbreviation": [
        "技术资料中使用{mention}作为机构标识。",
        "会议纪要记录了{mention}的相关安排。",
        "项目文件将{mention}列为合作对象。",
    ],
    "former_name": [
        "历史资料仍以{mention}称呼该主体。",
        "旧版公告中出现了名称{mention}。",
        "档案记录使用{mention}这一历史名称。",
    ],
    "english_name": [
        "英文资料中提及{mention}的业务进展。",
        "国际合作文件将{mention}列为相关主体。",
        "公开英文报道出现了{mention}。",
    ],
    "industry_alias": [
        "行业材料将{mention}列为相关对象。",
        "产品与服务说明中提到了{mention}。",
        "业务讨论围绕{mention}展开。",
    ],
    "regional_alias": [
        "区域发展材料提及{mention}的相关情况。",
        "统计报告以{mention}作为地区称谓。",
        "项目所在地标注为{mention}。",
    ],
    "nickname": [
        "公众报道中常以{mention}指代该主体。",
        "行业交流中出现了{mention}这一常用称呼。",
        "相关材料使用{mention}作为别称。",
    ],
}


def alias_name(value: object) -> str:
    return str(value.get("name", "")).strip() if isinstance(value, dict) else str(value).strip()


def alias_kind(value: object) -> str:
    return str(value.get("alias_type", "")).strip() if isinstance(value, dict) else ""


def balanced_take(pool: list[dict], count: int, used: set[str]) -> list[dict]:
    """Take unique aliases while round-robining entity types for breadth."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in pool:
        if item["mention"] not in used:
            groups[item["entity_type"]].append(item)
    for items in groups.values():
        items.sort(key=lambda x: (len(x["mention"]), x["entity_id"], x["mention"]))
    picked: list[dict] = []
    while len(picked) < count and any(groups.values()):
        progressed = False
        for entity_type in sorted(groups):
            if len(picked) >= count:
                break
            if groups[entity_type]:
                item = groups[entity_type].pop(0)
                if item["mention"] not in used:
                    picked.append(item)
                    used.add(item["mention"])
                    progressed = True
        if not progressed:
            break
    if len(picked) != count:
        raise ValueError(f"insufficient unique aliases: expected {count}, got {len(picked)}")
    return picked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=120, help="Create the first N samples of the fixed full set.")
    args = parser.parse_args()
    if not 1 <= args.limit <= 120:
        raise SystemExit("--limit must be between 1 and 120")

    kb = json.loads(KB_PATH.read_text(encoding="utf-8"))
    pools: dict[str, list[dict]] = defaultdict(list)
    for entity in kb["entities"]:
        base = {
            "entity_id": entity["entity_id"],
            "canonical_name": entity["entity_name"],
            "entity_type": entity["entity_type"],
        }
        abbreviation = str(entity.get("abbreviation", "")).strip()
        if abbreviation and abbreviation != entity["entity_name"]:
            pools["abbreviation"].append({**base, "mention": abbreviation, "kb_alias_type": "abbreviation"})
        for alias in entity.get("aliases", []):
            mention, kind = alias_name(alias), alias_kind(alias)
            if not mention or mention == entity["entity_name"]:
                continue
            record = {**base, "mention": mention, "kb_alias_type": kind or "string_alias"}
            if kind in SHORT:
                pools["short_name"].append(record)
            elif kind in FORMER:
                pools["former_name"].append(record)
            elif kind in ENGLISH:
                pools["english_name"].append(record)
            elif kind in NICKNAME:
                pools["nickname"].append(record)
            elif kind in INDUSTRY or "\u4ea7\u54c1" in kind or "\u5173\u8054" in kind:
                pools["industry_alias"].append(record)
            if entity["entity_type"] == "TECHNICAL_TERM":
                pools["industry_alias"].append(record)
            if entity["entity_type"] == "REGION":
                pools["regional_alias"].append(record)

    used: set[str] = set()
    selected: list[dict] = []
    for category, count in TARGETS:
        try:
            chosen = balanced_take(pools[category], count, used)
        except ValueError as exc:
            raise ValueError(f"{category}: pool={len(pools[category])}; {exc}") from exc
        selected.extend({**item, "alias_type": category} for item in chosen)

    # Short/common forms are the most likely to need contextual confirmation.
    hard_indices = sorted(
        range(len(selected)), key=lambda i: (len(selected[i]["mention"]), selected[i]["alias_type"], selected[i]["entity_id"])
    )[:20]
    hard_set = set(hard_indices)
    samples = []
    for index, item in enumerate(selected[: args.limit], start=1):
        hard = index - 1 in hard_set
        difficulty = "hard" if hard else ("medium" if item["alias_type"] in {"former_name", "english_name", "regional_alias", "nickname"} else "easy")
        text = TEXT_TEMPLATES[item["alias_type"]][(index - 1) % 3].format(mention=item["mention"])
        start = text.index(item["mention"])
        evidence = f"“{item['mention']}”直接收录于知识库实体 {item['entity_id']} 的别名信息（{item['kb_alias_type']}）。"
        if hard:
            evidence += "该名称较短或为常用称呼，可能与同业对象混淆；本样本以实体类型和上下文作为验收辅助证据。"
        samples.append({
            "id": f"ALIAS_{index:03d}",
            "text": text,
            "mention": item["mention"],
            "mention_type": "ALIAS",
            "alias_type": item["alias_type"],
            "entity_type": item["entity_type"],
            "expected_entity": {"entity_id": item["entity_id"], "canonical_name": item["canonical_name"]},
            "is_nil": False,
            "has_nil": False,
            "difficulty": difficulty,
            "is_ambiguous": hard,
            "evidence": evidence,
            "mentions": [{"mention": item["mention"], "type": item["entity_type"], "char_start": start, "char_end": start + len(item["mention"]), "confidence": 1.0}],
            "expected_entities": [{"mention": item["mention"], "entity_id": item["entity_id"]}],
        })
    payload = {
        "dataset_name": "alias_normalization_test",
        "version": "1.0",
        "purpose": "别名/简称/历史名称到标准实体的专项验收测试集。",
        "input_contract": "已识别 mention 输入；samples 同时保留 mention_linking_test 的 mentions/expected_entities 兼容字段。",
        "annotation_policy": "所有测试 mention 均直接来源于运行知识库 aliases 或 abbreviation；不含 NIL 或人工虚构别名。",
        "supported_alias_types": ["abbreviation", "short_name", "former_name", "english_name", "nickname", "industry_alias", "regional_alias", "typo_alias"],
        "statistics": {"sample_count": len(samples)},
        "samples": samples,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH}: {len(samples)} samples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
