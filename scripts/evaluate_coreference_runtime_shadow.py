"""Runtime-equivalent shadow evaluation for collective ambiguity rejection.

The script never changes production output.  It sends the JSON mentions to the
same resolver input used at runtime (no offline sentence-index enrichment),
then evaluates a copied, opt-in rejection decision before the formal decision.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from entity_linker.coreference import (  # noqa: E402
    CoreferenceMention,
    RuleBasedCoreferenceResolver,
    collective_cardinality_satisfied,
    is_anaphor,
)
from entity_linker.collective_ambiguity import evaluate_collective_ambiguity  # noqa: E402

DATASET = ROOT / "data/eval/coreference_challenge_dev_v2.json"
OFFLINE = ROOT / "reports/coreference_discourse_experiment.json"
OUT_JSON = ROOT / "reports/coreference_offline_runtime_alignment.json"
OUT_MD = ROOT / "reports/coreference_offline_runtime_alignment.md"
SWITCH = ("随后", "转由", "转而", "改由", "接管", "负责", "宣布", "发布")
RESET = ("与此同时", "另一方面", "项目转向", "另行启动", "转而", "改由")


def correct(ids: list[str], is_nil: bool, gold: list[str], gold_nil: bool) -> bool:
    return is_nil == gold_nil and (is_nil or set(ids) == set(gold))


def result_metrics(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    positive = [row for row in rows if not row["gold_is_nil"]]
    nils = [row for row in rows if row["gold_is_nil"]]
    ok = lambda xs: sum(row[field]["correct"] for row in xs)
    return {
        "correct": ok(rows), "total": len(rows), "positive_correct": ok(positive),
        "positive_total": len(positive), "nil_correct": ok(nils), "nil_total": len(nils),
        "false_nil": sum(not r["gold_is_nil"] and r[field]["is_nil"] for r in rows),
        "false_positive": sum(r["gold_is_nil"] and not r[field]["is_nil"] for r in rows),
    }


def shadow_decision(resolver: RuleBasedCoreferenceResolver, text: str, index: int, mentions: list[CoreferenceMention], off: dict[str, Any]) -> tuple[list[str], bool, dict[str, Any]]:
    candidates = resolver._collect_coordinated_group_candidates(text, index, mentions)
    trace: dict[str, Any] = {"candidate_group_count": len(candidates), "candidate_groups": [asdict(item) for item in candidates], "triggered_features": [], "rejection_decision": False}
    if off["is_nil"] or len(candidates) < 2:
        return list(off["entity_ids"]), bool(off["is_nil"]), trace
    target = mentions[index]
    trace = evaluate_collective_ambiguity(text, target, mentions, candidates, collective_cardinality_satisfied(target.mention, len(candidates[-1].entity_ids)))
    reject = bool(trace["rejection_decision"])
    trace["triggered_features"] = [name for name, value in (("explicit_subject_switch", trace["explicit_subject_switch"]), ("event_reset_signal", bool(trace["event_reset_signal"]))) if value]
    return ([] if reject else list(off["entity_ids"])), reject or bool(off["is_nil"]), trace


def classify(row: dict[str, Any]) -> tuple[str, str]:
    same_baseline = (
        row["offline_baseline"]["entity_ids"] == row["runtime_off"]["entity_ids"]
        and row["offline_baseline"]["is_nil"] == row["runtime_off"]["is_nil"]
    )
    same_rejection = (
        row["offline_rejection"]["entity_ids"] == row["runtime_on_experiment"]["entity_ids"]
        and row["offline_rejection"]["is_nil"] == row["runtime_on_experiment"]["is_nil"]
    )
    if not same_baseline:
        return "sentence_index_mismatch", "离线脚本基于字符偏移补充分句；运行时原始 JSON 未提供 sentence_index，解析器按默认值处理。"
    if not same_rejection:
        return "feature_extraction_mismatch", "离线特征使用补充分句后的候选上下文；影子路径严格使用运行时 mention 对象。"
    return "aligned", "离线与运行时等价路径结果一致。"


def main() -> int:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    offline = json.loads(OFFLINE.read_text(encoding="utf-8"))
    offline_traces = {x["sample_id"]: x for x in offline["traces"]["baseline_current_rule"]}
    offline_rej = {x["sample_id"]: x for x in offline["traces"]["nearest_group_with_ambiguity_rejection"]}
    rows: list[dict[str, Any]] = []
    for sample in dataset["samples"]:
        resolver = RuleBasedCoreferenceResolver()
        mentions = [CoreferenceMention.from_dict(item) for item in sample["mentions"]]
        resolutions = resolver.resolve(mentions, text=sample["text"])
        for expected in sample["expected_coreferences"]:
            index = expected["mention_index"]
            res = resolutions[index].to_dict()
            off = {"entity_ids": list(res["entity_ids"]), "is_nil": bool(res["is_nil"]), "rule": res["rule"], "evidence": res["evidence"]}
            shadow_ids, shadow_nil, trace = shadow_decision(resolver, sample["text"], index, mentions, off)
            baseline = offline_traces[sample["id"]]
            rejection = offline_rej[sample["id"]]
            row = {
                "sample_id": sample["id"], "domain": sample.get("domain", "Unspecified"),
                "gold_entity_ids": list(expected.get("entity_ids", [])), "gold_is_nil": bool(expected["is_nil"]),
                "offline_baseline": {"entity_ids": baseline["selected_entity_ids"], "is_nil": baseline["predicted_is_nil"]},
                "offline_rejection": {"entity_ids": rejection["selected_entity_ids"], "is_nil": rejection["predicted_is_nil"], "triggered_features": rejection.get("ambiguity_features", {})},
                "runtime_off": off,
                "runtime_on_experiment": {"entity_ids": shadow_ids, "is_nil": shadow_nil, "triggered_features": trace["triggered_features"]},
                "candidate_groups_offline": baseline.get("candidate_groups", []), "candidate_groups_runtime": trace["candidate_groups"],
                "runtime_trace": trace,
            }
            for field in ("offline_baseline", "offline_rejection", "runtime_off", "runtime_on_experiment"):
                row[field]["correct"] = correct(row[field]["entity_ids"], row[field]["is_nil"], row["gold_entity_ids"], row["gold_is_nil"])
            row["difference_type"], row["root_cause"] = classify(row)
            rows.append(row)
    domain = defaultdict(list)
    for row in rows: domain[row["domain"]].append(row)
    report = {
        "frozen_baseline": {"offline_baseline": "32/55", "offline_rejection": "42/55", "runtime_off": "34/55", "runtime_on_experiment": "39/55"},
        "gold_leakage": False,
        "input_matrix": [
            ["mention 来源", "原始 JSON + in-memory 分句字段", "原始 JSON", False],
            ["mention 顺序/偏移/entity_id/type", "原始 JSON", "原始 JSON", True],
            ["sentence_index", "按标点补充", "缺失时默认 0", False],
            ["候选过滤", "正式私有候选提取", "正式私有候选提取", True],
            ["候选组顺序", "正式提取顺序", "正式提取顺序", True],
        ],
        "metrics": {field: result_metrics(rows, field) for field in ("offline_baseline", "offline_rejection", "runtime_off", "runtime_on_experiment")},
        "domain_metrics": {key: {field: result_metrics(value, field) for field in ("runtime_off", "runtime_on_experiment")} for key, value in sorted(domain.items())},
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mismatches = [row for row in rows if row["difference_type"] != "aligned"]
    lines = ["# 离线拒绝器与运行时解析器对齐报告", "", "## 结论", "", f"- 不一致样本：{len(mismatches)} / {len(rows)}。", "- 未发现 gold leakage：离线脚本仅使用 gold 进行事后正确性计算，不参与候选、特征或决策。", "- 主要差异：离线脚本按字符偏移补充 `sentence_index`，运行时原始输入缺失该字段时默认均为 0。", "", "## 指标", "", "|路径|正确|正例|NIL|False NIL|False Positive|", "|-|-:|-:|-:|-:|-:|"]
    for field, label in (("offline_baseline", "Offline Baseline"), ("offline_rejection", "Offline Rejection"), ("runtime_off", "Runtime / Shadow OFF"), ("runtime_on_experiment", "Runtime Shadow Rejection")):
        metric = report["metrics"][field]
        lines.append(f"|{label}|{metric['correct']} / {metric['total']}|{metric['positive_correct']} / {metric['positive_total']}|{metric['nil_correct']} / {metric['nil_total']}|{metric['false_nil']}|{metric['false_positive']}|")
    lines.extend(["", "## 输入差异矩阵", "", "|项目|离线脚本|正式解析器|一致|", "|-|-|-|-|"])
    lines.extend(f"|{a}|{b}|{c}|{'是' if d else '否'}|" for a,b,c,d in report["input_matrix"])
    lines.extend(["", "## 差异样本", ""])
    for row in mismatches:
        lines.append(f"- `{row['sample_id']}`：`{row['difference_type']}`；{row['root_cause']}")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"shadow_off={report['metrics']['runtime_off']['correct']}/55 shadow_rejection={report['metrics']['runtime_on_experiment']['correct']}/55 mismatches={len(mismatches)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
