#!/usr/bin/env python3
"""Generate data gap baseline statistics and an expansion plan.

Scope: 欧小红负责的数据建设、数据质量检查与评测材料整理。

This script is intentionally read-only for datasets. It reads the current
knowledge base and evaluation files, then writes:
- reports/data_gap_baseline.json
- docs/data_gap_baseline_report.md
- docs/data_expansion_plan.md
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EVAL = DATA / "eval"
KB_PATH = DATA / "kb" / "energy_entities.json"


OFFICIAL_DATASETS = {
    "knowledge_base": "data/kb/energy_entities.json",
    "mention_linking": "data/eval/mention_linking_test.json",
    "eval_dataset": "data/eval/eval_dataset.json",
    "candidate_retrieval": "data/eval/candidate_retrieval_test.json",
    "disambiguation": "data/eval/disambiguation_test.json",
    "coreference": "data/eval/coreference_long_text_test.json",
    "llm_fallback_ambiguity": "data/eval/llm_fallback_ambiguity_test.json",
    "llm_fallback_difficult": "data/eval/llm_fallback_difficult_cases.json",
    "batch_texts": "data/batch_texts.txt",
    "batch_ground_truth": "data/batch_ground_truth.json",
}


DEMO_OR_AUXILIARY_DATASETS = {
    "ner_auxiliary": "data/eval/ner_test_dataset.json",
    "llm_comparison_template": "data/eval/llm_disambiguation_comparison_template.json",
    "kb_expansion_sample": "data/kb/kb_expansion_sample.json",
    "kb_expansion_step1_material": "data/kb/kb_expansion_20260709_step1.json",
    "ambiguity_report": "data/kb/ambiguity_report.json",
    "historical_reports": "reports/*历史/阶段性输出与旧实验结果",
    "tests_output": "tests/tests/output/*历史测试输出",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def distribution(values: list[int]) -> dict[str, int]:
    return {str(key): value for key, value in sorted(Counter(values).items())}


def entity_index(kb: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["entity_id"]: item for item in kb.get("entities", []) if item.get("entity_id")}


def entity_type(entity_id: str | None, index: dict[str, dict[str, Any]]) -> str:
    if not entity_id:
        return "NIL"
    return index.get(entity_id, {}).get("entity_type", "UNKNOWN")


def text_len_bucket(text: str) -> str:
    length = len(text)
    if length < 30:
        return "<30"
    if length < 60:
        return "30-59"
    if length < 100:
        return "60-99"
    return ">=100"


def count_high_similarity_error_candidate(sample: dict[str, Any]) -> bool:
    gold = sample.get("gold_entity") or sample.get("gold_entity_id")
    candidates = (
        sample.get("expected_candidates")
        or sample.get("candidate_entities")
        or sample.get("candidate_entity_ids")
        or []
    )
    if gold is None:
        return bool(candidates)
    return any(candidate != gold for candidate in candidates)


def analyze_kb(kb: dict[str, Any]) -> dict[str, Any]:
    entities = kb.get("entities", [])
    ids = [item.get("entity_id") for item in entities]
    names = [item.get("entity_name") for item in entities]
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    alias_owner: dict[str, set[str]] = defaultdict(set)
    alias_count_by_type: dict[str, list[int]] = defaultdict(list)

    missing_description = 0
    missing_aliases = 0
    for item in entities:
        typ = item.get("entity_type", "UNKNOWN")
        by_type[typ].append(item)
        aliases = item.get("aliases", [])
        alias_count_by_type[typ].append(len(aliases))
        if not aliases:
            missing_aliases += 1
        if not (item.get("summary") or item.get("description") or item.get("business")):
            missing_description += 1
        for alias in aliases:
            name = alias.get("name") if isinstance(alias, dict) else str(alias)
            if name:
                alias_owner[name].add(item.get("entity_id", ""))
        abbreviation = item.get("abbreviation")
        if abbreviation:
            alias_owner[str(abbreviation)].add(item.get("entity_id", ""))

    duplicate_ids = sorted([key for key, count in Counter(ids).items() if key and count > 1])
    duplicate_names = sorted([key for key, count in Counter(names).items() if key and count > 1])
    alias_conflicts = {
        alias: sorted(owner for owner in owners if owner)
        for alias, owners in sorted(alias_owner.items())
        if len([owner for owner in owners if owner]) > 1
    }

    return {
        "entity_total": len(entities),
        "entity_type_counts": dict(sorted((key, len(value)) for key, value in by_type.items())),
        "avg_aliases_by_type": {
            key: round(mean(values), 2) if values else 0
            for key, values in sorted(alias_count_by_type.items())
        },
        "alias_total": sum(len(item.get("aliases", [])) for item in entities),
        "missing_description": missing_description,
        "missing_aliases": missing_aliases,
        "duplicate_entity_ids": duplicate_ids,
        "duplicate_canonical_names": duplicate_names,
        "alias_conflicts": alias_conflicts,
        "weak_types": {
            key: len(value)
            for key, value in sorted(by_type.items())
            if len(value) < 8
        },
    }


def analyze_mention_linking(data: dict[str, Any], index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    samples = data.get("samples", [])
    sample_ids = [item.get("id") for item in samples]
    texts = [item.get("text", "") for item in samples]
    mention_counts = [len(item.get("mentions", [])) for item in samples]
    linked = nil = 0
    type_counts = Counter()
    difficulty = Counter()
    repeated_mentions = Counter()

    for sample in samples:
        difficulty[sample.get("difficulty", "unlabeled")] += 1
        for expected in sample.get("expected_entities", []):
            mention = expected.get("mention")
            if mention:
                repeated_mentions[mention] += 1
            eid = expected.get("entity_id")
            if eid is None:
                nil += 1
            else:
                linked += 1
            type_counts[entity_type(eid, index)] += 1

    duplicate_texts = [text for text, count in Counter(texts).items() if text and count > 1]
    duplicate_ids = [sid for sid, count in Counter(sample_ids).items() if sid and count > 1]
    duplicate_mentions = {
        mention: count
        for mention, count in repeated_mentions.most_common()
        if count > 1
    }

    return {
        "sample_count": len(samples),
        "text_count": len(texts),
        "unique_text_count": len(set(texts)),
        "mention_total": linked + nil,
        "linked_mentions": linked,
        "nil_mentions": nil,
        "linked_ratio": round(linked / (linked + nil), 4) if linked + nil else 0,
        "nil_ratio": round(nil / (linked + nil), 4) if linked + nil else 0,
        "entity_type_counts": dict(sorted(type_counts.items())),
        "difficulty_counts": dict(sorted(difficulty.items())),
        "mention_count_distribution": distribution(mention_counts),
        "duplicate_text_count": len(duplicate_texts),
        "duplicate_sample_ids": duplicate_ids,
        "duplicate_mentions_top20": dict(list(duplicate_mentions.items())[:20]),
    }


def analyze_eval_dataset(data: dict[str, Any], index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    samples = data.get("samples", [])
    nil = sum(1 for item in samples if item.get("gold_entity") is None)
    type_counts = Counter(entity_type(item.get("gold_entity"), index) for item in samples)
    return {
        "sample_count": len(samples),
        "nil_samples": nil,
        "linked_samples": len(samples) - nil,
        "difficulty_counts": dict(sorted(Counter(item.get("difficulty", "unknown") for item in samples).items())),
        "entity_type_counts": dict(sorted(type_counts.items())),
        "scenario_count": len({item.get("scenario") for item in samples}),
        "text_length_distribution": dict(sorted(Counter(text_len_bucket(item.get("text", "")) for item in samples).items())),
    }


def analyze_candidate(data: dict[str, Any], index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    samples = data.get("samples", [])
    positive = 0
    nil_like = 0
    correct_in_candidates = 0
    no_correct_candidate = 0
    type_counts = Counter()
    high_similarity_errors = 0
    candidate_len = []
    for sample in samples:
        gold = sample.get("gold_entity") or sample.get("gold_entity_id")
        candidates = sample.get("expected_candidates") or sample.get("candidate_entities") or []
        candidate_len.append(len(candidates))
        if gold is None:
            nil_like += 1
        else:
            positive += 1
            type_counts[entity_type(gold, index)] += 1
            if gold in candidates:
                correct_in_candidates += 1
            else:
                no_correct_candidate += 1
        if count_high_similarity_error_candidate(sample):
            high_similarity_errors += 1

    return {
        "sample_count": len(samples),
        "positive_samples": positive,
        "nil_like_samples": nil_like,
        "nil_like_ratio": round(nil_like / len(samples), 4) if samples else 0,
        "correct_entity_in_topk": correct_in_candidates,
        "correct_entity_in_topk_ratio": round(correct_in_candidates / positive, 4) if positive else 0,
        "no_correct_candidate_samples": no_correct_candidate,
        "entity_type_counts": dict(sorted(type_counts.items())),
        "high_similarity_error_candidate_samples": high_similarity_errors,
        "candidate_count_distribution": distribution(candidate_len),
    }


def analyze_coreference(data: dict[str, Any]) -> dict[str, Any]:
    samples = data.get("samples", [])
    simple_single = 0
    cross_sentence = 0
    cross_3_plus = 0
    collective = 0
    multi_antecedent = 0
    nil_mixed = 0
    total_cases = 0
    surfaces = Counter()
    collective_surfaces = {"两家公司", "两家企业", "两家央企", "两家高校", "两所高校", "上述银行", "这些企业", "这些机构", "多家企业", "多家机构", "双方", "二者", "它们", "他们", "她们"}

    for sample in samples:
        mentions = sample.get("mentions", [])
        expected = sample.get("expected_coreferences", [])
        named_before = [m for m in mentions if m.get("entity_id")]
        if len(named_before) > 1:
            multi_antecedent += 1
        if any(item.get("is_nil") or item.get("entity_id") is None for item in expected):
            nil_mixed += 1
        for coref in expected:
            total_cases += 1
            idx = coref.get("mention_index", -1)
            if not isinstance(idx, int) or idx < 0 or idx >= len(mentions):
                continue
            mention = mentions[idx]
            surface = mention.get("mention", "")
            surfaces[surface] += 1
            if surface in collective_surfaces:
                collective += 1
            antecedent_sentences = [
                item.get("sentence_index", 0)
                for item in mentions[:idx]
                if item.get("entity_id") == coref.get("entity_id") and coref.get("entity_id")
            ]
            if antecedent_sentences:
                gap = mention.get("sentence_index", 0) - max(antecedent_sentences)
                if gap >= 1:
                    cross_sentence += 1
                if gap >= 3:
                    cross_3_plus += 1
                if gap <= 1 and surface not in collective_surfaces:
                    simple_single += 1

    rule_report_path = ROOT / "reports" / "coreference_rule_eval_detailed.json"
    pass_rate = None
    if rule_report_path.exists():
        report = load_json(rule_report_path)
        pass_rate = report.get("accuracy")

    return {
        "sample_count": len(samples),
        "coreference_case_count": total_cases,
        "simple_single_anaphor_cases": simple_single,
        "cross_sentence_cases": cross_sentence,
        "cross_3_plus_cases": cross_3_plus,
        "collective_cases": collective,
        "multi_candidate_antecedent_samples": multi_antecedent,
        "nil_mixed_samples": nil_mixed,
        "current_rule_pass_rate": pass_rate,
        "anaphor_surface_top20": dict(surfaces.most_common(20)),
    }


def analyze_llm(data: dict[str, Any]) -> dict[str, Any]:
    samples = data.get("samples", [])
    nil = sum(1 for item in samples if item.get("expected_nil") is True)
    candidate_counts = [len(item.get("candidate_entity_ids", [])) for item in samples]
    return {
        "sample_count": len(samples),
        "linked_samples": len(samples) - nil,
        "nil_samples": nil,
        "nil_ratio": round(nil / len(samples), 4) if samples else 0,
        "difficulty_counts": dict(sorted(Counter(item.get("difficulty", "unknown") for item in samples).items())),
        "ambiguity_type_counts": dict(sorted(Counter(item.get("ambiguity_type", "unknown") for item in samples).items())),
        "candidate_count_distribution": distribution(candidate_counts),
        "text_length_distribution": dict(sorted(Counter(text_len_bucket(item.get("text", "")) for item in samples).items())),
    }


def analyze_batch(gt: dict[str, Any], lines: list[str], index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    entries = gt.get("entries", [])
    mention_counts = [len(item.get("expected_entities", [])) for item in entries]
    long_text = sum(1 for line in lines if len(line) >= 80)
    multi_mention = sum(1 for count in mention_counts if count > 1)
    nil_mixed = 0
    type_counts = Counter()
    repeated_mention_entries = 0
    coref_like = 0
    for entry, line in zip(entries, lines):
        expected = entry.get("expected_entities", [])
        eids = [item.get("entity_id") for item in expected]
        if any(eid is None for eid in eids) and any(eid is not None for eid in eids):
            nil_mixed += 1
        mentions = [item.get("mention") for item in expected]
        if len(mentions) != len(set(mentions)):
            repeated_mention_entries += 1
        if any(surface in line for surface in ("该公司", "该机构", "前者", "后者", "上述", "这些", "他们", "它们")):
            coref_like += 1
        for eid in eids:
            type_counts[entity_type(eid, index)] += 1
    return {
        "sample_count": len(entries),
        "text_line_count": len(lines),
        "mention_count_distribution": distribution(mention_counts),
        "long_text_count": long_text,
        "multi_mention_count": multi_mention,
        "nil_mixed_count": nil_mixed,
        "coreference_mixed_count": coref_like,
        "repeated_mention_entries": repeated_mention_entries,
        "entity_type_counts": dict(sorted(type_counts.items())),
    }


def audit_schema() -> dict[str, Any]:
    return {
        "paths": OFFICIAL_DATASETS,
        "schemas": {
            "knowledge_base": {
                "top_level": ["schema_version", "kb_version", "entities", "entity_type_enum", "ner_type_mapping"],
                "entity_required_observed": ["entity_id", "entity_name", "aliases", "entity_type", "summary/business", "keywords", "source"],
                "entity_id_rule_observed": "既有能源实体使用 ENT_ENERGY_XXXX，通用扩充实体使用 ENT_GEN_XXXX；新增应取当前最大序号后递增。",
            },
            "mention_linking": {
                "top_level": ["dataset_name", "version", "purpose", "input_contract", "knowledge_base", "statistics", "samples"],
                "sample_id_rule": "MENTION_LINK_001 起三位连续编号。",
                "mention_schema": ["mention", "type", "char_start", "char_end", "confidence"],
                "expected_schema": ["mention", "entity_id"],
                "nil_rule": "expected_entities[].entity_id = null；sample.has_nil 必须与 expected_entities 内是否存在 null 一致。",
                "span_rule": "需要 char_start/char_end，且 text[start:end] 必须等于 mention。",
            },
            "eval_dataset": {
                "top_level": ["dataset_metadata", "samples"],
                "sample_id_rule": "EVAL_001 起三位连续编号。",
                "sample_schema": ["text", "mention", "mention_start", "mention_end", "gold_entity", "candidate_entities", "expected_result", "difficulty", "scenario", "id"],
                "nil_rule": "gold_entity = null；expected_result.linked=false 且 expected_result.nil=true。",
            },
            "candidate_retrieval": {
                "top_level": ["dataset_name", "version", "purpose", "candidate_methods", "samples", "statistics"],
                "sample_id_rule": "CR_001 起三位连续编号。",
                "candidate_schema": "expected_candidates 为 entity_id 字符串列表；gold_entity 为正确实体或 null。",
                "nil_rule": "gold_entity = null 视为 NIL-like。",
            },
            "disambiguation": {
                "top_level": ["dataset_name", "version", "purpose", "nil_threshold", "bge_llm_trigger_threshold", "samples", "statistics"],
                "sample_id_rule": "DIS_001 起三位连续编号。",
                "sample_schema": ["text", "mention", "gold_entity", "confidence_level", "kb_status", "expected_bge_score_range", "expected_nil", "reason", "scenario", "id"],
                "nil_rule": "gold_entity = null 且 expected_nil=true。",
            },
            "coreference": {
                "top_level": ["schema_version", "dataset_name", "description", "samples"],
                "sample_id_rule": "COREF_LONG_001 起三位连续编号。",
                "mention_schema": ["mention", "type", "sentence_index", "role", "entity_id?", "standard_entity?"],
                "coref_schema": "expected_coreferences[].mention_index 指向 mentions 下标；entity_id=null/is_nil=true 表示集合或无法唯一绑定。",
            },
            "llm_fallback": {
                "files": ["llm_fallback_ambiguity_test.json", "llm_fallback_difficult_cases.json"],
                "sample_id_rule": "LLM_AMB_001 或 LLM_HARD_001 起三位连续编号。",
                "sample_schema": ["text", "mention", "candidate_entity_ids", "gold_entity_id", "expected_nil", "difficulty", "ambiguity_type", "decisive_evidence", "llm_prompt_focus"],
                "nil_rule": "expected_nil=true 且 gold_entity_id=null。",
            },
            "batch": {
                "files": ["data/batch_texts.txt", "data/batch_ground_truth.json"],
                "organization": "batch_texts.txt 第 N 行对应 batch_ground_truth.entries[N].text_idx=N。",
                "expected_schema": "entries[].expected_entities 为 {mention, entity_id} 列表，可同时包含 linked 与 NIL。",
                "nil_rule": "entity_id=null；entry.has_nil 与 expected_entities 内 null 保持一致。",
            },
        },
        "current_scripts": {
            "data_generation": ["scripts/expand_knowledge_base.py"],
            "data_validation": ["scripts/validate_eval_data.py"],
            "coreference_evaluation": ["scripts/evaluate_coreference.py", "scripts/evaluate_coreference_rules.py"],
            "e2e_or_api_helper": ["scripts/e2e_from_ground_truth.py"],
            "distribution_reporting": ["scripts/report_data_distribution.py"],
        },
        "script_scope_note": "仓库 _repo_check/scripts 下未发现日报截图专用脚本；项目根级 scripts/ 若存在日报截图工具，不应视为核心业务脚本。",
        "formal_vs_demo": {
            "formal_regression_data": list(OFFICIAL_DATASETS.values()),
            "demo_or_auxiliary_data": DEMO_OR_AUXILIARY_DATASETS,
        },
    }


def build_baseline() -> dict[str, Any]:
    kb = load_json(KB_PATH)
    index = entity_index(kb)
    mention = load_json(EVAL / "mention_linking_test.json")
    eval_dataset = load_json(EVAL / "eval_dataset.json")
    candidate = load_json(EVAL / "candidate_retrieval_test.json")
    disamb = load_json(EVAL / "disambiguation_test.json")
    coref = load_json(EVAL / "coreference_long_text_test.json")
    llm_amb = load_json(EVAL / "llm_fallback_ambiguity_test.json")
    llm_hard = load_json(EVAL / "llm_fallback_difficult_cases.json")
    batch_gt = load_json(DATA / "batch_ground_truth.json")
    batch_lines = [line for line in (DATA / "batch_texts.txt").read_text(encoding="utf-8").splitlines() if line.strip()]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": "课题10：实体链接与知识对齐智能体",
        "member_scope": "第三成员欧小红：数据处理、测试数据建设、数据质量检查和评测材料整理",
        "audit": audit_schema(),
        "knowledge_base": analyze_kb(kb),
        "mention_linking": analyze_mention_linking(mention, index),
        "eval_dataset": analyze_eval_dataset(eval_dataset, index),
        "candidate_retrieval": analyze_candidate(candidate, index),
        "disambiguation": analyze_candidate(disamb, index),
        "coreference": analyze_coreference(coref),
        "llm_fallback_ambiguity": analyze_llm(llm_amb),
        "llm_fallback_difficult": analyze_llm(llm_hard),
        "batch": analyze_batch(batch_gt, batch_lines, index),
    }


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(lines)


def write_baseline_markdown(report: dict[str, Any]) -> None:
    kb = report["knowledge_base"]
    mention = report["mention_linking"]
    candidate = report["candidate_retrieval"]
    coref = report["coreference"]
    llm_hard = report["llm_fallback_difficult"]
    batch = report["batch"]
    lines = [
        "# 数据缺口基线统计报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        "- 成员视角：第三成员欧小红（数据处理、评测数据建设、质量检查）",
        "- 范围说明：本报告只审计数据、脚本和评测材料，不修改核心算法或 API 架构。",
        "",
        "## 1. 仓库审计结论",
        "",
        "### 1.1 正式回归数据路径",
        "",
        md_table(["数据集", "路径"], [[key, value] for key, value in report["audit"]["paths"].items()]),
        "",
        "### 1.2 Schema 与 ID/NIL 规则摘要",
        "",
        "- 知识库实体 ID：已观察到 `ENT_ENERGY_XXXX` 与 `ENT_GEN_XXXX` 两类；后续新增通用实体应沿用 `ENT_GEN_` 最大序号递增。",
        "- mention linking：`MENTION_LINK_001` 连续编号；mention 需要 `char_start/char_end`；NIL 使用 `expected_entities[].entity_id = null`。",
        "- eval dataset：`EVAL_001` 连续编号；NIL 使用 `gold_entity = null` 与 `expected_result.nil=true`。",
        "- candidate retrieval：`CR_001` 连续编号；`expected_candidates` 是候选 entity_id 列表；`gold_entity=null` 表示 NIL-like。",
        "- disambiguation：`DIS_001` 连续编号；`gold_entity=null` 且 `expected_nil=true` 表示 NIL。",
        "- coreference：`COREF_LONG_001` 连续编号；`expected_coreferences[].mention_index` 指向 `mentions` 下标；集合/不可唯一绑定使用 `entity_id=null,is_nil=true`。",
        "- LLM fallback：`LLM_AMB_001`/`LLM_HARD_001` 连续编号；`expected_nil=true,gold_entity_id=null` 表示 NIL。",
        "- batch：`batch_texts.txt` 行号与 `batch_ground_truth.entries[].text_idx` 一一对应；每条可包含多个 `{mention, entity_id}`。",
        "",
        "### 1.3 脚本审计",
        "",
        "- 数据生成：`scripts/expand_knowledge_base.py`",
        "- 数据校验：`scripts/validate_eval_data.py`",
        "- 共指评测：`scripts/evaluate_coreference.py`、`scripts/evaluate_coreference_rules.py`",
        "- E2E/API 辅助：`scripts/e2e_from_ground_truth.py`",
        "- 本次新增统计：`scripts/report_data_distribution.py`",
        "- `_repo_check/scripts` 下未发现日报截图专用脚本；日报截图工具若位于仓库外层 `scripts/`，不应作为核心业务脚本。",
        "",
        "## 2. 主测试集 mention_linking",
        "",
        md_table(
            ["指标", "数值"],
            [
                ["样本条数", mention["sample_count"]],
                ["文本条数", mention["text_count"]],
                ["唯一文本数", mention["unique_text_count"]],
                ["mention 总数", mention["mention_total"]],
                ["LINKED 数", mention["linked_mentions"]],
                ["NIL 数", mention["nil_mentions"]],
                ["LINKED 比例", mention["linked_ratio"]],
                ["NIL 比例", mention["nil_ratio"]],
                ["重复文本数", mention["duplicate_text_count"]],
                ["重复样本 ID", len(mention["duplicate_sample_ids"])],
            ],
        ),
        "",
        f"- 每条文本 mention 数量分布：`{mention['mention_count_distribution']}`",
        f"- 实体类型覆盖：`{mention['entity_type_counts']}`",
        f"- 难度标注分布：`{mention['difficulty_counts']}`",
        f"- 高频重复 mention（前20）：`{mention['duplicate_mentions_top20']}`",
        "",
        "## 3. 知识库",
        "",
        md_table(
            ["指标", "数值"],
            [
                ["实体总数", kb["entity_total"]],
                ["别名总数", kb["alias_total"]],
                ["缺失 description/summary/business 数", kb["missing_description"]],
                ["缺失 aliases 数", kb["missing_aliases"]],
                ["重复 entity_id 数", len(kb["duplicate_entity_ids"])],
                ["重复 canonical name 数", len(kb["duplicate_canonical_names"])],
                ["alias 冲突数量", len(kb["alias_conflicts"])],
            ],
        ),
        "",
        f"- 各 entity type 数量：`{kb['entity_type_counts']}`",
        f"- 每类平均 alias 数：`{kb['avg_aliases_by_type']}`",
        f"- 弱覆盖类型（少于8个实体）：`{kb['weak_types']}`",
        "- alias 指向多个实体不直接判错，作为合法歧义/潜在消歧压力记录。",
        "",
        "## 4. Candidate Retrieval",
        "",
        md_table(
            ["指标", "数值"],
            [
                ["样本总数", candidate["sample_count"]],
                ["正样本数", candidate["positive_samples"]],
                ["NIL-like 数", candidate["nil_like_samples"]],
                ["NIL-like 比例", candidate["nil_like_ratio"]],
                ["正确实体在 Top-K 中数量", candidate["correct_entity_in_topk"]],
                ["正确实体在 Top-K 比例", candidate["correct_entity_in_topk_ratio"]],
                ["无正确候选样本数", candidate["no_correct_candidate_samples"]],
                ["高相似错误候选样本数", candidate["high_similarity_error_candidate_samples"]],
            ],
        ),
        "",
        f"- 候选数量分布：`{candidate['candidate_count_distribution']}`",
        f"- 正样本实体类型覆盖：`{candidate['entity_type_counts']}`",
        "",
        "## 5. Coreference",
        "",
        md_table(
            ["指标", "数值"],
            [
                ["样本总数", coref["sample_count"]],
                ["共指 case 总数", coref["coreference_case_count"]],
                ["简单单数指代数", coref["simple_single_anaphor_cases"]],
                ["跨句指代数", coref["cross_sentence_cases"]],
                ["跨 3 句以上数", coref["cross_3_plus_cases"]],
                ["集合指代数", coref["collective_cases"]],
                ["多候选先行词样本数", coref["multi_candidate_antecedent_samples"]],
                ["NIL 混合样本数", coref["nil_mixed_samples"]],
                ["当前规则通过率", coref["current_rule_pass_rate"]],
            ],
        ),
        "",
        f"- 指代表达 Top20：`{coref['anaphor_surface_top20']}`",
        "",
        "## 6. LLM Fallback",
        "",
        "### 6.1 LLM ambiguity",
        "",
        f"- 统计：`{report['llm_fallback_ambiguity']}`",
        "",
        "### 6.2 LLM hard cases",
        "",
        f"- 统计：`{llm_hard}`",
        "",
        "## 7. Batch",
        "",
        md_table(
            ["指标", "数值"],
            [
                ["样本总数", batch["sample_count"]],
                ["文本行数", batch["text_line_count"]],
                ["长文本数量", batch["long_text_count"]],
                ["多 mention 数量", batch["multi_mention_count"]],
                ["LINKED+NIL 混合数量", batch["nil_mixed_count"]],
                ["共指混合数量", batch["coreference_mixed_count"]],
                ["重复 mention 请求数", batch["repeated_mention_entries"]],
            ],
        ),
        "",
        f"- 每条请求 mention 数量分布：`{batch['mention_count_distribution']}`",
        f"- 实体类型覆盖：`{batch['entity_type_counts']}`",
        "",
        "## 8. 当前主要不足",
        "",
        "1. mention linking 当前 379 条，距离 500～520 目标仍缺约 121～141 条。",
        "2. 知识库弱类型仍明显存在，尤其 `GRID_COMPANY`、`MEDICAL_INSTITUTION`、`TRANSPORTATION_ORG`、`MEDIA_ORG`、`AUTO_MANUFACTURER` 都少于 8 个实体。",
        "3. candidate retrieval 的 NIL-like 为 16/151，占比约 10.6%，候选召回层面的未入库与高相似干扰仍不足。",
        "4. coreference 当前全通过，但跨 3 句以上样本为 0，说明长距离指代压力不足；多候选先行词数量虽有覆盖，但还需要更难的指代切换和部分集合指代。",
        "5. LLM hard cases 当前 63 条，距离 100～120 目标仍缺 37～57 条。",
        "6. batch 当前 155 条，距离 200～220 目标仍缺 45～65 条；长文本数量偏少，共指混合数量偏低。",
    ]
    path = ROOT / "docs" / "data_gap_baseline_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_plan(report: dict[str, Any]) -> None:
    mention_now = report["mention_linking"]["sample_count"]
    candidate_now = report["candidate_retrieval"]["sample_count"]
    coref_now = report["coreference"]["sample_count"]
    llm_now = report["llm_fallback_difficult"]["sample_count"]
    batch_now = report["batch"]["sample_count"]

    candidate_target = 210
    coref_target = 150
    llm_target = 110
    batch_target = 210
    mention_target = 510

    rows = [
        ["mention linking", mention_now, "500～520", max(0, mention_target - mention_now), "类型平衡、NIL、歧义、多表达体裁", "Schema + validate_eval_data + 抽检"],
        ["candidate retrieval", candidate_now, candidate_target, max(0, candidate_target - candidate_now), "NIL-like、高相似错误候选、未入库实体", "Schema + TopK 覆盖统计"],
        ["coreference", coref_now, coref_target, max(0, coref_target - coref_now), "多候选、跨3句、集合、NIL混合、指代切换", "共指回归 + badcase 记录"],
        ["LLM fallback hard", llm_now, "100～120", max(0, llm_target - llm_now), "同名异指、信息稀疏、行业知识、冲突线索", "人工抽检 + 回归"],
        ["batch", batch_now, "200～220", max(0, batch_target - batch_now), "长文本、多mention、LINKED+NIL、共指混合", "batch ground truth 校验"],
    ]

    lines = [
        "# 数据扩充实施计划",
        "",
        f"- 生成时间：{report['generated_at']}",
        "- 成员视角：第三成员欧小红",
        "- 当前状态：已完成阶段一仓库审计与阶段二基线统计；本计划用于后续分批扩充，不在本阶段直接批量造数。",
        "",
        "## 1. 目标表",
        "",
        md_table(["数据集", "当前数量", "目标数量", "预计新增", "主要补充类型", "校验方式"], rows),
        "",
        "## 2. 分批策略",
        "",
        "### 批次 A：Schema 和生成器验证",
        "",
        "- 新增规模：mention linking 10～15 条，candidate 5～10 条，coreference 5～8 条，LLM hard 5 条，batch 5 条。",
        "- 覆盖内容：各文件最小闭环样本、NIL 表示、连续 ID、span、batch text_idx。",
        "- 校验：`python scripts/validate_eval_data.py`、`python scripts/evaluate_coreference_rules.py --fail-on-wrong`、人工抽检 10 条。",
        "- Git 建议：`数据扩充批次A schema验证样本`。",
        "",
        "### 批次 B：弱类型知识库与正样本",
        "",
        "- 新增规模：每个弱类型 2～4 个实体，合计约 12～18 个实体；mention 正样本约 35～45 条。",
        "- 重点类型：`GRID_COMPANY`、`MEDICAL_INSTITUTION`、`TRANSPORTATION_ORG`、`MEDIA_ORG`、`AUTO_MANUFACTURER`。",
        "- 同步文件：`data/kb/energy_entities.json`、`mention_linking_test.json`、`eval_dataset.json`、`candidate_retrieval_test.json`、`batch_*`。",
        "- 校验：实体 ID 唯一、alias 非空、description/summary 可消歧、至少一条正样本覆盖。",
        "- Git 建议：`补充弱类型知识库实体和正样本`。",
        "",
        "### 批次 C：NIL 与候选召回压力样本",
        "",
        "- 新增规模：candidate retrieval 35～45 条，其中 NIL-like 至少 25 条；mention linking 30～40 条。",
        "- 覆盖内容：未入库机构、地区前缀差异、同名近似、错别字/缩写、候选存在高相似错误实体。",
        "- 不修改核心算法；若正确实体未召回，应记录为候选召回边界，而不是强行改 expected result。",
        "- Git 建议：`增强NIL和候选召回压力样本`。",
        "",
        "### 批次 D：困难共指样本",
        "",
        "- 新增规模：coreference 35～40 条。",
        "- 覆盖内容：跨 3 句以上、多候选先行词、前者/后者连续切换、集合指代只覆盖部分实体、NIL 与已链接实体混合。",
        "- 若共指规则失败：先输出 badcase 分析，区分样本错误与算法真实边界；不擅自重构算法。",
        "- Git 建议：`补充困难共指评测样本`。",
        "",
        "### 批次 E：LLM Fallback 困难样本",
        "",
        "- 新增规模：LLM hard cases 40～50 条，目标达到 100～120 条。",
        "- 覆盖内容：同名异指、候选描述高度接近、信息稀疏、长距离上下文、行业知识依赖、旧称/简称混合、NIL。",
        "- 抽检要求：新增样本不能是简单精确别名匹配；每条必须有 decisive_evidence。",
        "- Git 建议：`扩充LLM兜底困难样本`。",
        "",
        "### 批次 F：Batch 回归样本",
        "",
        "- 新增规模：batch 45～55 条，目标达到 200～220 条。",
        "- 覆盖内容：长文本、多 mention、LINKED+NIL 混合、重复 mention、同一实体多别名、中英文别名、共指链、部分失败场景。",
        "- 校验：text_idx 连续、mention 在文本中、输出数量与输入 mention 一致、NIL 不串位。",
        "- Git 建议：`扩充batch回归样本`。",
        "",
        "## 3. 数据质量控制",
        "",
        "- 避免数据泄漏：测试样本不直接复制知识库 summary；使用上下文证据而不是把答案写进模板。",
        "- 防止伪多样性：每批限制同一模板复用，覆盖新闻体、公告体、对话体、报告体、行业分析体、长段落和中英文混合。",
        "- LINKED/NIL 比例：主测试集维持 NIL mention 约 18%～25%；candidate retrieval 将 NIL-like 提升到约 25%～35%。",
        "- 类型覆盖：弱类型实体数量至少提升到 8～10 个，并确保每个新增实体至少被一个正样本和一个 batch/候选样本覆盖。",
        "- 难度覆盖：eval 与 LLM hard 中 hard/medium 样本比例保持可解释，不把简单精确匹配伪装成 hard。",
        "- 回滚方式：每批独立提交；若校验失败，优先回滚本批新增样本，不删除历史样本、不降低断言。",
        "",
        "## 4. 当前不执行的事项",
        "",
        "- 不训练或实现 NER。",
        "- 不重构实体链接 pipeline、API 服务或其他成员负责模块。",
        "- 不为了让困难共指样本通过而修改核心算法；失败样本先进入 badcase。",
    ]
    path = ROOT / "docs" / "data_expansion_plan.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report = build_baseline()
    save_json(ROOT / "reports" / "data_gap_baseline.json", report)
    write_baseline_markdown(report)
    write_plan(report)

    print("Data distribution report generated")
    print(f"  JSON: {ROOT / 'reports' / 'data_gap_baseline.json'}")
    print(f"  Markdown: {ROOT / 'docs' / 'data_gap_baseline_report.md'}")
    print(f"  Plan: {ROOT / 'docs' / 'data_expansion_plan.md'}")
    print(f"  mention_linking: {report['mention_linking']['sample_count']}")
    print(f"  candidate_retrieval: {report['candidate_retrieval']['sample_count']}")
    print(f"  coreference: {report['coreference']['sample_count']}")
    print(f"  llm_hard: {report['llm_fallback_difficult']['sample_count']}")
    print(f"  batch: {report['batch']['sample_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
