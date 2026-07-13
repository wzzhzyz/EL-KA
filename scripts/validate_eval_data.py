"""Validate evaluation datasets for the entity linking project.

This script is intentionally schema-aware but non-invasive. It keeps the
existing per-file formats compatible, while enforcing common quality rules:

- dataset IDs are continuous where a prefix convention exists;
- mentions appear in their source text;
- character spans match the mention text;
- linked entity IDs exist in the knowledge base, except local coreference
  person/entity IDs that are declared in the same sample;
- NIL flags are consistent with expected entity IDs;
- batch text and ground-truth entries are aligned.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
EVAL_DIR = DATA_DIR / "eval"
KB_PATH = DATA_DIR / "kb" / "energy_entities.json"


DATASET_CONTRACTS = {
    "mention_linking_test.json": "已识别 mention 输入下的实体链接主评测集",
    "eval_dataset.json": "综合实体链接、消歧、NIL 评测集",
    "coreference_long_text_test.json": "长文本共指消解专项评测集",
    "llm_fallback_ambiguity_test.json": "LLM 兜底疑难消歧样本集",
    "llm_fallback_difficult_cases.json": "高歧义、低置信度困难样本集",
    "candidate_retrieval_test.json": "候选实体召回专项测试集",
    "disambiguation_test.json": "实体消歧与排序专项测试集",
    "ner_test_dataset.json": "NER 辅助测试集，不作为最终输入契约主数据",
}


class Audit:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.summary: dict[str, Any] = {}

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_continuous_ids(audit: Audit, dataset: str, samples: list[dict[str, Any]], prefix: str) -> None:
    expected = [f"{prefix}_{idx:03d}" for idx in range(1, len(samples) + 1)]
    actual = [sample.get("id") for sample in samples]
    if actual != expected:
        audit.error(f"{dataset}: id 不连续或顺序异常，期望 {expected[:1]}...{expected[-1:]}, 实际 {actual[:1]}...{actual[-1:]}")


def check_mention_in_text(audit: Audit, dataset: str, sample_id: str, text: str, mention: str | None) -> None:
    if mention and mention not in text:
        audit.error(f"{dataset}/{sample_id}: mention 不在 text 中: {mention}")


def check_span(
    audit: Audit,
    dataset: str,
    sample_id: str,
    text: str,
    mention: str | None,
    start: int | None,
    end: int | None,
) -> None:
    if mention is None or start is None or end is None:
        return
    if start < 0 or end < start or end > len(text):
        audit.error(f"{dataset}/{sample_id}: span 越界: {(start, end)}")
        return
    if text[start:end] != mention:
        audit.error(f"{dataset}/{sample_id}: span 与 mention 不匹配: {(start, end)} -> {text[start:end]} != {mention}")


def check_kb_id(audit: Audit, dataset: str, sample_id: str, entity_id: str | None, kb_ids: set[str], field: str) -> None:
    if entity_id is not None and entity_id not in kb_ids:
        audit.error(f"{dataset}/{sample_id}: {field} 不存在于 KB: {entity_id}")


def validate_eval_dataset(audit: Audit, kb_ids: set[str]) -> None:
    dataset = "eval_dataset.json"
    data = load_json(EVAL_DIR / dataset)
    samples = data.get("samples", [])
    ensure_continuous_ids(audit, dataset, samples, "EVAL")

    difficulty = Counter()
    nil_count = 0
    scenarios = Counter()
    for sample in samples:
        sid = sample.get("id", "<missing-id>")
        text = sample.get("text", "")
        mention = sample.get("mention")
        gold = sample.get("gold_entity")
        candidates = sample.get("candidate_entities", [])
        expected = sample.get("expected_result", {})

        check_mention_in_text(audit, dataset, sid, text, mention)
        check_span(audit, dataset, sid, text, mention, sample.get("mention_start"), sample.get("mention_end"))
        check_kb_id(audit, dataset, sid, gold, kb_ids, "gold_entity")
        for candidate in candidates:
            check_kb_id(audit, dataset, sid, candidate, kb_ids, "candidate_entity")

        if gold is None:
            nil_count += 1
            if expected.get("linked") is not False or expected.get("nil") is not True:
                audit.error(f"{dataset}/{sid}: NIL 样本 expected_result 标记不一致")
        else:
            if expected.get("correct_entity") != gold or expected.get("linked") is not True:
                audit.error(f"{dataset}/{sid}: expected_result 与 gold_entity 不一致")

        difficulty[sample.get("difficulty", "unknown")] += 1
        scenarios[sample.get("scenario", "unknown")] += 1

    metadata = data.get("dataset_metadata") or data.get("metadata") or {}
    total = metadata.get("total_samples")
    if total is not None and total != len(samples):
        audit.error(f"{dataset}: metadata.total_samples={total} 与实际数量 {len(samples)} 不一致")

    audit.summary[dataset] = {
        "contract": DATASET_CONTRACTS[dataset],
        "samples": len(samples),
        "nil_samples": nil_count,
        "difficulty": dict(difficulty),
        "scenario_count": len(scenarios),
    }


def validate_mention_linking(audit: Audit, kb_ids: set[str]) -> None:
    dataset = "mention_linking_test.json"
    data = load_json(EVAL_DIR / dataset)
    samples = data.get("samples", [])
    ensure_continuous_ids(audit, dataset, samples, "MENTION_LINK")

    mention_total = 0
    nil_mentions = 0
    multi_mention_samples = 0
    empty_samples = 0
    scenarios = Counter()

    for sample in samples:
        sid = sample.get("id", "<missing-id>")
        text = sample.get("text", "")
        mentions = sample.get("mentions", [])
        expected_entities = sample.get("expected_entities", [])
        scenarios[sample.get("scenario", "unknown")] += 1

        if not mentions:
            empty_samples += 1
        if len(mentions) > 1:
            multi_mention_samples += 1
        if len(mentions) != len(expected_entities):
            audit.error(f"{dataset}/{sid}: mentions 数量与 expected_entities 数量不一致")

        expected_nil = any(item.get("entity_id") is None for item in expected_entities)
        if bool(sample.get("has_nil", False)) != expected_nil:
            audit.error(f"{dataset}/{sid}: has_nil 与 expected_entities 不一致")

        expected_by_mention = {item.get("mention"): item.get("entity_id") for item in expected_entities}
        for mention_item in mentions:
            mention_total += 1
            mention = mention_item.get("mention")
            check_mention_in_text(audit, dataset, sid, text, mention)
            check_span(audit, dataset, sid, text, mention, mention_item.get("char_start"), mention_item.get("char_end"))
            entity_id = expected_by_mention.get(mention)
            if entity_id is None:
                nil_mentions += 1
            else:
                check_kb_id(audit, dataset, sid, entity_id, kb_ids, "expected_entity")

        for expected in expected_entities:
            check_mention_in_text(audit, dataset, sid, text, expected.get("mention"))
            entity_id = expected.get("entity_id")
            if entity_id is not None:
                check_kb_id(audit, dataset, sid, entity_id, kb_ids, "expected_entity")

    stats = data.get("statistics", {})
    if stats.get("sample_count") not in (None, len(samples)):
        audit.error(f"{dataset}: statistics.sample_count 与实际数量不一致")

    audit.summary[dataset] = {
        "contract": DATASET_CONTRACTS[dataset],
        "samples": len(samples),
        "mentions": mention_total,
        "nil_mentions": nil_mentions,
        "multi_mention_samples": multi_mention_samples,
        "empty_mention_samples": empty_samples,
        "scenario_count": len(scenarios),
    }


def validate_coreference(audit: Audit) -> None:
    dataset = "coreference_long_text_test.json"
    data = load_json(EVAL_DIR / dataset)
    samples = data.get("samples", [])

    expected_prefix = [f"COREF_LONG_{idx:03d}" for idx in range(1, len(samples) + 1)]
    actual_ids = [sample.get("id") for sample in samples]
    if actual_ids != expected_prefix:
        audit.error(f"{dataset}: id 不连续或顺序异常")

    total_cases = 0
    nil_cases = 0
    collective_cases = 0
    collective_nil_cases = 0
    anaphor_surfaces = Counter()
    for sample in samples:
        sid = sample.get("id", "<missing-id>")
        text = sample.get("text", "")
        mentions = sample.get("mentions", [])
        expected_corefs = sample.get("expected_coreferences", [])

        local_ids = {m.get("entity_id") for m in mentions if m.get("entity_id")}
        for mention in mentions:
            check_mention_in_text(audit, dataset, sid, text, mention.get("mention"))

        for coref in expected_corefs:
            total_cases += 1
            idx = coref.get("mention_index")
            if not isinstance(idx, int) or idx < 0 or idx >= len(mentions):
                audit.error(f"{dataset}/{sid}: mention_index 越界: {idx}")
                continue
            surface = mentions[idx].get("mention")
            if surface:
                anaphor_surfaces[surface] += 1
            entity_id = coref.get("entity_id")
            is_nil = bool(coref.get("is_nil"))
            is_collective = bool(coref.get("is_collective", False))
            entity_ids = coref.get("entity_ids", [])
            if not isinstance(entity_ids, list) or not all(
                isinstance(item, str) for item in entity_ids
            ):
                audit.error(f"{dataset}/{sid}: entity_ids 必须为字符串列表")
                entity_ids = []
            if is_collective:
                collective_cases += 1
                if is_nil:
                    collective_nil_cases += 1
                    if entity_id is not None or entity_ids:
                        audit.error(f"{dataset}/{sid}: 集合 NIL 必须 entity_id=null 且 entity_ids=[]")
                else:
                    if entity_id is not None:
                        audit.error(f"{dataset}/{sid}: 集合成功结果 entity_id 必须为 null")
                    if len(entity_ids) < 2 or len(entity_ids) != len(set(entity_ids)):
                        audit.error(f"{dataset}/{sid}: 集合结果必须包含至少两个不重复 entity_ids")
                    for expected_id in entity_ids:
                        if expected_id not in local_ids:
                            audit.error(f"{dataset}/{sid}: 集合 entity_id 未在本样本 mentions 中声明: {expected_id}")
            elif is_nil:
                nil_cases += 1
                if entity_id is not None:
                    audit.error(f"{dataset}/{sid}: is_nil=true 但 entity_id 非空")
                if entity_ids:
                    audit.error(f"{dataset}/{sid}: 单实体 NIL 的 entity_ids 必须为空")
            elif entity_id not in local_ids:
                audit.error(f"{dataset}/{sid}: 共指 entity_id 未在本样本 mentions 中声明: {entity_id}")

    audit.summary[dataset] = {
        "contract": DATASET_CONTRACTS[dataset],
        "samples": len(samples),
        "coreference_cases": total_cases,
        "nil_cases": nil_cases,
        "collective_cases": collective_cases,
        "collective_nil_cases": collective_nil_cases,
        "anaphor_surface_count": len(anaphor_surfaces),
    }


def validate_llm_dataset(audit: Audit, kb_ids: set[str], dataset: str) -> None:
    data = load_json(EVAL_DIR / dataset)
    samples = data.get("samples", [])
    prefix = "LLM_AMB" if "ambiguity" in dataset else "LLM_HARD"
    ensure_continuous_ids(audit, dataset, samples, prefix)

    difficulty = Counter()
    nil_count = 0
    for sample in samples:
        sid = sample.get("id", "<missing-id>")
        text = sample.get("text", "")
        mention = sample.get("mention")
        gold = sample.get("gold_entity_id")
        expected_nil = bool(sample.get("expected_nil"))

        check_mention_in_text(audit, dataset, sid, text, mention)
        if expected_nil:
            nil_count += 1
            if gold is not None:
                audit.error(f"{dataset}/{sid}: expected_nil=true 但 gold_entity_id 非空")
        else:
            check_kb_id(audit, dataset, sid, gold, kb_ids, "gold_entity_id")

        for candidate in sample.get("candidate_entity_ids", []):
            check_kb_id(audit, dataset, sid, candidate, kb_ids, "candidate_entity")

        if not sample.get("decisive_evidence"):
            audit.warn(f"{dataset}/{sid}: decisive_evidence 为空，后续 LLM 对比解释性不足")
        difficulty[sample.get("difficulty", "unknown")] += 1

    audit.summary[dataset] = {
        "contract": DATASET_CONTRACTS[dataset],
        "samples": len(samples),
        "nil_samples": nil_count,
        "difficulty": dict(difficulty),
    }


def validate_candidate_or_disamb(audit: Audit, kb_ids: set[str], dataset: str) -> None:
    data = load_json(EVAL_DIR / dataset)
    samples = data.get("samples", [])
    prefix = "CAND" if dataset.startswith("candidate") else "DISAMB"
    actual_with_prefix = [s.get("id") for s in samples if str(s.get("id", "")).startswith(prefix)]
    if actual_with_prefix and len(actual_with_prefix) == len(samples):
        ensure_continuous_ids(audit, dataset, samples, prefix)

    nil_like = 0
    for sample in samples:
        sid = sample.get("id", "<missing-id>")
        text = sample.get("text", "")
        mention = sample.get("mention")
        check_mention_in_text(audit, dataset, sid, text, mention)

        for key in ("gold_entity_id", "gold_entity", "expected_entity_id", "correct_entity"):
            if key in sample and sample.get(key) is not None:
                check_kb_id(audit, dataset, sid, sample.get(key), kb_ids, key)

        for key in ("candidate_entity_ids", "candidate_entities", "expected_candidates", "candidates"):
            values = sample.get(key, [])
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str) and value.startswith("ENT_"):
                        check_kb_id(audit, dataset, sid, value, kb_ids, key)
                    elif isinstance(value, dict):
                        entity_id = value.get("entity_id") or value.get("id")
                        if isinstance(entity_id, str) and entity_id.startswith("ENT_"):
                            check_kb_id(audit, dataset, sid, entity_id, kb_ids, key)

        if sample.get("expected_nil") or sample.get("is_nil") or sample.get("gold_entity_id") is None and sample.get("gold_entity") is None:
            nil_like += 1

    audit.summary[dataset] = {
        "contract": DATASET_CONTRACTS[dataset],
        "samples": len(samples),
        "nil_like_samples": nil_like,
    }


def validate_ner(audit: Audit) -> None:
    dataset = "ner_test_dataset.json"
    data = load_json(EVAL_DIR / dataset)
    samples = data.get("samples", [])
    audit.summary[dataset] = {
        "contract": DATASET_CONTRACTS[dataset],
        "samples": len(samples),
        "note": "NER 数据仅作辅助，不作为课题终稿要求的已识别 mention 主输入。",
    }


def validate_batch(audit: Audit, kb_ids: set[str]) -> None:
    texts_path = DATA_DIR / "batch_texts.txt"
    gt_path = DATA_DIR / "batch_ground_truth.json"
    lines = [line for line in texts_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    data = load_json(gt_path)
    entries = data.get("entries", [])

    if len(lines) != len(entries):
        audit.error(f"batch: 文本数量 {len(lines)} 与标注数量 {len(entries)} 不一致")
    if data.get("total_texts") != len(lines):
        audit.error("batch: total_texts 与文本数量不一致")

    mention_total = 0
    nil_mentions = 0
    for expected_idx, entry in enumerate(entries):
        if entry.get("text_idx") != expected_idx:
            audit.error(f"batch: text_idx 不连续，位置 {expected_idx} 实际 {entry.get('text_idx')}")
            continue

        text = lines[expected_idx] if expected_idx < len(lines) else ""
        expected_entities = entry.get("expected_entities", [])
        expected_nil = any(item.get("entity_id") is None for item in expected_entities)
        if bool(entry.get("has_nil", False)) != expected_nil:
            audit.error(f"batch/{expected_idx}: has_nil 与 expected_entities 不一致")

        for item in expected_entities:
            mention_total += 1
            mention = item.get("mention")
            entity_id = item.get("entity_id")
            check_mention_in_text(audit, "batch_ground_truth.json", str(expected_idx), text, mention)
            if entity_id is None:
                nil_mentions += 1
            else:
                check_kb_id(audit, "batch_ground_truth.json", str(expected_idx), entity_id, kb_ids, "entity_id")

    audit.summary["batch_texts/batch_ground_truth"] = {
        "contract": "批量接口联调与 batch 评测输入",
        "texts": len(lines),
        "entries": len(entries),
        "mentions": mention_total,
        "nil_mentions": nil_mentions,
    }


def build_report(audit: Audit) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": "课题10：实体链接与知识对齐智能体",
        "member_scope": "第三成员欧小红：数据处理与实体链接模块实现",
        "dataset_contracts": DATASET_CONTRACTS,
        "summary": audit.summary,
        "errors": audit.errors,
        "warnings": audit.warnings,
        "passed": not audit.errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate entity-linking evaluation datasets.")
    parser.add_argument("--output", default=str(ROOT / "reports" / "data_quality_audit.json"))
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args()

    audit = Audit()
    kb = load_json(KB_PATH)
    entities = kb.get("entities", [])
    kb_ids = {entity.get("entity_id") for entity in entities}
    audit.summary["knowledge_base"] = {
        "entities": len(entities),
        "entity_types": dict(Counter(entity.get("entity_type", "unknown") for entity in entities)),
        "alias_total": sum(len(entity.get("aliases", [])) for entity in entities),
    }

    validate_eval_dataset(audit, kb_ids)
    validate_mention_linking(audit, kb_ids)
    validate_coreference(audit)
    validate_llm_dataset(audit, kb_ids, "llm_fallback_ambiguity_test.json")
    validate_llm_dataset(audit, kb_ids, "llm_fallback_difficult_cases.json")
    validate_candidate_or_disamb(audit, kb_ids, "candidate_retrieval_test.json")
    validate_candidate_or_disamb(audit, kb_ids, "disambiguation_test.json")
    validate_ner(audit)
    validate_batch(audit, kb_ids)

    report = build_report(audit)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Data quality audit")
    print(f"  output: {output}")
    print(f"  passed: {report['passed']}")
    print(f"  errors: {len(audit.errors)}")
    print(f"  warnings: {len(audit.warnings)}")
    for name, summary in audit.summary.items():
        print(f"  {name}: {summary}")

    if audit.errors or (args.fail_on_warning and audit.warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
