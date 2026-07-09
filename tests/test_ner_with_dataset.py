# tests/test_ner_with_dataset.py
import sys
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.ner import NEREngine
from src.utils.config import load_config
from src.utils.logger import logger


@dataclass
class TestCase:
    """测试用例"""
    id: str
    text: str
    expected: List[Dict[str, Any]]
    scenario: str = ""
    note: str = ""
    check_position: bool = True


@dataclass
class TestResult:
    """单个测试结果"""
    test_id: str
    text: str
    scenario: str
    note: str
    expected: List[Dict[str, Any]]
    actual: List[Dict[str, Any]]
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


class NERDatasetTester:
    """基于数据集的 NER 测试器"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.ner = NEREngine(self.config["ner"])
        self.results: List[TestResult] = []
        self.linkable_types = set(self.config["ner"].get("linkable_types", ["ORG", "PERSON", "GPE", "LOC"]))

    def load_dataset(self, dataset_path: str) -> List[TestCase]:
        """加载测试数据集"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(project_root, dataset_path)

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"数据集不存在: {full_path}")

        with open(full_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        test_cases = []
        for sample in data.get("samples", []):
            expected = []
            for exp in sample.get("expected", []):
                expected.append({
                    "mention": exp.get("mention", ""),
                    "char_start": exp.get("start", 0),
                    "char_end": exp.get("end", 0)
                })

            test_cases.append(TestCase(
                id=sample.get("id", "UNKNOWN"),
                text=sample.get("text", ""),
                expected=expected,
                scenario=sample.get("scenario", ""),
                note=sample.get("note", ""),
                check_position=True
            ))

        return test_cases

    def run_test_case(self, test_case: TestCase) -> TestResult:
        """运行单个测试用例"""
        start_time = datetime.now()

        result = TestResult(
            test_id=test_case.id,
            text=test_case.text,
            scenario=test_case.scenario,
            note=test_case.note,
            expected=test_case.expected,
            actual=[],
            passed=False,
            errors=[],
            warnings=[]
        )

        try:
            # 执行 NER
            mentions = self.ner.extract(test_case.text)

            # 转换为字典列表（只保留 mention 和位置）
            actual = [
                {
                    "mention": m.mention,
                    "char_start": m.char_start,
                    "char_end": m.char_end
                }
                for m in mentions
            ]
            result.actual = actual

            # 如果没有期望结果
            if not test_case.expected:
                result.passed = True
                result.warnings.append("没有期望结果，仅记录实际输出")
                return result

            # ============================================================
            # 检查匹配（只检查实体是否存在和位置是否正确）
            # ============================================================
            expected_mentions = [e.get("mention", "") for e in test_case.expected]
            actual_mentions = [a.get("mention", "") for a in actual]

            # 检查遗漏
            missing = set(expected_mentions) - set(actual_mentions)
            if missing:
                result.errors.append(f"遗漏实体: {list(missing)}")

            # 检查多余（仅警告，不算失败）
            extra = set(actual_mentions) - set(expected_mentions)
            if extra:
                result.warnings.append(f"额外识别: {list(extra)}")

            # 检查位置
            if test_case.check_position:
                for exp in test_case.expected:
                    exp_mention = exp.get("mention", "")
                    exp_start = exp.get("char_start")
                    exp_end = exp.get("char_end")

                    if exp_start is None or exp_end is None:
                        continue

                    actual_match = next((a for a in actual if a["mention"] == exp_mention), None)
                    if actual_match:
                        actual_start = actual_match.get("char_start", -1)
                        actual_end = actual_match.get("char_end", -1)

                        if actual_start != exp_start:
                            result.errors.append(
                                f"起始位置错误: '{exp_mention}' 期望 {exp_start}, 实际 {actual_start}"
                            )
                        if actual_end != exp_end:
                            result.errors.append(
                                f"结束位置错误: '{exp_mention}' 期望 {exp_end}, 实际 {actual_end}"
                            )

                        # 验证提取的文本是否匹配
                        extracted = test_case.text[actual_start:actual_end]
                        if extracted != exp_mention:
                            result.errors.append(
                                f"位置提取错误: '{exp_mention}' 在 [{actual_start}:{actual_end}] 提取到 '{extracted}'"
                            )

            result.passed = len(result.errors) == 0

        except Exception as e:
            result.errors.append(f"执行错误: {str(e)}")
            result.passed = False

        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        result.elapsed_ms = elapsed

        return result

    def run_batch(self, test_cases: List[TestCase]) -> Dict:
        """批量运行测试用例"""
        logger.info(f"🧪 开始 NER 数据集测试，共 {len(test_cases)} 个用例")

        self.results = []
        passed_count = 0
        failed_count = 0

        for i, case in enumerate(test_cases):
            result = self.run_test_case(case)
            self.results.append(result)

            if result.passed:
                passed_count += 1
            else:
                failed_count += 1

            # 打印进度
            status = "✅" if result.passed else "❌"
            logger.info(f"  [{i + 1}/{len(test_cases)}] {status} {result.test_id} - {result.scenario[:30]}...")

        summary = {
            "total": len(test_cases),
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate": passed_count / len(test_cases) if test_cases else 0,
            "results": self.results
        }

        logger.info(f"📊 测试完成: 通过 {passed_count}, 失败 {failed_count}, 通过率 {summary['pass_rate']:.1%}")

        return summary

    def print_report(self, summary: Dict):
        """打印测试报告"""
        print("\n" + "=" * 80)
        print("📊 NER 数据集测试报告")
        print("=" * 80)
        print(f"  总用例数: {summary['total']}")
        print(f"  ✅ 通过: {summary['passed']}")
        print(f"  ❌ 失败: {summary['failed']}")
        print(f"  📈 通过率: {summary['pass_rate']:.1%}")

        # 按场景分组统计
        scenario_stats = {}
        for r in summary["results"]:
            scenario = r.scenario or "未分类"
            if scenario not in scenario_stats:
                scenario_stats[scenario] = {"total": 0, "passed": 0}
            scenario_stats[scenario]["total"] += 1
            if r.passed:
                scenario_stats[scenario]["passed"] += 1

        print("\n" + "-" * 80)
        print("📂 按场景分组统计:")
        print("-" * 80)
        for scenario, stats in sorted(scenario_stats.items()):
            rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f"  {scenario}: {stats['passed']}/{stats['total']} ({rate:.1f}%)")

        # 打印失败用例详情
        if summary["failed"] > 0:
            print("\n" + "-" * 80)
            print("❌ 失败用例详情:")
            print("-" * 80)
            for result in summary["results"]:
                if not result.passed:
                    print(f"\n  {result.test_id} [{result.scenario}]")
                    print(f"  📝 {result.text[:60]}...")
                    print(f"  期望: {[e['mention'] for e in result.expected]}")
                    print(f"  实际: {[a['mention'] for a in result.actual]}")
                    for error in result.errors:
                        print(f"  ⚠️ {error}")

        # 打印有警告的用例
        warning_results = [r for r in summary["results"] if r.warnings]
        if warning_results:
            print("\n" + "-" * 80)
            print("⚠️ 有警告的用例:")
            print("-" * 80)
            for result in warning_results[:10]:
                print(f"\n  {result.test_id}: {result.scenario}")
                for warning in result.warnings:
                    print(f"  💡 {warning}")

    def save_report(self, summary: Dict, output_file: str = None):
        """保存测试报告到 JSON 文件"""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"reports/ner_dataset_test_{timestamp}.json"

        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # 按场景统计
        scenario_stats = {}
        for r in summary["results"]:
            scenario = r.scenario or "未分类"
            if scenario not in scenario_stats:
                scenario_stats[scenario] = {"total": 0, "passed": 0, "failed": 0}
            scenario_stats[scenario]["total"] += 1
            if r.passed:
                scenario_stats[scenario]["passed"] += 1
            else:
                scenario_stats[scenario]["failed"] += 1

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": summary["total"],
                "passed": summary["passed"],
                "failed": summary["failed"],
                "pass_rate": summary["pass_rate"]
            },
            "scenario_stats": scenario_stats,
            "details": []
        }

        for r in summary["results"]:
            report["details"].append({
                "test_id": r.test_id,
                "scenario": r.scenario,
                "note": r.note,
                "text": r.text,
                "text_length": len(r.text),
                "expected": r.expected,
                "actual": r.actual,
                "passed": r.passed,
                "errors": r.errors,
                "warnings": r.warnings,
                "elapsed_ms": r.elapsed_ms
            })

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"📄 报告已保存: {output_file}")
        return output_file


# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 80)
    print("🧪 NER 数据集测试")
    print("=" * 80)

    tester = NERDatasetTester()

    dataset_path = "data/ner_test_dataset.json"

    try:
        print(f"\n📋 加载数据集: {dataset_path}")
        test_cases = tester.load_dataset(dataset_path)
        print(f"   加载测试用例: {len(test_cases)} 个")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    summary = tester.run_batch(test_cases)
    tester.print_report(summary)

    report_file = tester.save_report(summary)
    print(f"\n📄 报告已保存: {report_file}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())