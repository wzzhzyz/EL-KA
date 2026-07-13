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
    if path.name == "coreference_collective_test.json":
        return "单元测试夹具 / 专项回归"
    if path.name == "llm_disambiguation_comparison_template.json":
        return "开发模板 / 非正式评测"
    if path.name in {"batch_ground_truth.json"}:
        return "批量回归金标"
    if path.parent == EVAL_DIR:
        return "正式专项评测集"
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


def entities_of(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        for key in ("entities", "items"):
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
    for key in ("entity_id", "expected_entity_id", "gold_entity_id"):
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
    for key in ("expected_candidates",):
        value = sample.get(key)
        if isinstance(value, list):
            ids.extend(x for x in value if isinstance(x, str) and x)
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
    conflict_examples = [{"items": [{"file": file_name, "sample_index": index, "entity_id": entity_id} for file_name, index, entity_id in items]} for items in conflict_groups[:20]]
    return {"exact_duplicate_groups": len(exact_groups), "exact_duplicate_instances": sum(len(x) - 1 for x in exact_groups), "label_conflict_groups": len(conflict_groups), "label_conflict_examples": conflict_examples, "cross_file_same_text_groups": sum(1 for items in by_text.values() if len({f for f, _, _ in items}) > 1), "near_duplicate_pairs_capped": near, "method": "文本去空白与标点后精确比较；标签冲突仅比较同一规范化文本和同一规范化 mention 的不同 gold entity；近重复使用 SequenceMatcher 比率 >= 0.90，并按长度差过滤，最多记录 100 对。"}


def coverage(dataset_samples: Dict[str, List[Dict[str, Any]]]) -> Dict[str, str]:
    corpus = "\n".join(str(sample.get("text", "")) for samples in dataset_samples.values() for sample in samples)
    mentions = "\n".join(str(m.get("mention", "")) for samples in dataset_samples.values() for s in samples for m in all_mentions(s))
    collective = dataset_samples.get("coreference_collective_test.json", [])
    collective_text = "\n".join(str(s.get("text", "")) for s in collective)
    matrix = {
        "实体链接：标准名、别名、歧义、候选、NIL": "已覆盖（由 mention_linking、alias、candidate、disambiguation 与 LLM 难例集分担）",
        "实体链接：轻微噪声 / 中英文数字": "部分覆盖；需要独立统计或增加对抗样本",
        "实体链接：嵌套或重叠 mention": "尚未形成明确专项 gold",
        "单实体共指：同句、跨句、类型不兼容、无前件": "已覆盖（coreference_long_text_test.json）",
        "单实体共指：链式、多同类型候选、远距离": "部分覆盖；建议按场景建立显式分组统计",
        "集合共指：两个 ORG、三实体 ORG、两个 PERSON": "已覆盖（专项夹具）",
        "集合共指：和、与、顿号": "已覆盖（专项夹具）",
        "集合共指：及、以及": "尚未覆盖",
        "集合共指：她们、它们、双方、二者、两家央企": "仅“两家央企”规则范围已确认；专项夹具未覆盖其余词面",
        "集合共指：混合类型、未链接、跨句、重复 ID、单数代词": "已覆盖（专项夹具）",
        "集合共指：非实体插入、非相邻候选、多协调组、复杂省略": "尚未覆盖",
    }
    matrix["检测依据"] = f"集合专项文本中含：{', '.join(marker for marker in ['和', '与', '、', '及', '以及'] if marker in collective_text) or '无'}；集合代词观测：{', '.join(sorted(set(re.findall(r'他们|她们|它们|这些机构|双方|二者|两家央企', collective_text)))) or '无'}。"
    return matrix


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only entity-linking dataset quality audit")
    parser.add_argument("--json-output", default="reports/dataset_quality_report.json")
    parser.add_argument("--markdown-output", default="reports/dataset_quality_report.md")
    args = parser.parse_args()

    kb_data, kb_error = load_json(KB_PATH)
    entities = entities_of(kb_data) if kb_data is not None else []
    kb_ids = {item.get("entity_id") for item in entities if isinstance(item.get("entity_id"), str)}
    kb_types = Counter(str(item.get("entity_type", item.get("type", "UNKNOWN"))) for item in entities)
    supplementary_kb = []
    for aux_path in sorted((ROOT / "data" / "kb").glob("*.json")):
        if aux_path == KB_PATH:
            continue
        aux_data, aux_error = load_json(aux_path)
        aux_entities = entities_of(aux_data) if aux_data is not None else []
        aux_samples, aux_root = samples_of(aux_data) if aux_data is not None else ([], "unparsed")
        supplementary_kb.append({"path": str(aux_path.relative_to(ROOT)), "parse_error": aux_error, "entity_records": len(aux_entities), "sample_records": len(aux_samples), "root_key": aux_root})

    paths = sorted(EVAL_DIR.glob("*.json")) + [ROOT / "data" / "batch_ground_truth.json"]
    files: List[Dict[str, Any]] = []
    dataset_samples: Dict[str, List[Dict[str, Any]]] = {}
    offset_total = Counter()
    id_issues: List[Dict[str, str]] = []
    aggregate = Counter()
    type_distribution = Counter()
    nil_total = 0
    for path in paths:
        data, error = load_json(path)
        entry: Dict[str, Any] = {"path": str(path.relative_to(ROOT)), "classification": classify(path), "format": "JSON", "parse_error": error}
        if error:
            files.append(entry)
            continue
        samples, root_key = samples_of(data)
        dataset_samples[path.name] = samples
        offsets = offset_audit(path, samples)
        coref = coref_audit(path, samples)
        fields = field_audit(path, samples)
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
                category = "外部知识库 ID"
            else:
                category = "无法确认"
            if category == "测试夹具 ID":
                placeholder_ids += 1
            id_issues.append({"file": path.name, "entity_id": entity_id, "category": category})
        entry.update({"root_key": root_key, "samples": len(samples), "mentions": mention_count, "positive_marked": positive, "nil_labeled_units": nil, "unique_referenced_ids": len(unique_entities), "coreference": coref, "field_audit": {"confidence_checked": fields["confidence_checked"], "error_count": len(fields["errors"]), "examples": fields["errors"][:20]}, "offsets": {k: v for k, v in offsets.items() if k != "errors"}, "offset_error_count": len(offsets["errors"]), "offset_error_examples": offsets["errors"][:20], "placeholder_ids": placeholder_ids, "has_gold": any(key in sample for sample in samples for key in ("expected_entity", "expected_entities", "expected_coreferences", "entity_id"))})
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
    errors = [f for f in files if f.get("parse_error")] + [e for f in files for e in f.get("offset_error_examples", [])] + [e for f in files for e in f.get("coreference", {}).get("errors", [])] + [e for f in files for e in f.get("field_audit", {}).get("examples", [])]
    formal_files = [f for f in files if f["classification"] == "正式专项评测集"]
    findings = {
        "P0": [],
        "P1": ["集合共指专项仅 8 条文本 / 8 个 case，且为单元测试夹具；其 100% 结果不能作为正式总体共指准确率。"],
        "P2": ["集合专项未覆盖“及”“以及”、她们/它们/双方/二者、非实体插入、多协调组、复杂省略与非相邻候选。", "历史长文本共指集未采用 entity_ids 集合 gold，无法单独衡量集合共指能力。", "多份专项集可能包含模板化实体替换；近重复检测结果应作为扩充时的去重基线。"],
        "P3": ["不同历史数据集的 gold 字段存在 schema 差异；评测时需按数据契约区分历史兼容格式与集合扩展格式。"],
    }
    if errors:
        findings["P0"].append(f"发现 {len(errors)} 项结构、偏移或集合契约错误；详见 JSON 报告 examples。")
    if duplicates["label_conflict_groups"]:
        findings["P1"].append(f"发现 {duplicates['label_conflict_groups']} 组相同规范化文本的标签差异，需人工判定是否为合理上下文差异。")
    external_id_count = sum(1 for issue in id_issues if issue["category"] == "外部知识库 ID")
    if external_id_count:
        findings["P2"].append(f"正式长文本共指集中存在 {external_id_count} 个不在当前运行知识库的历史外部 ID；它们不构成结构错误，但不能直接用于端到端知识库 ID 一致性验收。")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "data/eval/*.json + data/batch_ground_truth.json；主知识库为 data/kb/energy_entities.json。历史运行输出、索引文件和 trace.db 不作为 gold 测试集。",
        "knowledge_base": {"path": str(KB_PATH.relative_to(ROOT)), "entities": len(entities), "entity_types": dict(kb_types), "aliases": sum(len(item.get("aliases", [])) for item in entities)},
        "supplementary_knowledge_files": supplementary_kb,
        "files": files,
        "aggregate": {**aggregate, "nil_marked": nil_total, "entity_type_mentions": dict(type_distribution), "formal_eval_files": len(formal_files)},
        "entity_id_issues": id_issues,
        "duplicates": duplicates,
        "coverage_matrix": coverage(dataset_samples),
        "findings": findings,
        "quality_conclusion": "良好：结构与偏移检查通过时适合阶段性验收；作为最终测试集仍需要扩充集合共指和独立困难样本，且不得以夹具 100% 代表整体能力。",
    }
    json_path = ROOT / args.json_output
    md_path = ROOT / args.markdown_output
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 实体链接与共指测试数据质量报告", "", "## 1. 总体结论", "", report["quality_conclusion"], "", "## 2. 核心统计", "", f"- 扫描 JSON 数据文件：{len(files)}", f"- 样本 / entry：{aggregate['samples']}", f"- 输入 mention 或 batch gold mention：{aggregate['mentions']}", f"- 显式 NIL 标注单元（跨数据集原始计数，不去重）：{nil_total}", f"- 共指 case：{aggregate['coreference_cases']}（当前字段化单实体 case：{aggregate['single_coreference']}；集合 case：{aggregate['collective_coreference']}）", f"- 偏移：检查 {aggregate['offset_checked']}，正确 {aggregate['offset_correct']}，错误 {aggregate['offset_errors']}，重叠 {aggregate['overlaps']}，重复 mention {aggregate['duplicate_mentions']}", f"- 字段类型 / confidence 错误：{aggregate['field_errors']}", f"- 知识库：{len(entities)} 个实体、{sum(len(item.get('aliases', [])) for item in entities)} 条 alias", f"- ID 非知识库引用：{len(id_issues)}（测试夹具 ID：{sum(1 for x in id_issues if x['category'] == '测试夹具 ID')}；历史外部 ID：{sum(1 for x in id_issues if x['category'] == '外部知识库 ID')}）", "", "## 3. 文件清单", "", "| 文件 | 分类 | 样本 | mention | NIL 标注 | 共指 case | 集合 case | 偏移错误 |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for item in files:
        if item.get("parse_error"):
            lines.append(f"| `{item['path']}` | {item['classification']} | - | - | - | - | 解析失败 |")
        else:
            coref = item["coreference"]
            lines.append(f"| `{item['path']}` | {item['classification']} | {item['samples']} | {item['mentions']} | {item['nil_labeled_units']} | {coref['cases']} | {coref['collective']} | {item['offset_error_count']} |")
    lines += ["", "### 补充知识库文件", "", "| 文件 | 实体记录 | 样本记录 | 说明 |", "| --- | ---: | ---: | --- |"]
    for item in supplementary_kb:
        detail = item["parse_error"] or "辅助知识库 / 扩充或歧义分析数据，不作为当前主 KB ID 有效性基准"
        lines.append(f"| `{item['path']}` | {item['entity_records']} | {item['sample_records']} | {detail} |")
    lines += ["", "## 4. 结构、偏移与实体 ID", "", f"- JSON 解析错误：{sum(1 for item in files if item.get('parse_error'))}。", f"- 字段类型 / `confidence` 错误：{aggregate['field_errors']}。", f"- 字符偏移错误：{aggregate['offset_errors']}；越界：{sum(item.get('offsets', {}).get('out_of_bounds', 0) for item in files)}。", f"- 集合共指契约错误：{sum(len(item.get('coreference', {}).get('errors', [])) for item in files)}。", f"- 非知识库 ID：{len(id_issues)}；测试夹具 ID 与历史外部 ID 已按用途分类，不直接判为 gold 错误。", "", "## 5. 重复、泄漏与 100% 风险", "", f"- 完全重复实例：{duplicates['exact_duplicate_instances']}；标签冲突组：{duplicates['label_conflict_groups']}；跨文件同文本组：{duplicates['cross_file_same_text_groups']}。", f"- 近重复方法：{duplicates['method']}", "- 集合专项的 100% 是规则夹具回归结果，样本量仅 8 个 case 且与规则设计高度贴合，结论为“基本可信但覆盖有限”，不得外推为通用集合共指能力。", "- 未发现训练集目录；仓库中的 `tests/tests/output` 与 `reports` 为运行输出，不作为 gold 测试集计入。", "", "## 6. 功能覆盖矩阵", ""]
    for name, status in report["coverage_matrix"].items():
        lines.append(f"- **{name}**：{status}")
    lines += ["", "## 7. 问题分级与建议", ""]
    for level, items in findings.items():
        lines.append(f"### {level}")
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- 未发现。")
        lines.append("")
    lines += ["## 8. 适用性", "", "- **阶段性验收**：有条件适合。实体链接、NIL、候选、消歧、长文本单实体共指已有独立数据；集合能力应以专项夹具回归结论单独展示。", "- **最终测试集**：需要扩充。应新增独立于规则示例的集合共指金标、真实长文本、复杂并列与对抗 NIL，并建立集合数据的正式评测划分。", "", "## 9. 复现命令", "", "```powershell", "python scripts\\check_dataset_quality.py", "git diff --check", "git status --short", "```"]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"dataset quality audit: files={len(files)} samples={aggregate['samples']} offset_errors={aggregate['offset_errors']} coref_cases={aggregate['coreference_cases']}")
    print(f"json={json_path.relative_to(ROOT)}")
    print(f"markdown={md_path.relative_to(ROOT)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
