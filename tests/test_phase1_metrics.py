# tests/test_phase1_metrics.py
"""
阶段一基础效果指标测试模块

测试指标：
1. 实体召回率（Recall）：标准实体能否被正确召回（进入候选列表）
2. 别名召回能力：别名/简称能否正确匹配到标准实体
3. 候选生成质量：候选列表中是否包含正确的标准实体
4. 链接准确率（Precision）：消歧后正确链接的比例（新增）
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.linker import EntityLinker
from src.core.candidate import CandidateGenerator
from src.knowledge.kb_manager import KnowledgeBase
from src.knowledge.vector_index import VectorIndex
from src.models.mention import StandardMention
from src.models.entity import StandardEntity
from src.models.candidate import Candidate
from src.utils.config import load_config
from src.utils.logger import logger


@dataclass
class TestCase:
    """测试用例"""
    text_idx: int
    text: str
    mention: str
    mention_type: str
    expected_entity_id: Optional[str]
    expected_standard_name: Optional[str]
    scenario: str = ""
    has_nil: bool = False
    char_start: int = 0
    char_end: int = 0


@dataclass
class TestResult:
    """单个测试结果"""
    text_idx: int
    mention: str
    expected_entity_id: Optional[str]
    expected_standard_name: Optional[str]
    scenario: str
    # 候选生成结果
    candidates: List[Candidate]
    candidate_count: int
    has_correct_entity: bool
    correct_entity_rank: Optional[int]
    correct_entity_score: Optional[float]
    # 消歧结果（新增）
    disambiguation_result: Optional[Dict[str, Any]]
    disambiguation_entity_id: Optional[str]
    disambiguation_entity_name: Optional[str]
    disambiguation_score: Optional[float]
    disambiguation_method: Optional[str]
    # 别名匹配结果
    alias_matched: bool
    alias_match_score: Optional[float]
    # 向量检索结果
    vector_retrieved: bool
    vector_retrieved_score: Optional[float]
    # 指标
    recalled: bool  # 候选生成是否召回
    linked_correctly: bool  # 消歧是否链接正确
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
    error_type: str  # "no_candidate", "not_in_top_k", "wrong_link", "nil_mismatch"
    expected_entity_id: Optional[str]
    expected_standard_name: Optional[str]
    actual_entity_id: Optional[str]
    actual_standard_name: Optional[str]
    detail: str = ""


class Phase1MetricsTester:
    """阶段一基础效果指标测试器"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"

        self.config = load_config(str(config_path))

        # 初始化完整链接器（用于消歧）
        self.linker = EntityLinker(self.config)

        # 初始化知识库
        self.kb = self.linker.kb

        # 构建实体映射
        self.entity_by_id = {}
        self.entity_by_name = {}
        self.id_to_name = {}
        for entity in self.kb.get_all_entities():
            self.entity_by_id[entity.entity_id] = entity
            self.entity_by_name[entity.standard_name] = entity
            self.id_to_name[entity.entity_id] = entity.standard_name

        self.results: List[TestResult] = []
        self.error_cases: List[ErrorCase] = []
        self.passed = 0
        self.failed = 0
        self.total_candidates_generated = 0

        # 统计指标
        self.metrics = {
            "total": 0,
            "non_nil": 0,
            "nil": 0,
            # 候选生成指标
            "recalled": 0,  # 正确实体在候选列表中
            "recalled_top1": 0,  # 正确实体排名第1
            "recalled_top3": 0,  # 正确实体排名前3
            "recalled_top5": 0,  # 正确实体排名前5
            "alias_matched": 0,  # 通过别名匹配成功
            "vector_retrieved": 0,  # 通过向量检索成功
            "alias_exact_matched": 0,  # 精确别名匹配
            "alias_fuzzy_matched": 0,  # 模糊别名匹配
            # 消歧指标（新增）
            "linked_correctly": 0,  # 消歧链接正确
            "linked_wrong": 0,  # 消歧链接错误
            "linked_nil_wrong": 0,  # 应该NIL但链接了实体
            "linked_nil_correct": 0,  # 应该NIL且正确判定NIL
        }

        print("\n" + "=" * 80)
        print("阶段一：基础效果指标测试")
        print("=" * 80)
        print(f"配置: {config_path}")
        print(f"知识库实体数: {len(self.kb.get_all_entities())}")
        print(f"消歧器: Reranker={'启用' if self.linker.disambiguator.enable_reranker else '禁用'}")
        print(f"NIL阈值: {self.linker.disambiguator.nil_threshold}")
        print("=" * 80)

    def load_data(self, texts_path: str, ground_truth_path: str) -> List[TestCase]:
        """加载测试数据和标准答案"""
        with open(texts_path, "r", encoding="utf-8") as f:
            texts = [line.strip() for line in f.readlines() if line.strip()]

        with open(ground_truth_path, "r", encoding="utf-8") as f:
            gt_data = json.load(f)

        test_cases = []
        for entry in gt_data.get("entries", []):
            text_idx = entry.get("text_idx", -1)
            scenario = entry.get("scenario", "")

            text_content = texts[text_idx] if text_idx < len(texts) else ""

            for exp in entry.get("expected_entities", []):
                mention = exp.get("mention", "")
                entity_id = exp.get("entity_id")

                standard_name = None
                if entity_id:
                    entity = self.kb.get_entity_by_id(entity_id)
                    if entity:
                        standard_name = entity.standard_name
                    else:
                        standard_name = self.id_to_name.get(entity_id)

                mention_type = "UNKNOWN"
                if entity_id:
                    entity = self.kb.get_entity_by_id(entity_id)
                    if entity and entity.entity_type:
                        mention_type = entity.entity_type

                char_start = text_content.find(mention) if text_content else 0
                char_end = char_start + len(mention) if char_start != -1 else 0
                if char_start == -1:
                    char_start = 0
                    char_end = 0

                test_cases.append(TestCase(
                    text_idx=text_idx,
                    text=text_content,
                    mention=mention,
                    mention_type=mention_type,
                    expected_entity_id=entity_id,
                    expected_standard_name=standard_name,
                    scenario=scenario,
                    has_nil=entity_id is None,
                    char_start=char_start,
                    char_end=char_end
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

        # 构建 StandardMention
        mention_obj = StandardMention(
            mention=test_case.mention,
            mention_type=test_case.mention_type,
            char_start=test_case.char_start,
            char_end=test_case.char_end
        )

        result = TestResult(
            text_idx=test_case.text_idx,
            mention=test_case.mention,
            expected_entity_id=test_case.expected_entity_id,
            expected_standard_name=test_case.expected_standard_name,
            scenario=test_case.scenario,
            candidates=[],
            candidate_count=0,
            has_correct_entity=False,
            correct_entity_rank=None,
            correct_entity_score=None,
            disambiguation_result=None,
            disambiguation_entity_id=None,
            disambiguation_entity_name=None,
            disambiguation_score=None,
            disambiguation_method=None,
            alias_matched=False,
            alias_match_score=None,
            vector_retrieved=False,
            vector_retrieved_score=None,
            recalled=False,
            linked_correctly=False,
            passed=False,
            errors=[]
        )

        # ============================================================
        # 第一步：候选生成
        # ============================================================
        try:
            candidates = self.linker.candidate_gen.generate(
                test_case.mention,
                top_k=50,
                context=test_case.text
            )
            result.candidates = candidates
            result.candidate_count = len(candidates)
            self.total_candidates_generated += len(candidates)

            # 检查正确实体是否在候选列表中
            expected_id = test_case.expected_entity_id

            for i, cand in enumerate(candidates, 1):
                if cand.entity.entity_id == expected_id:
                    result.has_correct_entity = True
                    result.correct_entity_rank = i
                    result.correct_entity_score = cand.score
                    result.recalled = True

                    if cand.method == "alias_exact":
                        result.alias_matched = True
                        result.alias_match_score = cand.score
                    elif cand.method == "alias_fuzzy":
                        result.alias_matched = True
                        result.alias_match_score = cand.score
                    elif cand.method == "vector":
                        result.vector_retrieved = True
                        result.vector_retrieved_score = cand.score

                    break

        except Exception as e:
            result.errors.append(f"候选生成异常: {str(e)}")
            result.passed = False
            elapsed = (time.time() - start_time) * 1000
            result.elapsed_ms = elapsed
            return result

        # ============================================================
        # 第二步：消歧（如果候选存在）
        # ============================================================
        if candidates:
            try:
                disambig_result = self.linker.disambiguator.disambiguate(
                    test_case.mention, candidates, test_case.text, test_case.mention_type
                )
                result.disambiguation_result = disambig_result

                entity = disambig_result.get("entity")
                if entity:
                    result.disambiguation_entity_id = entity.entity_id
                    result.disambiguation_entity_name = entity.standard_name
                else:
                    result.disambiguation_entity_id = None
                    result.disambiguation_entity_name = "NIL"

                result.disambiguation_score = disambig_result.get("score", 0.0)
                result.disambiguation_method = disambig_result.get("method", "unknown")

                # ============================================================
                # 验证消歧结果
                # ============================================================
                expected_id = test_case.expected_entity_id
                actual_id = result.disambiguation_entity_id

                if expected_id is None:
                    # 期望 NIL
                    if actual_id is None:
                        result.linked_correctly = True
                        self.metrics["linked_nil_correct"] += 1
                    else:
                        result.linked_correctly = False
                        result.errors.append(f"期望 NIL，实际链接到 {actual_id} ({result.disambiguation_entity_name})")
                        self.metrics["linked_nil_wrong"] += 1
                else:
                    # 期望非 NIL
                    if actual_id is None:
                        result.linked_correctly = False
                        result.errors.append(f"期望 {expected_id} ({test_case.expected_standard_name})，实际 NIL")
                        self.metrics["linked_wrong"] += 1
                    elif actual_id == expected_id:
                        result.linked_correctly = True
                        self.metrics["linked_correctly"] += 1
                    else:
                        result.linked_correctly = False
                        result.errors.append(
                            f"期望 {expected_id} ({test_case.expected_standard_name})，实际 {actual_id} ({result.disambiguation_entity_name})")
                        self.metrics["linked_wrong"] += 1

            except Exception as e:
                result.errors.append(f"消歧异常: {str(e)}")
                result.linked_correctly = False
                self.metrics["linked_wrong"] += 1
        else:
            # 无候选：如果期望 NIL 则正确，否则错误
            if test_case.has_nil:
                result.linked_correctly = True
                self.metrics["linked_nil_correct"] += 1
            else:
                result.linked_correctly = False
                result.errors.append(f"无候选实体，但期望非 NIL")
                self.metrics["linked_wrong"] += 1

        # ============================================================
        # 综合判断
        # ============================================================
        result.passed = result.linked_correctly

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

        non_nil_cases = [tc for tc in test_cases if not tc.has_nil]
        nil_cases = [tc for tc in test_cases if tc.has_nil]

        print("\n开始执行阶段一测试...")
        print("-" * 80)

        # 测试非 NIL 用例
        for i, test_case in enumerate(non_nil_cases):
            print(f"\n[{i + 1}/{len(non_nil_cases)}] 测试: {test_case.scenario}")
            print(f"  🔍 Mention: '{test_case.mention}'")
            print(f"  📌 期望: {test_case.expected_standard_name} ({test_case.expected_entity_id})")

            result = self.run_single_test(test_case)
            self.results.append(result)

            # 更新候选生成指标
            if result.recalled:
                self.metrics["recalled"] += 1
                if result.correct_entity_rank == 1:
                    self.metrics["recalled_top1"] += 1
                if result.correct_entity_rank is not None and result.correct_entity_rank <= 3:
                    self.metrics["recalled_top3"] += 1
                if result.correct_entity_rank is not None and result.correct_entity_rank <= 5:
                    self.metrics["recalled_top5"] += 1

                if result.alias_matched:
                    self.metrics["alias_matched"] += 1
                    if result.candidates and result.candidates[0].method == "alias_exact":
                        self.metrics["alias_exact_matched"] += 1
                    else:
                        self.metrics["alias_fuzzy_matched"] += 1

                if result.vector_retrieved:
                    self.metrics["vector_retrieved"] += 1

            # 更新消歧指标（在 run_single_test 中已更新）

            if result.passed:
                self.passed += 1
                print(
                    f"  ✅ PASS → 消歧结果: {result.disambiguation_entity_name or 'NIL'} (分数: {result.disambiguation_score:.3f})")
            else:
                self.failed += 1
                print(f"  ❌ FAIL → 消歧结果: {result.disambiguation_entity_name or 'NIL'}")
                for err in result.errors:
                    print(f"     ⚠️ {err}")

                # 记录错误案例
                error_type = "wrong_link"
                if result.candidate_count == 0:
                    error_type = "no_candidate"
                elif not result.has_correct_entity:
                    error_type = "not_in_top_k"
                elif result.expected_entity_id is not None and result.disambiguation_entity_id is None:
                    error_type = "nil_mismatch"
                elif result.expected_entity_id is None and result.disambiguation_entity_id is not None:
                    error_type = "nil_mismatch"

                self.error_cases.append(ErrorCase(
                    text_idx=test_case.text_idx,
                    text=test_case.text[:80],
                    mention=test_case.mention,
                    scenario=test_case.scenario,
                    error_type=error_type,
                    expected_entity_id=test_case.expected_entity_id,
                    expected_standard_name=test_case.expected_standard_name,
                    actual_entity_id=result.disambiguation_entity_id,
                    actual_standard_name=result.disambiguation_entity_name,
                    detail=f"候选数: {result.candidate_count}, 消歧方法: {result.disambiguation_method}"
                ))

        # 测试 NIL 用例
        for i, test_case in enumerate(nil_cases):
            print(f"\n[{len(non_nil_cases) + i + 1}/{len(test_cases)}] 测试: {test_case.scenario} (NIL)")
            print(f"  🔍 Mention: '{test_case.mention}'")
            print(f"  📌 期望: NIL")

            result = self.run_single_test(test_case)
            self.results.append(result)

            if result.passed:
                self.passed += 1
                print(f"  ✅ PASS → 消歧结果: NIL")
            else:
                self.failed += 1
                print(f"  ❌ FAIL → 消歧结果: {result.disambiguation_entity_name or 'NIL'}")
                for err in result.errors:
                    print(f"     ⚠️ {err}")

                self.error_cases.append(ErrorCase(
                    text_idx=test_case.text_idx,
                    text=test_case.text[:80],
                    mention=test_case.mention,
                    scenario=test_case.scenario,
                    error_type="nil_mismatch",
                    expected_entity_id=None,
                    expected_standard_name="NIL",
                    actual_entity_id=result.disambiguation_entity_id,
                    actual_standard_name=result.disambiguation_entity_name,
                    detail=f"期望 NIL，实际链接到实体"
                ))

        self.metrics["total"] = len(test_cases)
        self.metrics["non_nil"] = len(non_nil_cases)
        self.metrics["nil"] = len(nil_cases)

        self.print_summary()
        self.print_error_cases()
        self.save_results()

    def print_summary(self):
        """打印测试汇总"""
        print("\n" + "=" * 80)
        print("阶段一：基础效果指标测试报告")
        print("=" * 80)

        total = self.passed + self.failed
        non_nil_total = self.metrics["non_nil"]
        nil_total = self.metrics["nil"]

        print(f"\n📊 测试统计:")
        print(f"   总测试用例: {self.metrics['total']}")
        print(f"   非 NIL 用例: {non_nil_total}")
        print(f"   NIL 用例: {nil_total}")
        print(f"   通过: {self.passed} ✅")
        print(f"   失败: {self.failed} ❌")
        print(f"   通过率: {self.passed / max(1, self.metrics['total']) * 100:.1f}%")

        print(f"\n📈 候选生成指标 (非 NIL 用例):")
        if non_nil_total > 0:
            print(
                f"   实体召回率: {self.metrics['recalled']}/{non_nil_total} = {self.metrics['recalled'] / non_nil_total * 100:.1f}%")
            print(
                f"   Top-1 召回率: {self.metrics['recalled_top1']}/{non_nil_total} = {self.metrics['recalled_top1'] / non_nil_total * 100:.1f}%")
            print(
                f"   Top-3 召回率: {self.metrics['recalled_top3']}/{non_nil_total} = {self.metrics['recalled_top3'] / non_nil_total * 100:.1f}%")
            print(
                f"   Top-5 召回率: {self.metrics['recalled_top5']}/{non_nil_total} = {self.metrics['recalled_top5'] / non_nil_total * 100:.1f}%")

        print(f"\n📈 消歧指标 (全部用例):")
        total_correct = self.metrics["linked_correctly"] + self.metrics["linked_nil_correct"]
        total_link_attempts = self.metrics["linked_correctly"] + self.metrics["linked_wrong"] + self.metrics[
            "linked_nil_correct"] + self.metrics["linked_nil_wrong"]
        if total_link_attempts > 0:
            print(
                f"   链接准确率: {total_correct}/{total_link_attempts} = {total_correct / total_link_attempts * 100:.1f}%")
            print(f"   非 NIL 链接正确: {self.metrics['linked_correctly']}")
            print(f"   非 NIL 链接错误: {self.metrics['linked_wrong']}")
            print(f"   NIL 正确判定: {self.metrics['linked_nil_correct']}")
            print(f"   NIL 误判: {self.metrics['linked_nil_wrong']}")

        print(f"\n🔍 召回方式统计 (成功召回的用例):")
        recalled_count = self.metrics['recalled']
        if recalled_count > 0:
            print(
                f"   别名精确匹配: {self.metrics['alias_exact_matched']}/{recalled_count} = {self.metrics['alias_exact_matched'] / recalled_count * 100:.1f}%")
            print(
                f"   别名模糊匹配: {self.metrics['alias_fuzzy_matched']}/{recalled_count} = {self.metrics['alias_fuzzy_matched'] / recalled_count * 100:.1f}%")
            print(
                f"   向量检索: {self.metrics['vector_retrieved']}/{recalled_count} = {self.metrics['vector_retrieved'] / recalled_count * 100:.1f}%")

            alias_total = self.metrics['alias_exact_matched'] + self.metrics['alias_fuzzy_matched']
            print(f"\n   别名召回率: {alias_total}/{recalled_count} = {alias_total / recalled_count * 100:.1f}%")

        print(f"\n📊 候选生成统计:")
        avg_candidates = self.total_candidates_generated / max(1, len(self.results))
        print(f"   平均候选数: {avg_candidates:.1f}")

    def print_error_cases(self):
        """打印错误案例"""
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
                print(f"  期望: {case.expected_standard_name or 'NIL'} ({case.expected_entity_id or 'NIL'})")
                print(f"  实际: {case.actual_standard_name or 'NIL'} ({case.actual_entity_id or 'NIL'})")
                print(f"  详情: {case.detail}")
                print()

    def save_results(self):
        """保存测试结果"""
        output_dir = Path("tests/output")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        result_data = []
        for r in self.results:
            result_data.append({
                "text_idx": r.text_idx,
                "mention": r.mention,
                "expected_entity_id": r.expected_entity_id,
                "expected_standard_name": r.expected_standard_name,
                "scenario": r.scenario,
                "candidate_count": r.candidate_count,
                "has_correct_entity": r.has_correct_entity,
                "correct_entity_rank": r.correct_entity_rank,
                "correct_entity_score": r.correct_entity_score,
                "disambiguation_entity_id": r.disambiguation_entity_id,
                "disambiguation_entity_name": r.disambiguation_entity_name,
                "disambiguation_score": r.disambiguation_score,
                "disambiguation_method": r.disambiguation_method,
                "recalled": r.recalled,
                "linked_correctly": r.linked_correctly,
                "passed": r.passed,
                "errors": r.errors
            })

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
                "detail": case.detail
            })

        result_file = output_dir / f"phase1_metrics_{timestamp}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "metrics": self.metrics,
                "summary": {
                    "total": self.metrics["total"],
                    "non_nil": self.metrics["non_nil"],
                    "nil": self.metrics["nil"],
                    "passed": self.passed,
                    "failed": self.failed,
                    "pass_rate": f"{self.passed / max(1, self.metrics['total']) * 100:.1f}%",
                    "recall": f"{self.metrics['recalled'] / max(1, self.metrics['non_nil']) * 100:.1f}%",
                    "recall_top1": f"{self.metrics['recalled_top1'] / max(1, self.metrics['non_nil']) * 100:.1f}%",
                    "recall_top3": f"{self.metrics['recalled_top3'] / max(1, self.metrics['non_nil']) * 100:.1f}%",
                    "recall_top5": f"{self.metrics['recalled_top5'] / max(1, self.metrics['non_nil']) * 100:.1f}%",
                    "link_accuracy": f"{(self.metrics['linked_correctly'] + self.metrics['linked_nil_correct']) / max(1, self.metrics['linked_correctly'] + self.metrics['linked_wrong'] + self.metrics['linked_nil_correct'] + self.metrics['linked_nil_wrong']) * 100:.1f}%"
                },
                "error_cases": error_data,
                "details": result_data
            }, f, ensure_ascii=False, indent=2)

        print(f"\n📄 测试结果已保存: {result_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="阶段一基础效果指标测试")
    parser.add_argument("--texts", type=str, help="测试文本文件路径")
    parser.add_argument("--gt", type=str, help="标准答案文件路径")
    args = parser.parse_args()

    tester = Phase1MetricsTester()
    tester.run_all_tests(args.texts, args.gt)


if __name__ == "__main__":
    main()