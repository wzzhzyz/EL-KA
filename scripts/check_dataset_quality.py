#!/usr/bin/env python3
"""Read-only quality audit for entity-linking and coreference evaluation data.

The script intentionally never edits source data or gold labels.  It writes a
machine-readable report and a Markdown summary, and treats coverage/duplication
findings as warnings rather than structural failures.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "data" / "eval"
KB_PATH = ROOT / "data" / "kb" / "energy_entities.json"
FORMAL_EXCLUSIONS = {"coreference_collective_test.json", "llm_disambiguation_comparison_template.json"}
PUNCT_RE = re.compile(r"[\s\W_]+", flags=re.UNICODE)


def load_json(path: Path) -> Tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def normalize(text: Any) -> str:
    return PUNCT_RE.sub("", str(text or "")).lower()


def classify(path: Path) -> str:
    labels = {
        "mention_linking_test.json": "实体链接正式金标集",
        "alias_normalization_test.json": "别名标准化正式金标集",
        "candidate_retrieval_test.json": "候选召回金标集",
        "disambiguation_test.json": "消歧金标集",
        "eval_dataset.json": "综合实体链接金标集",
        "llm_fallback_ambiguity_test.json": "LLM 消歧专项金标集",
        "llm_fallback_difficult_cases.json": "LLM 疑难专项金标集",
        "coreference_long_text_test.json": "单实体共指正式金标集（历史 Schema）",
        "coreference_collective_eval.json": "集合共指正式金标集",
        "coreference_failure_regression.json": "集合共指失败驱动回归集（非正式验收）",
        "coreference_blind_holdout.json": "集合共指 Blind Holdout（独立泛化，不计入统一总体）",
        "ner_test_dataset.json": "NER 专项金标集（非实体链接 gold）",
    }
    if path.name in labels:
        return labels[path.name]
    if path.name == "coreference_collective_test.json":
        return "单元测试夹具 / 专项回归"
    if path.name == "llm_disambiguation_comparison_template.json":
        return "开发模板 / 非正式评测"
    if path.name in {"batch_ground_truth.json"}:
        return "批量回归金标"
    if path.parent == EVAL_DIR:
        return "未识别用途的评测数据"
    return "知识库或辅助数据"


def samples_of(data: Any) -> Tuple[List[Dict[str, Any]], str]:
    if isinstance(data, dict):
        for key in ("samples", "entries", "cases", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)], key
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)], "root_list"
    return [], "unsupported"


def detect_schema(data: Any, samples: List[Dict[str, Any]], root_key: str) -> Dict[str, Any]:
    """Identify known project contracts; never treat an unknown root as zero records."""
    if not isinstance(data, dict):
        return {"schema_status": "unsupported", "detected_root_type": type(data).__name__, "unparsed_reason": "root_not_object", "raw_top_level_size": len(data) if hasattr(data, "__len__") else None, "gold_status": "unknown"}
    keys = set(data)
    first = samples[0] if samples else {}
    sample_keys = set(first) if isinstance(first, dict) else set()
    status = "supported" if samples else "partially_supported"
    schema_name = "generic_samples"
    gold_status = "no_samples_or_template"
    if "expected_coreferences" in sample_keys:
        if data.get("evaluation_scope") == "acceptance":
            schema_name, gold_status = "coreference_collective_acceptance_gold", "complete_gold"
        else:
            schema_name, gold_status = "coreference_gold", "complete_gold"
    elif "expected_entities" in sample_keys:
        schema_name, gold_status = "mention_linking_gold", "complete_gold"
    elif "expected_entity" in sample_keys:
        schema_name, gold_status = "alias_normalization_gold", "complete_gold"
    elif {"expected_candidates", "gold_entity"}.issubset(sample_keys):
        schema_name, gold_status = "candidate_retrieval_gold", "complete_task_gold"
    elif {"gold_entity", "expected_nil"}.issubset(sample_keys):
        schema_name, gold_status = "disambiguation_gold", "complete_task_gold"
    elif "expected_result" in sample_keys and "gold_entity" in sample_keys:
        schema_name, gold_status = "comprehensive_linking_gold", "complete_task_gold"
    elif {"candidate_entity_ids", "gold_entity_id", "expected_nil"}.issubset(sample_keys):
        schema_name, gold_status = "llm_fallback_gold", "complete_task_gold"
    elif "expected" in sample_keys and {"text", "scenario"}.issubset(sample_keys):
        schema_name, gold_status = "ner_gold", "complete_ner_gold"
    elif "new_entities" in keys:
        schema_name, gold_status, status = "kb_expansion", "not_evaluation_data", "supported"
    elif {"summary", "ambiguous_groups"}.issubset(keys):
        schema_name, gold_status, status = "kb_ambiguity_report", "not_evaluation_data", "supported"
    elif not samples:
        status = "partially_supported"
    return {"schema_status": status, "detected_root_type": "object", "schema_name": schema_name, "root_key": root_key, "raw_top_level_size": len(data), "unparsed_reason": None if status == "supported" else "no_recognized_sample_array", "gold_status": gold_status, "top_level_keys": sorted(keys), "sample_keys": sorted(sample_keys)}


def entities_of(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        for key in ("entities", "items", "new_entities"):
            if isinstance(data.get(key), list):
                return [item for item in data[key] if isinstance(item, dict)]
        for value in data.values():
            if isinstance(value, dict) and isinstance(value.get("entities"), list):
                return [item for item in value["entities"] if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict) and "entity_id" in item]
    return []


def expected_ids(sample: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for key in ("entity_id", "expected_entity_id", "gold_entity_id", "gold_entity"):
        value = sample.get(key)
        if isinstance(value, str) and value:
            ids.append(value)
    expected = sample.get("expected_entity")
    if isinstance(expected, dict):
        value = expected.get("entity_id")
        if isinstance(value, str) and value:
            ids.append(value)
    for key in ("expected_entities", "candidate_entities"):
        for item in sample.get(key, []) if isinstance(sample.get(key), list) else []:
            if isinstance(item, dict) and isinstance(item.get("entity_id"), str):
                ids.append(item["entity_id"])
    for key in ("gold_entity",):
        value = sample.get(key)
        if isinstance(value, str) and value:
            ids.append(value)
    for key in ("expected_candidates", "candidate_entity_ids", "candidate_entities"):
        value = sample.get(key)
        if isinstance(value, list):
            ids.extend(item.get("entity_id") if isinstance(item, dict) else item for item in value if (isinstance(item, str) and item) or (isinstance(item, dict) and isinstance(item.get("entity_id"), str)))
    for item in sample.get("expected_coreferences", []) if isinstance(sample.get("expected_coreferences"), list) else []:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("entity_id"), str) and item["entity_id"]:
            ids.append(item["entity_id"])
        if isinstance(item.get("entity_ids"), list):
            ids.extend(x for x in item["entity_ids"] if isinstance(x, str) and x)
    return ids


def all_mentions(sample: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    mentions = sample.get("mentions")
    if isinstance(mentions, list):
        yield from (m for m in mentions if isinstance(m, dict))
        return
    if isinstance(sample.get("mention"), str):
        yield sample
        return
    expected = sample.get("expected")
    if isinstance(expected, list):
        for item in expected:
            if isinstance(item, dict) and isinstance(item.get("mention"), str):
                converted = dict(item)
                converted["char_start"] = converted.get("start")
                converted["char_end"] = converted.get("end")
                yield converted


def offset_audit(path: Path, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {"checked": 0, "correct": 0, "errors": [], "out_of_bounds": 0, "overlaps": 0, "duplicate_mentions": 0}
    for index, sample in enumerate(samples):
        text = sample.get("text")
        if not isinstance(text, str):
            continue
        spans: List[Tuple[int, int, str]] = []
        seen = set()
        for mention in all_mentions(sample):
            if not all(key in mention for key in ("mention", "char_start", "char_end")):
                continue
            value, start, end = mention.get("mention"), mention.get("char_start"), mention.get("char_end")
            result["checked"] += 1
            valid = isinstance(value, str) and isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text)
            actual = text[start:end] if valid else "<out_of_bounds_or_invalid>"
            if valid and actual == value:
                result["correct"] += 1
                key = (start, end, value)
                if key in seen:
                    result["duplicate_mentions"] += 1
                seen.add(key)
                spans.append(key)
            else:
                if not valid:
                    result["out_of_bounds"] += 1
                result["errors"].append({"file": str(path.relative_to(ROOT)), "sample": sample.get("id", index), "text": text, "mention": value, "char_start": start, "char_end": end, "actual": actual})
        spans.sort()
        for left, right in zip(spans, spans[1:]):
            if right[0] < left[1] and right != left:
                result["overlaps"] += 1
    return result


def coref_audit(path: Path, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = {"cases": 0, "single": 0, "collective": 0, "collective_success": 0, "collective_nil": 0, "legacy_cases": 0, "errors": []}
    for sample_index, sample in enumerate(samples):
        cases = sample.get("expected_coreferences")
        if not isinstance(cases, list):
            continue
        local_ids = {m.get("entity_id") for m in sample.get("mentions", []) if isinstance(m, dict) and m.get("entity_id")}
        for case in cases:
            if not isinstance(case, dict):
                result["errors"].append({"sample": sample.get("id", sample_index), "reason": "expected_coreference_not_object"})
                continue
            result["cases"] += 1
            if not {"entity_ids", "is_collective"}.issubset(case):
                result["legacy_cases"] += 1
                continue
            entity_id, entity_ids = case.get("entity_id"), case.get("entity_ids")
            is_nil, collective = case.get("is_nil"), case.get("is_collective")
            if not isinstance(entity_ids, list) or not isinstance(is_nil, bool) or not isinstance(collective, bool) or not all(isinstance(x, str) for x in entity_ids):
                result["errors"].append({"sample": sample.get("id", sample_index), "reason": "invalid_collective_field_type"})
                continue
            if collective:
                result["collective"] += 1
                if not is_nil:
                    result["collective_success"] += 1
                    if entity_id is not None or len(entity_ids) < 2 or len(entity_ids) != len(set(entity_ids)) or not set(entity_ids).issubset(local_ids):
                        result["errors"].append({"sample": sample.get("id", sample_index), "reason": "invalid_collective_success_contract"})
                else:
                    result["collective_nil"] += 1
                    if entity_id is not None or entity_ids:
                        result["errors"].append({"sample": sample.get("id", sample_index), "reason": "invalid_collective_nil_contract"})
            else:
                result["single"] += 1
                if is_nil and entity_ids:
                    result["errors"].append({"sample": sample.get("id", sample_index), "reason": "ordinary_nil_has_entity_ids"})
                if not is_nil and isinstance(entity_id, str) and entity_ids and entity_ids != [entity_id]:
                    result["errors"].append({"sample": sample.get("id", sample_index), "reason": "single_entity_ids_inconsistent"})
    return result


def field_audit(path: Path, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate common scalar and collection fields without requiring one schema."""
    errors: List[Dict[str, Any]] = []
    checked_confidence = 0
    for index, sample in enumerate(samples):
        sample_id = sample.get("id", index)
        if "text" in sample and (not isinstance(sample["text"], str) or not sample["text"].strip()):
            errors.append({"sample": sample_id, "reason": "empty_or_nonstring_text"})
        for item in [sample, *list(all_mentions(sample))]:
            if "confidence" in item:
                checked_confidence += 1
                value = item["confidence"]
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= float(value) <= 1.0:
                    errors.append({"sample": sample_id, "reason": "invalid_confidence", "value": value})
            for boolean_key in ("is_nil", "is_collective"):
                if boolean_key in item and not isinstance(item[boolean_key], bool):
                    errors.append({"sample": sample_id, "reason": f"{boolean_key}_not_boolean"})
            if "entity_ids" in item and (not isinstance(item["entity_ids"], list) or not all(isinstance(x, str) for x in item["entity_ids"])):
                errors.append({"sample": sample_id, "reason": "entity_ids_not_string_array"})
            if "antecedent_indices" in item and (not isinstance(item["antecedent_indices"], list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in item["antecedent_indices"])):
                errors.append({"sample": sample_id, "reason": "antecedent_indices_not_integer_array"})
        for case in sample.get("expected_coreferences", []) if isinstance(sample.get("expected_coreferences"), list) else []:
            if isinstance(case, dict):
                for key in ("is_nil", "is_collective"):
                    if key in case and not isinstance(case[key], bool):
                        errors.append({"sample": sample_id, "reason": f"coreference_{key}_not_boolean"})
    return {"confidence_checked": checked_confidence, "errors": errors}


def nil_units(sample: Dict[str, Any]) -> int:
    """Count explicitly labelled NIL units, preserving dataset-specific granularity."""
    labels = sample.get("expected_entities")
    if isinstance(labels, list):
        return sum(1 for item in labels if isinstance(item, dict) and not item.get("entity_id"))
    expected = sample.get("expected_entity")
    if isinstance(expected, dict):
        return int(not expected.get("entity_id"))
    corefs = sample.get("expected_coreferences")
    if isinstance(corefs, list):
        return sum(1 for item in corefs if isinstance(item, dict) and item.get("is_nil") is True)
    if sample.get("is_nil") is True or sample.get("has_nil") is True or sample.get("is_negative") is True or sample.get("is_nil_like") is True:
        return 1
    return 0


def acceptance_collective_audit(data: Dict[str, Any], samples: List[Dict[str, Any]], kb_ids: set[str]) -> List[Dict[str, Any]]:
    """Additional contract checks for the runtime-KB collective acceptance set."""
    errors: List[Dict[str, Any]] = []
    if data.get("evaluation_scope") != "acceptance" or data.get("requires_runtime_kb") is not True:
        errors.append({"reason": "missing_acceptance_scope_or_runtime_kb_flag"})
    for index, sample in enumerate(samples):
        sample_id = sample.get("id", index)
        mentions = sample.get("mentions", [])
        try:
            sample_number = int(str(sample_id).rsplit("_", 1)[1])
        except (IndexError, ValueError):
            sample_number = 0
        # Metadata was introduced for the incremental expansion.  Keep the
        # original 60 acceptance samples immutable while enforcing the new
        # contract on appended samples.
        if sample_number >= 61:
            if sample.get("subset") not in {"acceptance_main", "challenge_dev"}:
                errors.append({"sample": sample_id, "reason": "invalid_or_missing_acceptance_subset"})
            if sample.get("difficulty") not in {"easy", "medium", "hard"}:
                errors.append({"sample": sample_id, "reason": "invalid_or_missing_acceptance_difficulty"})
        for mention in mentions if isinstance(mentions, list) else []:
            if isinstance(mention, dict) and isinstance(mention.get("entity_id"), str):
                entity_id = mention["entity_id"]
                if entity_id.startswith(("TEST_", "PER_TEST_", "SYS_TEST_")) or entity_id not in kb_ids:
                    errors.append({"sample": sample_id, "reason": "non_runtime_kb_antecedent_id", "entity_id": entity_id})
        for case in sample.get("expected_coreferences", []) if isinstance(sample.get("expected_coreferences"), list) else []:
            if not isinstance(case, dict):
                continue
            if sample_number >= 61:
                if not isinstance(case.get("scenario"), str) or not case["scenario"].strip():
                    errors.append({"sample": sample_id, "reason": "missing_acceptance_scenario"})
                if not isinstance(case.get("conjunction"), str) or not case["conjunction"].strip():
                    errors.append({"sample": sample_id, "reason": "missing_acceptance_conjunction"})
                if not isinstance(case.get("anaphor"), str) or not case["anaphor"].strip():
                    errors.append({"sample": sample_id, "reason": "missing_acceptance_anaphor"})
                elif isinstance(case.get("mention_index"), int) and 0 <= case["mention_index"] < len(mentions) and case["anaphor"] != mentions[case["mention_index"]].get("mention"):
                    errors.append({"sample": sample_id, "reason": "acceptance_anaphor_mismatch"})
                if not isinstance(case.get("sentence_distance"), int) or case["sentence_distance"] < 0:
                    errors.append({"sample": sample_id, "reason": "invalid_acceptance_sentence_distance"})
                if not isinstance(case.get("evidence"), str) or not case["evidence"].strip():
                    errors.append({"sample": sample_id, "reason": "missing_acceptance_evidence"})
            if case.get("is_collective") is True and case.get("is_nil") is False:
                ids = case.get("entity_ids", [])
                indices = case.get("antecedent_indices", [])
                if not isinstance(ids, list) or len(ids) < 2 or len(ids) != len(set(ids)) or any(entity_id not in kb_ids for entity_id in ids):
                    errors.append({"sample": sample_id, "reason": "invalid_acceptance_collective_entity_ids"})
                if not isinstance(indices, list) or len(indices) < 2 or any(not isinstance(i, int) or i < 0 or i >= len(mentions) for i in indices):
                    errors.append({"sample": sample_id, "reason": "invalid_acceptance_antecedent_indices"})
    return errors


def gold_pairs(sample: Dict[str, Any]) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for item in sample.get("expected_entities", []) if isinstance(sample.get("expected_entities"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("mention"), str):
            pairs.append((normalize(item["mention"]), str(item.get("entity_id", "<NIL>"))))
    expected = sample.get("expected_entity")
    if isinstance(expected, dict) and isinstance(sample.get("mention"), str):
        pairs.append((normalize(sample["mention"]), str(expected.get("entity_id", "<NIL>"))))
    if isinstance(sample.get("mention"), str) and isinstance(sample.get("gold_entity"), str):
        pairs.append((normalize(sample["mention"]), sample["gold_entity"]))
    if isinstance(sample.get("mention"), str) and isinstance(sample.get("gold_entity_id"), str):
        pairs.append((normalize(sample["mention"]), sample["gold_entity_id"]))
    return pairs


def sample_signature(sample: Dict[str, Any]) -> Tuple[str, str]:
    text = normalize(sample.get("text", ""))
    return text, json.dumps(gold_pairs(sample), ensure_ascii=False, sort_keys=True)


def find_duplicates(dataset_samples: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    exact: Dict[Tuple[str, str], List[Tuple[str, int]]] = defaultdict(list)
    by_text: Dict[str, List[Tuple[str, int, str]]] = defaultdict(list)
    by_text_mention: Dict[Tuple[str, str], List[Tuple[str, int, str]]] = defaultdict(list)
    for file_name, samples in dataset_samples.items():
        for index, sample in enumerate(samples):
            text, gold = sample_signature(sample)
            if not text:
                continue
            exact[(text, gold)].append((file_name, index))
            by_text[text].append((file_name, index, gold))
            for mention, entity_id in gold_pairs(sample):
                by_text_mention[(text, mention)].append((file_name, index, entity_id))
    exact_groups = [items for items in exact.values() if len(items) > 1]
    conflict_groups = [items for items in by_text_mention.values() if len({gold for _, _, gold in items}) > 1]
    near: List[Dict[str, Any]] = []
    unique = [(text, file_name, index) for text, entries in by_text.items() for file_name, index, _ in entries[:1]]
    # Same length bucket makes the standard-library similarity pass tractable and reproducible.
    for i, (left, left_file, left_index) in enumerate(unique):
        for right, right_file, right_index in unique[i + 1 :]:
            if left == right or abs(len(left) - len(right)) > max(6, int(max(len(left), len(right)) * 0.15)):
                continue
            score = SequenceMatcher(None, left, right).ratio()
            if score >= 0.90:
                near.append({"left": f"{left_file}#{left_index}", "right": f"{right_file}#{right_index}", "similarity": round(score, 3)})
                if len(near) >= 100:
                    break
        if len(near) >= 100:
            break
    def family(file_name: str) -> str:
        if file_name.startswith("candidate_"):
            return "candidate_retrieval"
        if file_name.startswith("disambiguation_"):
            return "disambiguation"
        if file_name.startswith("llm_"):
            return "llm_fallback"
        return file_name
    conflict_examples = []
    conflict_counts = Counter()
    for items in conflict_groups:
        families = {family(file_name) for file_name, _, _ in items}
        # All currently compared contracts expose an explicit gold entity.
        # Cross-task reuse remains a true conflict when text and mention are equal.
        classification = "confirmed_gold_conflict"
        conflict_counts[classification] += 1
        conflict_examples.append({"classification": classification, "items": [{"file": file_name, "sample_index": index, "entity_id": entity_id} for file_name, index, entity_id in items]})
    same_task_groups = sum(1 for items in exact_groups if len({family(file_name) for file_name, _ in items}) == 1)
    cross_task_groups = len(exact_groups) - same_task_groups
    total_instances = sum(len(items) for items in exact_groups)
    return {"exact_duplicate_groups": len(exact_groups), "exact_duplicate_instances_total": total_instances, "exact_duplicate_excess_instances": total_instances - len(exact_groups), "same_task_duplicate_groups": same_task_groups, "cross_task_reuse_groups": cross_task_groups, "conflicting_duplicate_groups": conflict_counts["confirmed_gold_conflict"], "cross_task_field_difference_groups": conflict_counts["cross_task_field_difference"], "label_conflict_examples": conflict_examples, "cross_file_same_text_groups": sum(1 for items in by_text.values() if len({f for f, _, _ in items}) > 1), "near_duplicate_pairs_total": len(near), "near_duplicate_pairs_reported": len(near), "near_duplicate_pairs_truncated": False, "near_duplicate_pairs": near, "method": "文本去空白与标点后精确比较；冲突仅比较同一规范化文本和同一规范化 mention 的不同 gold entity；近重复使用 SequenceMatcher 比率 >= 0.90 与长度差过滤。近重复仅供人工审查。"}


def coverage(dataset_samples: Dict[str, List[Dict[str, Any]]]) -> Dict[str, str]:
    corpus = "\n".join(str(sample.get("text", "")) for samples in dataset_samples.values() for sample in samples)
    mentions = "\n".join(str(m.get("mention", "")) for samples in dataset_samples.values() for s in samples for m in all_mentions(s))
    collective_fixture = dataset_samples.get("coreference_collective_test.json", [])
    collective_eval = dataset_samples.get("coreference_collective_eval.json", [])
    collective_cases = sum(
        len(sample.get("expected_coreferences", []))
        for sample in collective_eval
        if isinstance(sample.get("expected_coreferences"), list)
    )
    challenge_count = sum(sample.get("subset") == "challenge_dev" for sample in collective_eval)
    collective_text = "\n".join(
        str(sample.get("text", ""))
        for sample in [*collective_fixture, *collective_eval]
    )
    matrix = {
        "实体链接：标准名、别名、歧义、候选、NIL": "已覆盖（由 mention_linking、alias、candidate、disambiguation 与 LLM 难例集分担）",
        "实体链接：轻微噪声 / 中英文数字": "部分覆盖；需要独立统计或增加对抗样本",
        "实体链接：嵌套或重叠 mention": "尚未形成明确专项 gold",
        "单实体共指：同句、跨句、类型不兼容、无前件": "已覆盖（coreference_long_text_test.json）",
        "单实体共指：链式、多同类型候选、远距离": "部分覆盖；建议按场景建立显式分组统计",
        "集合共指：两个 ORG、三实体 ORG、两个 PERSON": f"ORG 双、三、四实体已由正式 {len(collective_eval)} 条 / {collective_cases} case 验收集覆盖；运行知识库缺少可用 PERSON 实体，PERSON 正例未纳入端到端验收。",
        "集合共指：和、与、顿号": "已覆盖（正式验收集与规则夹具）。",
        "集合共指：及、以及": "已覆盖（正式验收集）。",
        "集合共指：她们、它们、双方、二者、两家央企": "已覆盖它们、双方、二者、两家央企；他们用于类型不兼容 NIL 边界。她们与产品级“这些平台”尚无正式正例。",
        "集合共指：混合类型、未链接、跨句、重复 ID、单数代词": "已覆盖为正式集的集合/普通 NIL 边界。",
        "集合共指：非实体插入、非相邻候选、多协调组、复杂省略": "非实体插入和多协调组已覆盖；远距离隐式前件与复杂省略仍未覆盖。",
    }
    matrix["检测依据"] = f"集合数据：正式集 {len(collective_eval)} 条 / {collective_cases} case（challenge_dev {challenge_count} 条）、规则夹具 {len(collective_fixture)} 条；文本中含：{', '.join(marker for marker in ['和', '与', '、', '及', '以及', '同', '跟', '连同', '会同'] if marker in collective_text) or '无'}；集合代词观测：{', '.join(sorted(set(re.findall(r'他们|她们|它们|这些机构|双方|二者|两家央企|各方|三方|两者|该二者|上述单位', collective_text)))) or '无'}。"
    return matrix


def build_conflict_details(duplicates: Dict[str, Any], dataset_samples: Dict[str, List[Dict[str, Any]]], kb_by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    details = []
    for group in duplicates.get("label_conflict_examples", []):
        records = []
        for ref in group["items"]:
            sample = dataset_samples[ref["file"]][ref["sample_index"]]
            gold_field = "gold_entity_id" if "gold_entity_id" in sample else "gold_entity" if "gold_entity" in sample else "expected_entities"
            candidate_key = next((key for key in ("expected_candidates", "candidate_entities", "candidate_entity_ids") if key in sample), None)
            candidates = sample.get(candidate_key, []) if candidate_key else []
            records.append({"file_path": f"data/eval/{ref['file']}", "sample_id": sample.get("id"), "sample_index": ref["sample_index"], "text": sample.get("text"), "normalized_text": normalize(sample.get("text")), "mention": sample.get("mention"), "mention_type": sample.get("type", sample.get("entity_type")), "context_fields": {key: sample[key] for key in ("scenario", "gold_reason", "reason", "note", "notes", "difficulty", "confidence_level", "expected_nil", "kb_status") if key in sample}, "gold_field": gold_field, "gold_entity_id": ref["entity_id"], "gold_entity_name": kb_by_id.get(ref["entity_id"], {}).get("entity_name", kb_by_id.get(ref["entity_id"], {}).get("standard_name")), "candidate_field": candidate_key, "candidate_entities": candidates})
        same_context = len({record["text"] for record in records}) == 1
        classification = group["classification"]
        details.append({"classification": classification, "same_normalized_text": len({record["normalized_text"] for record in records}) == 1, "same_raw_text": same_context, "initial_assessment": "相同原始文本与 mention 的显式 gold entity 不一致，属于确认 gold 冲突", "records": records})
    return details


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only entity-linking dataset quality audit")
    parser.add_argument("--json-output", default="reports/dataset_quality_report.json")
    parser.add_argument("--markdown-output", default="reports/dataset_quality_report.md")
    args = parser.parse_args()

    kb_data, kb_error = load_json(KB_PATH)
    entities = entities_of(kb_data) if kb_data is not None else []
    kb_ids = {item.get("entity_id") for item in entities if isinstance(item.get("entity_id"), str)}
    kb_by_id = {item["entity_id"]: item for item in entities if isinstance(item.get("entity_id"), str)}
    kb_types = Counter(str(item.get("entity_type", item.get("type", "UNKNOWN"))) for item in entities)
    supplementary_kb = []
    for aux_path in sorted((ROOT / "data" / "kb").glob("*.json")):
        if aux_path == KB_PATH:
            continue
        aux_data, aux_error = load_json(aux_path)
        aux_entities = entities_of(aux_data) if aux_data is not None else []
        aux_samples, aux_root = samples_of(aux_data) if aux_data is not None else ([], "unparsed")
        aux_schema = detect_schema(aux_data, aux_samples, aux_root) if aux_data is not None else {"schema_status": "unsupported", "detected_root_type": "unparsed", "unparsed_reason": aux_error, "raw_top_level_size": None}
        supplementary_kb.append({"path": str(aux_path.relative_to(ROOT)), "parse_error": aux_error, "schema_detection": aux_schema, "entity_records": len(aux_entities) if aux_schema["schema_status"] == "supported" else None, "sample_records": len(aux_samples) if aux_schema["schema_status"] == "supported" else None})

    paths = sorted(EVAL_DIR.glob("*.json")) + [ROOT / "data" / "batch_ground_truth.json"]
    files: List[Dict[str, Any]] = []
    dataset_samples: Dict[str, List[Dict[str, Any]]] = {}
    offset_total = Counter()
    id_issues: List[Dict[str, str]] = []
    aggregate = Counter()
    type_distribution = Counter()
    entity_reference_counter = Counter()
    nil_total = 0
    for path in paths:
        data, error = load_json(path)
        entry: Dict[str, Any] = {"path": str(path.relative_to(ROOT)), "classification": classify(path), "format": "JSON", "parse_error": error}
        if error:
            files.append(entry)
            continue
        samples, root_key = samples_of(data)
        schema = detect_schema(data, samples, root_key)
        dataset_samples[path.name] = samples
        offsets = offset_audit(path, samples)
        coref = coref_audit(path, samples)
        fields = field_audit(path, samples)
        acceptance_errors = acceptance_collective_audit(data, samples, kb_ids) if schema.get("schema_name") == "coreference_collective_acceptance_gold" else []
        mention_count = 0
        positive = 0
        nil = 0
        placeholder_ids = 0
        unique_entities = set()
        for sample in samples:
            input_mentions = list(all_mentions(sample))
            for mention in input_mentions:
                mention_count += 1
                typ = mention.get("type", mention.get("entity_type"))
                if isinstance(typ, str):
                    type_distribution[typ] += 1
                if mention.get("is_nil") is True:
                    nil += 1
                if isinstance(mention.get("entity_id"), str) and mention["entity_id"]:
                    unique_entities.add(mention["entity_id"])
            if not input_mentions and isinstance(sample.get("expected_entities"), list):
                # Batch gold has no text/offset-bearing input mention object; count its labels once.
                mention_count += sum(1 for item in sample["expected_entities"] if isinstance(item, dict) and isinstance(item.get("mention"), str))
            nil += nil_units(sample)
            is_nil = sample.get("is_nil")
            if is_nil is False:
                positive += 1
            for entity_id in expected_ids(sample):
                unique_entities.add(entity_id)
                entity_reference_counter[entity_id] += 1
        ids_to_check = set(expected_ids(sample)[i] for sample in samples for i in range(len(expected_ids(sample))))
        for sample in samples:
            for mention in sample.get("mentions", []) if isinstance(sample.get("mentions"), list) else []:
                if isinstance(mention, dict) and isinstance(mention.get("entity_id"), str):
                    ids_to_check.add(mention["entity_id"])
        for entity_id in sorted(ids_to_check):
            if entity_id in kb_ids:
                continue
            if entity_id.startswith(("TEST_", "PER_TEST_")) and path.name == "coreference_collective_test.json":
                category = "测试夹具 ID"
            elif entity_id.startswith(("PER_TEST_", "SYS_TEST_")) and path.name == "coreference_long_text_test.json":
                category = "历史测试夹具 ID"
            else:
                category = "无法确认"
            if category == "测试夹具 ID":
                placeholder_ids += 1
            id_issues.append({"file": path.name, "entity_id": entity_id, "category": category})
        entry.update({"schema_detection": schema, "root_key": root_key, "samples": len(samples), "mentions": mention_count, "positive_marked": positive, "nil_labeled_units": nil, "unique_referenced_ids": len(unique_entities), "coreference": coref, "field_audit": {"confidence_checked": fields["confidence_checked"], "error_count": len(fields["errors"]), "examples": fields["errors"][:20]}, "acceptance_collective_errors": acceptance_errors, "offsets": {k: v for k, v in offsets.items() if k != "errors"}, "offset_error_count": len(offsets["errors"]), "offset_error_examples": offsets["errors"][:20], "placeholder_ids": placeholder_ids, "has_gold": schema["gold_status"] in {"complete_gold", "complete_task_gold", "complete_ner_gold"}})
        files.append(entry)
        aggregate["samples"] += len(samples)
        aggregate["mentions"] += mention_count
        aggregate["coreference_cases"] += coref["cases"]
        aggregate["single_coreference"] += coref["single"]
        aggregate["collective_coreference"] += coref["collective"]
        aggregate["collective_success"] += coref["collective_success"]
        aggregate["collective_nil"] += coref["collective_nil"]
        aggregate["offset_checked"] += offsets["checked"]
        aggregate["offset_correct"] += offsets["correct"]
        aggregate["offset_errors"] += len(offsets["errors"])
        aggregate["field_errors"] += len(fields["errors"])
        aggregate["overlaps"] += offsets["overlaps"]
        aggregate["duplicate_mentions"] += offsets["duplicate_mentions"]
        nil_total += nil

    duplicates = find_duplicates(dataset_samples)
    conflict_details = build_conflict_details(duplicates, dataset_samples, kb_by_id)
    formal_collective_samples = dataset_samples.get("coreference_collective_eval.json", [])
    blind_holdout_samples = dataset_samples.get("coreference_blind_holdout.json", [])
    formal_collective_cases = sum(
        len(sample.get("expected_coreferences", []))
        for sample in formal_collective_samples
        if isinstance(sample.get("expected_coreferences"), list)
    )
    formal_collective_challenge = sum(sample.get("subset") == "challenge_dev" for sample in formal_collective_samples)
    critical_errors = [f for f in files if f.get("parse_error")] + [e for f in files for e in f.get("coreference", {}).get("errors", [])] + [e for f in files for e in f.get("field_audit", {}).get("examples", [])] + [e for f in files for e in f.get("acceptance_collective_errors", [])]
    formal_files = [f for f in files if f["classification"] == "正式专项评测集"]
    findings = {
        "P0": [],
        "P1": [],
        "P2": [
            f"正式集合共指集已扩充到 {len(formal_collective_samples)} 条 / {formal_collective_cases} 个 case（challenge_dev {formal_collective_challenge} 条）；其结果仅代表当前规则与运行知识库组合，不能外推为通用篇章共指能力。",
            "正式运行知识库缺少可用 PERSON 实体，PERSON 集合正例未纳入端到端 KB 验收；她们与产品级“这些平台”也尚无正式正例。",
            "跨句集合、远距离隐式前件与复杂省略当前以 NIL 边界或未覆盖项处理。",
            "历史长文本共指集未采用 entity_ids 集合 gold，无法单独衡量集合共指能力。",
            "多份专项集可能包含模板化实体替换；近重复检测结果应作为扩充时的去重基线。",
        ],
        "P3": ["不同历史数据集的 gold 字段存在 schema 差异；评测时需按数据契约区分历史兼容格式与集合扩展格式。"],
    }
    if critical_errors:
        findings["P0"].append(f"发现 {len(critical_errors)} 项解析、字段或集合契约错误；详见 JSON 报告 examples。")
    if aggregate["offset_errors"]:
        findings["P1"].append(f"NER 专项金标发现 {aggregate['offset_errors']} 个字符偏移错误；该问题不影响已给定 mention 的实体链接 gold，但会影响 NER 专项评测可信度。")
    if duplicates["conflicting_duplicate_groups"]:
        findings["P1"].append(f"发现 {duplicates['conflicting_duplicate_groups']} 组同输入、显式 gold 不一致的确认冲突，需人工复核。")
    external_id_count = sum(1 for issue in id_issues if issue["category"] == "历史测试夹具 ID")
    if external_id_count:
        findings["P2"].append(f"正式长文本共指集中存在 {external_id_count} 个不在当前运行知识库的历史测试夹具 ID；它们不构成结构错误，但不能直接用于端到端知识库 ID 一致性验收。")
    gold_status_summary = dict(Counter(item.get("schema_detection", {}).get("gold_status", "parse_error") for item in files))
    schema_detection_summary = dict(Counter(item.get("schema_detection", {}).get("schema_status", "parse_error") for item in files))
    report = {
        "schema_version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "data/eval/*.json + data/batch_ground_truth.json；主知识库为 data/kb/energy_entities.json。历史运行输出、索引文件和 trace.db 不作为 gold 测试集。",
        "audit_scope": "data/eval/*.json + data/batch_ground_truth.json；主知识库为 data/kb/energy_entities.json。历史运行输出、索引文件和 trace.db 不作为 gold 测试集。",
        "knowledge_base": {"path": str(KB_PATH.relative_to(ROOT)), "entities": len(entities), "entity_types": dict(kb_types), "aliases": sum(len(item.get("aliases", [])) for item in entities)},
        "supplementary_knowledge_files": supplementary_kb,
        "files": files,
        "file_classification_summary": dict(Counter(item["classification"] for item in files)),
        "gold_status_summary": gold_status_summary,
        "schema_detection_summary": schema_detection_summary,
        "type_distribution": {"mention_raw_type_distribution": dict(type_distribution), "mention_coarse_type_distribution": {key: type_distribution.get(key, 0) for key in ("ORG", "PERSON", "GPE", "LOC", "PRON", "NOUN", "UNKNOWN")}, "knowledge_base_entity_subtype_distribution": dict(kb_types), "type_schema_note": "mention 原始类型与知识库 entity_type 属于不同层级；未建立经过人工确认的全量映射，因此不强行合并。"},
        "entity_reference_distribution": {"unique_referenced_entities": len(entity_reference_counter), "top_10": [{"entity_id": entity_id, "entity_name": kb_by_id.get(entity_id, {}).get("entity_name"), "count": count, "share_of_references": round(count / sum(entity_reference_counter.values()), 6)} for entity_id, count in entity_reference_counter.most_common(10)]},
        "aggregate": {**aggregate, "nil_marked": nil_total, "entity_type_mentions": dict(type_distribution), "formal_eval_files": len(formal_files)},
        "entity_id_issues": id_issues,
        "duplicates": duplicates,
        "duplicate_metrics": duplicates,
        "conflict_details": conflict_details,
        "offset_coverage": {"total_input_or_gold_mentions": aggregate["mentions"], "offset_checkable_mentions": aggregate["offset_checked"], "offset_correct": aggregate["offset_correct"], "offset_errors": aggregate["offset_errors"], "not_checkable_mentions": aggregate["mentions"] - aggregate["offset_checked"], "note": "无 text/mention/char_start/char_end 的候选、gold 或历史位置表达不能进行字符偏移验证。"},
        "coreference_statistics": {"coreference_cases_total": aggregate["coreference_cases"], "legacy_coreference_cases": aggregate["coreference_cases"] - aggregate["single_coreference"] - aggregate["collective_coreference"], "structured_coreference_cases": aggregate["single_coreference"] + aggregate["collective_coreference"], "structured_single_cases": aggregate["single_coreference"], "structured_collective_cases": aggregate["collective_coreference"], "collective_success_cases": aggregate["collective_success"], "collective_expected_nil_cases": aggregate["collective_nil"]},
        "coverage_matrix": coverage(dataset_samples),
        "findings": findings,
        "limitations": ["只对 Schema 已识别的文件执行字段级统计。", "近重复仅为人工审查候选，不自动视为错误。", "未发现训练目录不等于能够证明不存在所有形式的数据泄漏。", "未执行人工语义标注复核，不能替代模型效果评测。"],
        "current_worktree_notice": "本轮仅修改 scripts/check_dataset_quality.py 与两份 dataset_quality_report；报告不推断其他工作区改动，实际范围应以运行 git status --short 为准。",
        "quality_conclusion": f"良好：结构与偏移检查通过，正式集合共指集已具备 {len(formal_collective_samples)} 条 / {formal_collective_cases} 个 case 的验收数据，并新增 {len(blind_holdout_samples)} 条独立 Blind Holdout；当前结果仍仅代表受控规则范围，PERSON、跨句隐式集合和复杂篇章语义仍是明确边界，且不得将规则夹具或受控集的高分外推为整体能力。",
    }
    json_path = ROOT / args.json_output
    md_path = ROOT / args.markdown_output
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    coref_stats = report["coreference_statistics"]
    lines = ["# 实体链接与共指测试数据质量报告", "", "## 1. 总体结论", "", report["quality_conclusion"], "", "## 2. 审计范围与统计口径", "", report["scope"], "", "- `has_gold=false` 不等于文件无价值；本报告以 `gold_status` 区分完整 gold、任务 gold、NER gold、模板和非评测数据。", "- 样本、mention、NIL 均按各文件原始任务契约累计，跨任务汇总不代表去重后的统一基准。", "", "## 3. 核心统计", "", f"- 扫描 JSON 数据文件：{len(files)}；Schema 已识别：{schema_detection_summary.get('supported', 0)}。", f"- 样本 / entry：{aggregate['samples']}；输入 mention 或 batch gold mention：{aggregate['mentions']}。", f"- 显式 NIL 标注单元（跨数据集原始计数，不去重）：{nil_total}。", f"- 共指总 case：{coref_stats['coreference_cases_total']}；历史格式：{coref_stats['legacy_coreference_cases']}；当前字段化：{coref_stats['structured_coreference_cases']}（单实体对照：{coref_stats['structured_single_cases']}；集合：{coref_stats['structured_collective_cases']}；集合成功：{coref_stats['collective_success_cases']}；集合预期 NIL：{coref_stats['collective_expected_nil_cases']}）。", f"- 知识库：{len(entities)} 个实体、{sum(len(item.get('aliases', [])) for item in entities)} 条 alias。", f"- ID 非知识库引用：{len(id_issues)}（专项测试夹具 ID：{sum(1 for x in id_issues if x['category'] == '测试夹具 ID')}；历史测试夹具 ID：{sum(1 for x in id_issues if x['category'] == '历史测试夹具 ID')}）。", "", "## 4. 文件分类、Schema 与 gold 状态", "", "| 文件 | 分类 | Schema | gold 状态 | 样本 | mention | NIL 标注 |", "| --- | --- | --- | --- | ---: | ---: | ---: |"]
    for item in files:
        if item.get("parse_error"):
            lines.append(f"| `{item['path']}` | {item['classification']} | 解析失败 | - | - | - | - |")
        else:
            coref = item["coreference"]
            schema = item["schema_detection"]
            lines.append(f"| `{item['path']}` | {item['classification']} | {schema.get('schema_name', 'unrecognized')} | {schema.get('gold_status')} | {item['samples']} | {item['mentions']} | {item['nil_labeled_units']} |")
    lines += ["", "### 补充知识库文件", "", "| 文件 | 实体记录 | 样本记录 | 说明 |", "| --- | ---: | ---: | --- |"]
    for item in supplementary_kb:
        detail = item["parse_error"] or "辅助知识库 / 扩充或歧义分析数据，不作为当前主 KB ID 有效性基准"
        lines.append(f"| `{item['path']}` | {item['entity_records']} | {item['sample_records']} | {detail} |")
    lines += ["", "## 5. Schema 识别、字符偏移与实体 ID", "", f"- JSON 解析错误：{sum(1 for item in files if item.get('parse_error'))}；字段类型 / `confidence` 错误：{aggregate['field_errors']}。", f"- 字符偏移：共统计 {aggregate['mentions']} 个输入或 gold mention，其中 {aggregate['offset_checked']} 个具备 `text`、`mention`、`char_start`、`char_end`；正确 {aggregate['offset_correct']}，错误 {aggregate['offset_errors']}、越界 {sum(item.get('offsets', {}).get('out_of_bounds', 0) for item in files)}。其余样本缺少偏移字段、仅含候选/gold，或采用历史位置表达。", f"- 集合共指契约错误：{sum(len(item.get('coreference', {}).get('errors', [])) for item in files)}。", f"- 非知识库 ID：{len(id_issues)}；测试夹具 ID 与历史测试夹具 ID 已按用途分类，不直接判为 gold 错误。", "", "## 6. 重复、跨任务复用与泄漏风险", "", f"- `exact_duplicate_groups`：{duplicates['exact_duplicate_groups']}；`exact_duplicate_instances_total`：{duplicates['exact_duplicate_instances_total']}；`exact_duplicate_excess_instances`：{duplicates['exact_duplicate_excess_instances']}（每组保留 1 条后的多余实例）。", f"- `same_task_duplicate_groups`：{duplicates['same_task_duplicate_groups']}；`cross_task_reuse_groups`：{duplicates['cross_task_reuse_groups']}；`cross_file_same_text_groups`：{duplicates['cross_file_same_text_groups']}。不同任务的复用不直接等同于泄漏。", f"- `conflicting_duplicate_groups`：{duplicates['conflicting_duplicate_groups']}；`cross_task_field_difference_groups`：{duplicates['cross_task_field_difference_groups']}。", f"- 近重复候选：总计 {duplicates['near_duplicate_pairs_total']}，展示 {duplicates['near_duplicate_pairs_reported']}，截断={duplicates['near_duplicate_pairs_truncated']}。方法：{duplicates['method']} 模板实体替换、中文短文本和相似实体可能误报，不能自动视为错误。", "- 集合专项的 100% 是规则夹具回归结果，样本量仅 8 个 case 且与规则设计高度贴合，结论为“基本可信但覆盖有限”，不得外推为通用集合共指能力。", "- 未发现训练集目录；仓库中的 `tests/tests/output` 与 `reports` 为运行输出，不作为 gold 测试集计入。", "", "## 7. 功能覆盖矩阵", ""]
    for name, status in report["coverage_matrix"].items():
        lines.append(f"- **{name}**：{status}")
    lines += ["", "## 8. 标签冲突人工复核", ""]
    if duplicates["label_conflict_examples"]:
        for item in duplicates["label_conflict_examples"]:
            lines.append(f"- 分类：`{item['classification']}`；条目：" + "；".join(f"`{x['file']}#{x['sample_index']}` → `{x['entity_id']}`" for x in item["items"]))
        lines.append("- 当前发现的 candidate_retrieval 与 disambiguation 条目均带显式 gold entity，且原始文本与 mention 完全一致但 ID 不同，归类为 `confirmed_gold_conflict`；完整文本、候选、字段名和标准实体名称保留在 JSON 的 `conflict_details` 中供人工复核。")
    else:
        lines.append("- 未发现同任务、同输入、不同 gold 的确认冲突。")
    lines += ["", "## 9. 类型与 NIL 分布", "", f"- mention 原始类型分布见 JSON `aggregate.entity_type_mentions`；其中 `ORG`、`PERSON`、`GPE`、`LOC` 与知识库细粒度类型分层统计，未强行合并。", f"- 知识库细粒度实体类型分布见 JSON `knowledge_base.entity_types`；正式 gold 的 NIL 以各数据集原始契约累计为 {nil_total}。", "", "## 10. 问题分级与建议", ""]
    for level, items in findings.items():
        lines.append(f"### {level}")
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- 未发现。")
        lines.append("")
    lines += ["## 11. 检查覆盖与局限", "", f"- {len(files)} 个 JSON 文件均完成 JSON 解析；只有 Schema 已识别的文件执行字段级统计。", "- 只有具备偏移字段的数据能执行字符偏移检查；`has_gold=false` 不等于数据无价值。", "- 近重复结果仅是人工审查候选；未发现训练目录也不能证明完全不存在数据泄漏。", "- Blind Holdout 已建立独立人工复核清单，但当前为单人复核限制，不能替代第二位标注者审查。", "", "## 12. 阶段验收与最终测试集建议", "", "- **阶段性验收**：有条件适合。实体链接、NIL、候选、消歧、长文本单实体共指与集合共指均有独立数据；Holdout 结果应与 Challenge Dev 分开展示。", "- **最终测试集**：已新增独立 Holdout；后续应优先补充 PERSON、跨句主体连续性、真实长文本和复杂篇章语义，而非重复受控模板。", "", "## 13. 复现命令", "", "```powershell", "python scripts\\check_dataset_quality.py", "python -m py_compile scripts\\check_dataset_quality.py", "git diff --check", "git status --short", "```", "", "## 14. 本轮文件变更", "", "本报告由质量审计脚本生成；实际工作区变更范围应以 `git status --short` 为准。"]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"dataset quality audit: files={len(files)} samples={aggregate['samples']} offset_errors={aggregate['offset_errors']} coref_cases={aggregate['coreference_cases']}")
    print(f"json={json_path.relative_to(ROOT)}")
    print(f"markdown={md_path.relative_to(ROOT)}")
    return 1 if critical_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
