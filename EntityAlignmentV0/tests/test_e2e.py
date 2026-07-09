# tests/test_e2e_with_mentions.py
"""
端到端实体链接测试模块（给定 mention 版本）

测试流程：
1. 从 batch_ground_truth.json 读取 (text, mention, expected_entity_id)
2. 执行链接流水线（跳过 NER，直接使用给定的 mention）
3. 输出链接结果并验证
4. 收集错误案例并分类
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.linker import EntityLinker
from src.utils.config import load_config
from src.utils.logger import logger
from src.models.mention import StandardMention


@dataclass
class TestCase:
    """测试用例"""
    text_idx: int
    text: str
    mention: str
    expected_entity_id: Optional[str]
    expected_standard_name: Optional[str]
    scenario: str = ""
    has_nil: bool = False


@dataclass
class TestResult:
    """单个测试结果"""
    text_idx: int
    text: str
    mention: str
    scenario: str
    expected_entity_id: Optional[str]
    expected_standard_name: Optional[str]
    actual_entity_id: Optional[str]
    actual_standard_name: Optional[str]
    confidence: float
    method: str
    evidence: str
    passed: bool
    errors: List[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


@dataclass
class ErrorCase:
    """错误案例"""
    text_idx: int
    text: str
    mention: str
    scenario: str
    error_type: str
    expected_entity_id: Optional[str]
    expected_standard_name: Optional[str]
    actual_entity_id: Optional[str]
    actual_standard_name: Optional[str]
    confidence: float
    evidence: str
    detail: str = ""


class E2ETester:
    """端到端测试器（给定 mention 版本）"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"

        self.config = load_config(str(config_path))
        self.linker = EntityLinker(self.config)
        self.results: List[TestResult] = []
        self.error_cases: List[ErrorCase] = []
        self.passed = 0
        self.failed = 0

        print("\n" + "=" * 80)
        print("端到端实体链接测试（给定 mention）")
        print("=" * 80)
        print(f"配置: {config_path}")
        print(f"LLM兜底: {'启用' if self.linker.disambiguator.enable_llm else '禁用'}")
        print(f"NIL阈值: {self.linker.disambiguator.nil_threshold}")
        print("=" * 80)

    def load_data(self, texts_path: str, ground_truth_path: str) -> List[TestCase]:
        """加载测试数据和标准答案，展开为每个 mention 一个测试用例"""
        # 加载文本
        with open(texts_path, "r", encoding="utf-8") as f:
            texts = [line.strip() for line in f.readlines() if line.strip()]

        # 加载标准答案
        with open(ground_truth_path, "r", encoding="utf-8") as f:
            gt_data = json.load(f)

        test_cases = []
        for entry in gt_data.get("entries", []):
            text_idx = entry.get("text_idx", -1)
            scenario = entry.get("scenario", "")

            # 每个 expected_entities 中的实体作为一个独立的测试用例
            for exp in entry.get("expected_entities", []):
                mention = exp.get("mention", "")
                entity_id = exp.get("entity_id")

                # 获取标准实体名
                standard_name = None
                if entity_id:
                    # 从知识库获取标准名称
                    entity = self.linker.kb.get_entity_by_id(entity_id)
                    if entity:
                        standard_name = entity.standard_name

                test_cases.append(TestCase(
                    text_idx=text_idx,
                    text=texts[text_idx] if text_idx < len(texts) else "",
                    mention=mention,
                    expected_entity_id=entity_id,
                    expected_standard_name=standard_name,
                    scenario=scenario,
                    has_nil=entity_id is None
                ))

        print(f"\n📋 加载测试数据:")
        print(f"   文本数: {len(texts)}")
        print(f"   测试用例数: {len(test_cases)}")
        print(f"   含 NIL 用例: {sum(1 for tc in test_cases if tc.has_nil)}")
        print(f"   非 NIL 用例: {sum(1 for tc in test_cases if not tc.has_nil)}")

        return test_cases

    def run_single_test(self, test_case: TestCase) -> TestResult:
        """运行单个测试用例"""
        start_time = time.time()

        result = TestResult(
            text_idx=test_case.text_idx,
            text=test_case.text[:100] + "..." if len(test_case.text) > 100 else test_case.text,
            mention=test_case.mention,
            scenario=test_case.scenario,
            expected_entity_id=test_case.expected_entity_id,
            expected_standard_name=test_case.expected_standard_name,
            actual_entity_id=None,
            actual_standard_name=None,
            confidence=0.0,
            method="",
            evidence="",
            passed=False,
            errors=[]
        )

        try:
            # 构建 StandardMention
            mention_obj = StandardMention(
                mention=test_case.mention,
                mention_type="UNKNOWN",
                char_start=0,
                char_end=len(test_case.mention)
            )

            # 执行链接（跳过 NER）
            output = self.linker.link_with_mentions(
                test_case.text,
                [mention_obj.to_dict()],
                {"nil_threshold": self.linker.disambiguator.nil_threshold}
            )

            # 提取结果
            if output.get("results"):
                r = output["results"][0]
                result.actual_entity_id = r.get("entity_id")
                result.actual_standard_name = r.get("standard_entity")
                result.confidence = r.get("confidence", 0.0)
                result.method = r.get("method", "")
                result.evidence = r.get("evidence", "")
            else:
                result.actual_entity_id = None
                result.actual_standard_name = None
                result.confidence = 0.0
                result.method = "none"
                result.evidence = "无结果"

            # ============================================================
            # 验证逻辑
            # ============================================================
            expected_id = test_case.expected_entity_id
            actual_id = result.actual_entity_id

            # 情况1：期望 NIL
            if expected_id is None:
                if actual_id is None:
                    result.passed = True
                else:
                    result.errors.append(f"期望 NIL，实际链接到 {actual_id} ({result.actual_standard_name})")
                    self.error_cases.append(ErrorCase(
                        text_idx=test_case.text_idx,
                        text=result.text,
                        mention=test_case.mention,
                        scenario=test_case.scenario,
                        error_type="nil_mismatch",
                        expected_entity_id=None,
                        expected_standard_name="NIL",
                        actual_entity_id=actual_id,
                        actual_standard_name=result.actual_standard_name,
                        confidence=result.confidence,
                        evidence=result.evidence,
                        detail=f"期望 NIL 但链接到实体"
                    ))

            # 情况2：期望非 NIL
            else:
                if actual_id is None:
                    result.errors.append(f"期望 {expected_id} ({test_case.expected_standard_name})，实际 NIL")
                    self.error_cases.append(ErrorCase(
                        text_idx=test_case.text_idx,
                        text=result.text,
                        mention=test_case.mention,
                        scenario=test_case.scenario,
                        error_type="nil_mismatch",
                        expected_entity_id=expected_id,
                        expected_standard_name=test_case.expected_standard_name,
                        actual_entity_id=None,
                        actual_standard_name="NIL",
                        confidence=result.confidence,
                        evidence=result.evidence,
                        detail=f"期望实体但被判为NIL"
                    ))
                elif actual_id != expected_id:
                    result.errors.append(
                        f"期望 {expected_id} ({test_case.expected_standard_name})，实际 {actual_id} ({result.actual_standard_name})")
                    self.error_cases.append(ErrorCase(
                        text_idx=test_case.text_idx,
                        text=result.text,
                        mention=test_case.mention,
                        scenario=test_case.scenario,
                        error_type="wrong_entity",
                        expected_entity_id=expected_id,
                        expected_standard_name=test_case.expected_standard_name,
                        actual_entity_id=actual_id,
                        actual_standard_name=result.actual_standard_name,
                        confidence=result.confidence,
                        evidence=result.evidence,
                        detail=f"链接到错误实体"
                    ))
                else:
                    result.passed = True

        except Exception as e:
            result.errors.append(f"执行异常: {str(e)}")
            result.passed = False
            self.error_cases.append(ErrorCase(
                text_idx=test_case.text_idx,
                text=result.text,
                mention=test_case.mention,
                scenario=test_case.scenario,
                error_type="exception",
                expected_entity_id=test_case.expected_entity_id,
                expected_standard_name=test_case.expected_standard_name,
                actual_entity_id=None,
                actual_standard_name=None,
                confidence=0.0,
                evidence=str(e),
                detail=f"执行异常: {str(e)}"
            ))
            import traceback
            traceback.print_exc()

        elapsed = (time.time() - start_time) * 1000
        result.elapsed_ms = elapsed

        return result

    def run_all_tests(self, texts_path: str = None, ground_truth_path: str = None):
        """运行所有测试"""
        if texts_path is None:
            texts_path = Path(__file__).parent.parent / "data" / "batch_texts.txt"
        if ground_truth_path is None:
            ground_truth_path = Path(__file__).parent.parent / "data" / "batch_ground_truth.json"

        test_cases = self.load_data(str(texts_path), str(ground_truth_path))

        print("\n开始执行端到端测试...")
        print("-" * 80)

        total = len(test_cases)

        for i, test_case in enumerate(test_cases):
            print(f"\n[{i + 1}/{total}] 测试: {test_case.scenario}")
            print(f"  📝 {test_case.text[:60]}...")
            print(f"  🔍 Mention: '{test_case.mention}'")
            print(f"  📌 期望: {test_case.expected_entity_id or 'NIL'} ({test_case.expected_standard_name or 'NIL'})")

            result = self.run_single_test(test_case)
            self.results.append(result)

            if result.passed:
                self.passed += 1
                print(f"  ✅ PASS → {result.actual_entity_id or 'NIL'} (置信度: {result.confidence:.3f})")
            else:
                self.failed += 1
                print(f"  ❌ FAIL → {result.actual_entity_id or 'NIL'} (置信度: {result.confidence:.3f})")
                for err in result.errors:
                    print(f"     ⚠️ {err}")

        self.print_summary()
        self.print_error_cases()
        self.save_results()

    def print_summary(self):
        """打印测试汇总"""
        print("\n" + "=" * 80)
        print("端到端测试汇总（给定 mention）")
        print("=" * 80)

        total = self.passed + self.failed
        print(f"总测试用例数: {total}")
        print(f"通过: {self.passed} ✅")
        print(f"失败: {self.failed} ❌")
        print(f"通过率: {self.passed / total * 100:.1f}%" if total > 0 else "通过率: 0%")
        print(f"\n失败用例数: {len(self.error_cases)}")

        # 按错误类型统计
        if self.error_cases:
            print("\n📊 错误类型分布:")
            error_types = {}
            for case in self.error_cases:
                error_types[case.error_type] = error_types.get(case.error_type, 0) + 1
            for err_type, count in error_types.items():
                print(f"  {err_type}: {count}")

            # 按场景统计
            print("\n📊 按场景统计:")
            scenario_stats = {}
            for case in self.error_cases:
                scenario_stats[case.scenario] = scenario_stats.get(case.scenario, 0) + 1
            for scenario, count in sorted(scenario_stats.items(), key=lambda x: -x[1]):
                print(f"  {scenario}: {count}")

    def print_error_cases(self):
        """打印所有错误案例"""
        if not self.error_cases:
            print("\n✅ 所有测试通过！")
            return

        print("\n" + "=" * 80)
        print(f"❌ 错误案例详情 (共 {len(self.error_cases)} 个)")
        print("=" * 80)

        # 按错误类型分组
        by_type = {}
        for case in self.error_cases:
            by_type.setdefault(case.error_type, []).append(case)

        for error_type, cases in by_type.items():
            print(f"\n【{error_type}】({len(cases)} 个)")
            print("-" * 60)
            for case in cases[:10]:
                print(f"  文本 #{case.text_idx}: {case.text[:50]}...")
                print(f"  Mention: '{case.mention}'")
                print(f"  场景: {case.scenario}")
                print(f"  期望: {case.expected_entity_id or 'NIL'} ({case.expected_standard_name or 'NIL'})")
                print(f"  实际: {case.actual_entity_id or 'NIL'} ({case.actual_standard_name or 'NIL'})")
                print(f"  置信度: {case.confidence:.4f}")
                print(f"  依据: {case.evidence[:100]}...")
                if case.detail:
                    print(f"  详情: {case.detail}")
                print()

    def save_results(self):
        """保存测试结果"""
        output_dir = Path("tests/output")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存详细结果
        result_data = []
        for r in self.results:
            result_data.append({
                "text_idx": r.text_idx,
                "text": r.text,
                "mention": r.mention,
                "scenario": r.scenario,
                "expected_entity_id": r.expected_entity_id,
                "expected_standard_name": r.expected_standard_name,
                "actual_entity_id": r.actual_entity_id,
                "actual_standard_name": r.actual_standard_name,
                "confidence": r.confidence,
                "method": r.method,
                "evidence": r.evidence,
                "passed": r.passed,
                "errors": r.errors,
                "elapsed_ms": r.elapsed_ms
            })

        # 保存错误案例
        error_data = []
        for case in self.error_cases:
            error_data.append({
                "text_idx": case.text_idx,
                "text": case.text,
                "mention": case.mention,
                "scenario": case.scenario,
                "error_type": case.error_type,
                "expected_entity_id": case.expected_entity_id,
                "expected_standard_name": case.expected_standard_name,
                "actual_entity_id": case.actual_entity_id,
                "actual_standard_name": case.actual_standard_name,
                "confidence": case.confidence,
                "evidence": case.evidence,
                "detail": case.detail
            })

        result_file = output_dir / f"e2e_with_mentions_test_{timestamp}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": self.passed + self.failed,
                    "passed": self.passed,
                    "failed": self.failed,
                    "pass_rate": f"{self.passed / (self.passed + self.failed) * 100:.1f}%" if (
                                                                                                          self.passed + self.failed) > 0 else "0%"
                },
                "error_cases": error_data,
                "all_results": result_data
            }, f, ensure_ascii=False, indent=2)

        print(f"\n📄 测试结果已保存: {result_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="端到端实体链接测试（给定 mention）")
    parser.add_argument("--texts", type=str, help="测试文本文件路径")
    parser.add_argument("--gt", type=str, help="标准答案文件路径")
    args = parser.parse_args()

    tester = E2ETester()
    tester.run_all_tests(args.texts, args.gt)


if __name__ == "__main__":
    main()