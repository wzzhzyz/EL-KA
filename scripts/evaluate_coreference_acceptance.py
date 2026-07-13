#!/usr/bin/env python3
"""Evaluate the fifth acceptance metric against the real coreference resolver.

The official score combines the immutable legacy single-coreference gold with
the runtime-KB collective acceptance gold.  Unit fixtures are intentionally
excluded from the denominator.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ratio(correct: int, total: int) -> float:
    return round(correct / total, 6) if total else 0.0


def git_revision() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def sentence_distance(sample: Mapping[str, Any], expected: Mapping[str, Any]) -> int | None:
    if isinstance(expected.get("sentence_distance"), int):
        return expected["sentence_distance"]
    indices = expected.get("antecedent_indices", [])
    mentions = sample.get("mentions", [])
    target_index = expected.get("mention_index")
    if not indices or not isinstance(target_index, int) or target_index >= len(mentions):
        return None
    target_sentence = int(mentions[target_index].get("sentence_index", 0))
    distances = [abs(target_sentence - int(mentions[index].get("sentence_index", 0))) for index in indices]
    return max(distances) if distances else None


def bucket_rows(counter: Counter[str]) -> list[Dict[str, Any]]:
    keys = sorted({item.rsplit("__", 1)[0] for item in counter})
    return [
        {
            "name": key,
            "total": counter[f"{key}__total"],
            "correct": counter[f"{key}__correct"],
            "wrong": counter[f"{key}__total"] - counter[f"{key}__correct"],
            "accuracy": ratio(counter[f"{key}__correct"], counter[f"{key}__total"]),
        }
        for key in keys
    ]


def classify_error(expected: Mapping[str, Any], predicted: Any) -> str:
    expected_nil = bool(expected.get("is_nil", expected.get("entity_id") is None))
    expected_collective = bool(expected.get("is_collective", False))
    expected_ids = set(expected.get("entity_ids", []))
    predicted_ids = set(predicted.entity_ids)
    if expected_collective:
        if expected_nil:
            if not predicted.is_nil:
                return "false_positive"
            return "collective_flag_error"
        if predicted.is_nil:
            return "false_nil"
        if not predicted.is_collective:
            return "collective_flag_error"
        if predicted_ids < expected_ids:
            return "under_prediction"
        if predicted_ids > expected_ids:
            return "over_prediction"
        return "wrong_entity_set"
    if expected_nil:
        return "false_positive"
    if predicted.is_nil:
        return "false_nil"
    return "wrong_single_entity"


def add_bucket(buckets: dict[str, Counter[str]], name: str, key: str, ok: bool) -> None:
    buckets[name][f"{key}__total"] += 1
    if ok:
        buckets[name][f"{key}__correct"] += 1


def evaluate_dataset(
    dataset: Mapping[str, Any],
    source: str,
    resolver: Any,
    cases: list[Dict[str, Any]],
    buckets: dict[str, Counter[str]],
    set_diagnostic: Counter[str],
) -> None:
    for sample in dataset.get("samples", []):
        mentions = sample.get("mentions", [])
        expected_cases = sample.get("expected_coreferences", [])
        text = sample.get("text", "") if source != "legacy" else ""
        resolutions = resolver.resolve(mentions, text=text)
        for expected in expected_cases:
            mention_index = int(expected["mention_index"])
            mention = mentions[mention_index]
            predicted = resolutions[mention_index]
            expected_nil = bool(expected.get("is_nil", expected.get("entity_id") is None))
            expected_collective = bool(expected.get("is_collective", False))
            expected_id = expected.get("entity_id")
            expected_ids = list(expected.get("entity_ids", []))
            predicted_ids = list(predicted.entity_ids)
            if expected_collective:
                if expected_nil:
                    ok = predicted.is_collective and predicted.is_nil and not predicted_ids
                else:
                    ok = (
                        predicted.is_collective
                        and not predicted.is_nil
                        and set(predicted_ids) == set(expected_ids)
                        and len(predicted_ids) == len(set(predicted_ids))
                    )
                    expected_set, predicted_set = set(expected_ids), set(predicted_ids)
                    set_diagnostic["intersection"] += len(expected_set & predicted_set)
                    set_diagnostic["predicted"] += len(predicted_set)
                    set_diagnostic["expected"] += len(expected_set)
                    if not ok and expected_set & predicted_set:
                        set_diagnostic["partial_match"] += 1
            else:
                ok = predicted.is_nil if expected_nil else (
                    not predicted.is_nil
                    and predicted.entity_id == expected_id
                    and (not predicted_ids or predicted_ids == [expected_id])
                )

            subset = sample.get("subset", "legacy" if source == "legacy" else "blind_holdout" if source == "holdout" else "acceptance_main")
            difficulty = sample.get("difficulty", "legacy")
            distance = sentence_distance(sample, expected)
            sentence_scope = "legacy" if source == "legacy" else ("cross_sentence" if distance and distance > 0 else "same_sentence" if distance == 0 else "no_gold_antecedent")
            antecedent_count = len(expected_ids)
            scenario = expected.get("scenario", "legacy")
            conjunction = expected.get("conjunction", "legacy")
            anaphor = expected.get("anaphor", mention.get("mention", ""))
            positive_nil = "NIL" if expected_nil else "POSITIVE"
            entity_types = sorted({str(mentions[index].get("type", "UNKNOWN")) for index in expected.get("antecedent_indices", [])})
            entity_type = "+".join(entity_types) if entity_types else "NIL_OR_UNLINKED"
            for bucket, key in {
                "source": source,
                "subset": subset,
                "difficulty": difficulty,
                "anaphor": anaphor,
                "conjunction": conjunction,
                "sentence_scope": sentence_scope,
                "antecedent_count": str(antecedent_count),
                "entity_type": entity_type,
                "positive_or_nil": positive_nil,
                "scenario": scenario,
            }.items():
                add_bucket(buckets, bucket, str(key), ok)

            record = {
                "source": source,
                "sample_id": sample.get("id"),
                "text": sample.get("text", ""),
                "mention_index": mention_index,
                "mention": mention.get("mention"),
                "subset": subset,
                "difficulty": difficulty,
                "scenario": scenario,
                "conjunction": conjunction,
                "sentence_distance": distance,
                "gold_entity_id": expected_id,
                "gold_entity_ids": expected_ids,
                "gold_is_collective": expected_collective,
                "gold_is_nil": expected_nil,
                "predicted_entity_id": predicted.entity_id,
                "predicted_entity_ids": predicted_ids,
                "predicted_is_collective": predicted.is_collective,
                "predicted_is_nil": predicted.is_nil,
                "rule": predicted.rule,
                "evidence": predicted.evidence,
                "is_correct": ok,
            }
            if not ok:
                record["error_type"] = classify_error(expected, predicted)
            cases.append(record)


def metric(cases: Iterable[Mapping[str, Any]], predicate) -> Dict[str, Any]:
    rows = [item for item in cases if predicate(item)]
    correct = sum(bool(item["is_correct"]) for item in rows)
    return {"total": len(rows), "correct": correct, "wrong": len(rows) - correct, "accuracy": ratio(correct, len(rows))}


def markdown(report: Mapping[str, Any]) -> str:
    overall = report["metrics"]["overall"]
    lines = [
        "# 共指消解第五项验收报告",
        "",
        "## 1. 验收标准",
        "",
        "共指消解准确率 ≥80%。正式总体不计入 `coreference_collective_test.json` 单元夹具。",
        "",
        "## 2. 评测环境",
        "",
        f"- 代码版本：`{report['environment']['git_revision'] or 'unknown'}`",
        "- 共指模块入口：`entity_linker.coreference.RuleBasedCoreferenceResolver`",
        "- 调用方式：直接实例化真实解析器，对真实输出与 gold 比较；未使用 mock 或 gold 预测。",
        f"- 历史数据：`{report['inputs']['legacy']}`",
        f"- 正式集合数据：`{report['inputs']['collective']}`",
        f"- Blind Holdout：`{report['inputs']['holdout'] or '未运行'}`",
        "",
        "## 3. 数据规模",
        "",
        f"- 历史单实体 case：{report['metrics']['legacy_single']['total']}",
        f"- 正式集合 case：{report['metrics']['collective_all']['total']}（正例 {report['metrics']['collective_positive']['total']}；集合 NIL {report['metrics']['collective_nil']['total']}）",
        f"- `acceptance_main`：{report['metrics']['acceptance_main']['total']}；`challenge_dev`：{report['metrics']['challenge_dev']['total']}；`blind_holdout`：{report['metrics']['blind_holdout']['total']}",
        "",
        "## 4. 总体结果",
        "",
        "|指标|结果|阈值|结论|",
        "|-|-:|-:|-|",
        f"|Overall Coreference Accuracy|{overall['accuracy']:.2%} ({overall['correct']}/{overall['total']})|80.00%|{'PASS' if report['acceptance']['passed'] else 'FAIL'}|",
        "",
        "## 5. 分类结果",
        "",
        "|指标|结果|",
        "|-|-|",
    ]
    for key, label in (
        ("legacy_single", "Legacy Single Accuracy"),
        ("single_positive", "Single Positive Accuracy"),
        ("single_nil", "Single NIL Accuracy"),
        ("collective_exact_match", "Collective Exact Match Accuracy"),
        ("collective_positive", "Collective Positive Accuracy"),
        ("collective_nil", "Collective NIL Accuracy"),
        ("acceptance_main", "Acceptance Main Accuracy"),
        ("challenge_dev", "Challenge Dev Accuracy"),
        ("blind_holdout", "Blind Holdout Accuracy"),
        ("blind_holdout_positive", "Blind Holdout Positive Exact Match"),
        ("blind_holdout_nil", "Blind Holdout NIL Accuracy"),
    ):
        row = report["metrics"][key]
        lines.append(f"|{label}|{row['accuracy']:.2%} ({row['correct']}/{row['total']})|")
    lines += ["", "## 6. 场景分组", ""]
    for name in ("subset", "difficulty", "conjunction", "sentence_scope", "antecedent_count", "positive_or_nil"):
        lines += [f"### {name}", "", "|分组|正确 / 总数|准确率|", "|-|-:|-:|"]
        lines += [f"|`{row['name']}`|{row['correct']} / {row['total']}|{row['accuracy']:.2%}|" for row in report["breakdown"][name]]
        lines.append("")
    lines += ["## 7. Badcase", ""]
    if not report["badcases"]:
        lines.append("- 无失败 case。")
    else:
        lines += ["|Sample|指代|错误类型|gold|预测|规则|", "|-|-|-|-|-|-|"]
        for item in report["badcases"]:
            lines.append(f"|`{item['sample_id']}`|{item['mention']}|`{item['error_type']}`|`{item['gold_entity_ids'] or item['gold_entity_id']}`|`{item['predicted_entity_ids'] or item['predicted_entity_id']}`|`{item['rule']}`|")
    lines += [
        "",
        "## 8. 当前限制",
        "",
        "- 当前规则以同句显式并列为主，跨句隐式集合、未覆盖连接词和非 ORG/PERSON 集合会暴露失败；",
        "- 运行知识库缺少可用 PERSON 实体，PERSON 集合正例未纳入端到端 KB 评测；",
        "- Challenge Dev 已参与规则开发，不能作为最终泛化指标；Blind Holdout 在规则冻结后一次性运行，不能据此继续调规则。",
        "",
        "## 9. 最终验收结论",
        "",
        f"正式共指准确率为 **{overall['accuracy']:.2%}**，阈值为 **80.00%**，结论：**{'PASS' if report['acceptance']['passed'] else 'FAIL'}**。数据质量通过与该算法验收结论分别由质量审计和本脚本的真实解析输出支撑。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fifth acceptance metric for real coreference resolution.")
    parser.add_argument("--legacy", default="data/eval/coreference_long_text_test.json")
    parser.add_argument("--collective", default="data/eval/coreference_collective_eval.json")
    parser.add_argument("--holdout", default=None, help="冻结后一次性运行的独立 blind holdout；不计入既有统一总体。")
    parser.add_argument("--output-json", default="reports/coreference_acceptance_result.json")
    parser.add_argument("--output-md", default="reports/coreference_acceptance_result.md")
    parser.add_argument("--acceptance-output-json", default=None, help="可选：同一次评测额外写入统一验收 JSON。")
    parser.add_argument("--acceptance-output-md", default=None, help="可选：同一次评测额外写入统一验收 Markdown。")
    parser.add_argument("--threshold", type=float, default=0.80)
    args = parser.parse_args()

    from entity_linker.coreference import RuleBasedCoreferenceResolver

    resolver = RuleBasedCoreferenceResolver()
    cases: list[Dict[str, Any]] = []
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    set_diagnostic: Counter[str] = Counter()
    evaluate_dataset(load(ROOT / args.legacy), "legacy", resolver, cases, buckets, set_diagnostic)
    evaluate_dataset(load(ROOT / args.collective), "collective", resolver, cases, buckets, set_diagnostic)
    if args.holdout:
        evaluate_dataset(load(ROOT / args.holdout), "holdout", resolver, cases, buckets, set_diagnostic)

    metrics = {
        # Keep the project’s pre-holdout unified denominator stable.  The
        # frozen holdout is reported separately and is never used to tune rules.
        "overall": metric(cases, lambda row: row["source"] != "holdout"),
        "all_evaluated": metric(cases, lambda _: True),
        "legacy_single": metric(cases, lambda row: row["source"] == "legacy"),
        "single_positive": metric(cases, lambda row: not row["gold_is_collective"] and not row["gold_is_nil"]),
        "single_nil": metric(cases, lambda row: not row["gold_is_collective"] and row["gold_is_nil"]),
        "collective_all": metric(cases, lambda row: row["source"] != "holdout" and row["gold_is_collective"]),
        "collective_exact_match": metric(cases, lambda row: row["source"] != "holdout" and row["gold_is_collective"] and not row["gold_is_nil"]),
        "collective_positive": metric(cases, lambda row: row["source"] != "holdout" and row["gold_is_collective"] and not row["gold_is_nil"]),
        "collective_nil": metric(cases, lambda row: row["source"] != "holdout" and row["gold_is_collective"] and row["gold_is_nil"]),
        "acceptance_main": metric(cases, lambda row: row["source"] == "collective" and row["subset"] != "challenge_dev"),
        "challenge_dev": metric(cases, lambda row: row["source"] == "collective" and row["subset"] == "challenge_dev"),
        "blind_holdout": metric(cases, lambda row: row["source"] == "holdout"),
        "blind_holdout_positive": metric(cases, lambda row: row["source"] == "holdout" and row["gold_is_collective"] and not row["gold_is_nil"]),
        "blind_holdout_nil": metric(cases, lambda row: row["source"] == "holdout" and row["gold_is_collective"] and row["gold_is_nil"]),
    }
    precision = ratio(set_diagnostic["intersection"], set_diagnostic["predicted"])
    recall = ratio(set_diagnostic["intersection"], set_diagnostic["expected"])
    f1 = round(2 * precision * recall / (precision + recall), 6) if precision + recall else 0.0
    badcases = [row for row in cases if not row["is_correct"]]
    report = {
        "report_version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {"legacy": args.legacy, "collective": args.collective, "holdout": args.holdout, "excluded_unit_fixture": "data/eval/coreference_collective_test.json", "excluded_failure_regression": "data/eval/coreference_failure_regression.json"},
        "environment": {"git_revision": git_revision(), "resolver": "entity_linker.coreference.RuleBasedCoreferenceResolver", "nil_threshold": resolver.nil_threshold, "max_sentence_gap": resolver.max_sentence_gap},
        "acceptance": {"threshold": args.threshold, "passed": metrics["overall"]["accuracy"] >= args.threshold, "definition": "correct coreference cases / all official legacy + collective cases"},
        "metrics": metrics,
        "set_diagnostics": {"entity_set_precision": precision, "entity_set_recall": recall, "entity_set_f1": f1, "partial_match_count": set_diagnostic["partial_match"]},
        "breakdown": {name: bucket_rows(counter) for name, counter in buckets.items()},
        "cases": cases,
        "badcases": badcases,
        "error_type_counts": dict(Counter(row["error_type"] for row in badcases)),
    }
    json_path, md_path = ROOT / args.output_json, ROOT / args.output_md
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown(report), encoding="utf-8")
    for optional_path, content in ((args.acceptance_output_json, json.dumps(report, ensure_ascii=False, indent=2) + "\n"), (args.acceptance_output_md, markdown(report))):
        if optional_path:
            path = ROOT / optional_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    overall = metrics["overall"]
    print(f"Overall Coreference Accuracy: {overall['accuracy']:.2%} ({overall['correct']}/{overall['total']})")
    print(f"Acceptance Threshold: {args.threshold:.2%}")
    print(f"Acceptance Result: {'PASS' if report['acceptance']['passed'] else 'FAIL'}")
    print(f"Badcases: {len(badcases)}")
    return 0 if report["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
