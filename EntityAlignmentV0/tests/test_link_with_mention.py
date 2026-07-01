#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体链接智能体评测脚本
基于 eval_dataset.json 验证 Candidate Generation、Disambiguation、NIL Detection、Coreference Resolution 能力

Usage:
    python test_entity_linker.py                    # 运行全部评测
    python test_entity_linker.py --category easy    # 只跑 easy 难度
    python test_entity_linker.py --verbose          # 详细输出
    python test_entity_linker.py --trace-id xxx     # 指定 trace_id 查询留痕
"""

import json
import os
import sys
import argparse
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.linker import EntityLinker
from src.utils.logger import logger, generate_trace_id
from src.models.entity import StandardEntity
from src.models.mention import StandardMention
from src.knowledge.kb_manager import KnowledgeBase
from src.utils.config import load_config


# ============================================================
# 评测数据结构
# ============================================================

@dataclass
class EvalSample:
    """评测样本"""
    id: str
    text: str
    mention: str
    mention_start: int
    mention_end: int
    gold_entity_id: Optional[str]
    gold_entity_name: Optional[str]
    candidate_entities: List[str]
    expected_result: Dict[str, Any]
    difficulty: str
    scenario: str
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvalSample":
        return cls(
            id=data.get("id", ""),
            text=data.get("text", ""),
            mention=data.get("mention", ""),
            mention_start=data.get("mention_start", 0),
            mention_end=data.get("mention_end", 0),
            gold_entity_id=data.get("gold_entity"),
            gold_entity_name=data.get("gold_entity_name"),
            candidate_entities=data.get("candidate_entities", []),
            expected_result=data.get("expected_result", {}),
            difficulty=data.get("difficulty", "medium"),
            scenario=data.get("scenario", "unknown"),
            notes=data.get("notes", "")
        )


@dataclass
class EvalResult:
    """单个样本评测结果"""
    sample_id: str
    scenario: str
    difficulty: str
    mention: str
    gold_entity_id: Optional[str]
    gold_entity_name: Optional[str]
    predicted_entity_id: Optional[str]
    predicted_entity_name: Optional[str]
    confidence: float
    is_nil: bool
    is_coreference: bool
    resolved_from: Optional[str] = None
    evidence: str = ""
    correct: bool = False
    error_type: Optional[str] = None  # "wrong_entity", "false_nil", "false_positive", "coref_error"
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SummaryStats:
    """汇总统计"""
    total: int = 0
    correct: int = 0
    wrong: int = 0
    accuracy: float = 0.0

    # 按场景统计
    by_scenario: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {"total": 0, "correct": 0}))

    # 按难度统计
    by_difficulty: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {"total": 0, "correct": 0}))

    # 错误类型统计
    error_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # 详细统计
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    nil_precision: float = 0.0
    nil_recall: float = 0.0
    nil_f1: float = 0.0
    coref_accuracy: float = 0.0


# ============================================================
# 实体链接评测器
# ============================================================

class EntityLinkerEvaluator:
    """实体链接评测器"""

    def __init__(self, linker: EntityLinker, dataset_path: str, verbose: bool = False):
        self.linker = linker
        self.verbose = verbose
        self.dataset = self._load_dataset(dataset_path)
        self.results: List[EvalResult] = []
        self.summary = SummaryStats()

    def _load_dataset(self, path: str) -> List[EvalSample]:
        """加载评测数据集"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        samples = []
        for item in data.get("samples", []):
            samples.append(EvalSample.from_dict(item))

        logger.info(f"📊 加载评测集: {len(samples)} 个样本")
        return samples

    def _get_entity_id_from_result(self, result: Dict) -> Optional[str]:
        """从链接结果中提取 entity_id"""
        entity = result.get("entity")
        if entity:
            if hasattr(entity, "entity_id"):
                return entity.entity_id
            elif isinstance(entity, dict):
                return entity.get("entity_id")
        return result.get("entity_id")

    def _get_entity_name_from_result(self, result: Dict) -> Optional[str]:
        """从链接结果中提取 entity_name"""
        entity = result.get("entity")
        if entity:
            if hasattr(entity, "standard_name"):
                return entity.standard_name
            elif isinstance(entity, dict):
                return entity.get("standard_name")
        return result.get("standard_entity")

    def _get_entity_id_from_obj(self, obj: Any) -> Optional[str]:
        """从 StandardEntity 或 dict 中提取 entity_id"""
        if hasattr(obj, "entity_id"):
            return obj.entity_id
        elif isinstance(obj, dict):
            return obj.get("entity_id")
        return None

    def _resolve_coref_mentions(self, link_result: Dict) -> List[Dict]:
        """从链接结果中提取共指消解的 mention"""
        results = link_result.get("results", [])
        # 只取 NER 识别的 mention（非共指解析产生的）
        ner_mentions = [r for r in results if not r.get("is_coreference", False)]
        coref_mentions = [r for r in results if r.get("is_coreference", False)]
        return ner_mentions, coref_mentions

    def run(self, category: Optional[str] = None) -> SummaryStats:
        """
        运行评测

        Args:
            category: 过滤场景类别，如 "easy", "medium", "hard"
        """
        # 过滤样本
        samples = self.dataset
        if category:
            samples = [s for s in samples if s.difficulty == category]
            logger.info(f"🔍 过滤后: {len(samples)} 个样本 (category={category})")

        logger.info(f"🚀 开始评测 {len(samples)} 个样本...")

        for sample in samples:
            result = self._evaluate_sample(sample)
            self.results.append(result)

            # 更新统计
            self._update_stats(result)

            if self.verbose:
                self._print_sample_result(result)

        # 计算汇总统计
        self._compute_summary_stats()

        return self.summary

    def _evaluate_sample(self, sample: EvalSample) -> EvalResult:
        """评测单个样本"""
        # 构建输入 mention
        mention_obj = StandardMention(
            mention=sample.mention,
            mention_type="ORG",  # 从 context 推断，这里统一用 ORG
            char_start=sample.mention_start,
            char_end=sample.mention_end
        )

        # 调用实体链接（跳过 NER，直接使用提供的 mention）
        result = self.linker.link_with_mentions(
            sample.text,
            [mention_obj.to_dict()],
            options={
                "enable_coreference": True,
                "nil_threshold": 0.65,
                "linkable_types": ["ORG", "GPE", "PERSON", "LOC", "PRON", "NOUN"]
            }
        )

        # 提取预测结果
        results = result.get("results", [])
        if not results:
            return EvalResult(
                sample_id=sample.id,
                scenario=sample.scenario,
                difficulty=sample.difficulty,
                mention=sample.mention,
                gold_entity_id=sample.gold_entity_id,
                gold_entity_name=sample.gold_entity_name,
                predicted_entity_id=None,
                predicted_entity_name=None,
                confidence=0.0,
                is_nil=True,
                is_coreference=False,
                evidence="无返回结果",
                correct=False,
                error_type="no_result"
            )

        # 找到对应的预测结果
        predicted = None
        coref_predicted = None

        for r in results:
            if r.get("mention") == sample.mention:
                predicted = r
                break

        # 如果没有精确匹配，取第一个
        if not predicted and results:
            predicted = results[0]

        # 检查是否是共指消解结果
        is_coreference = predicted.get("is_coreference", False) if predicted else False
        resolved_from = predicted.get("resolved_from") if predicted else None

        # 提取预测实体
        predicted_entity_id = self._get_entity_id_from_result(predicted) if predicted else None
        predicted_entity_name = self._get_entity_name_from_result(predicted) if predicted else None
        is_nil = predicted.get("is_nil", True) if predicted else True
        confidence = predicted.get("confidence", 0.0) if predicted else 0.0
        evidence = predicted.get("evidence", "") if predicted else ""

        # 判断是否正确
        correct = False
        error_type = None

        expected_linked = sample.expected_result.get("linked", True)
        expected_entity_id = sample.expected_result.get("correct_entity")

        # 处理共指消解的期望结果
        is_coref_sample = "coref" in sample.scenario or "共指" in sample.scenario
        if is_coref_sample and "coref" in sample.expected_result:
            expected_coref = sample.expected_result.get("coref_antecedent")
            # 共指消解结果判断
            if is_coreference and resolved_from == expected_coref:
                correct = True
            elif not is_coreference and not is_nil:
                # 如果是非共指但预期是共指，判断是否直接链接到正确实体
                if predicted_entity_id == expected_entity_id:
                    correct = True
                else:
                    correct = False
                    error_type = "coref_error"
            else:
                correct = False
                error_type = "coref_error"
        else:
            # 普通实体链接判断
            if expected_linked:
                # 预期有链接
                if not is_nil and predicted_entity_id == expected_entity_id:
                    correct = True
                elif not is_nil and predicted_entity_id != expected_entity_id:
                    correct = False
                    error_type = "wrong_entity"
                else:
                    correct = False
                    error_type = "false_nil"
            else:
                # 预期 NIL
                if is_nil:
                    correct = True
                else:
                    correct = False
                    error_type = "false_positive"

        return EvalResult(
            sample_id=sample.id,
            scenario=sample.scenario,
            difficulty=sample.difficulty,
            mention=sample.mention,
            gold_entity_id=sample.gold_entity_id,
            gold_entity_name=sample.gold_entity_name,
            predicted_entity_id=predicted_entity_id,
            predicted_entity_name=predicted_entity_name,
            confidence=confidence,
            is_nil=is_nil,
            is_coreference=is_coreference,
            resolved_from=resolved_from,
            evidence=evidence,
            correct=correct,
            error_type=error_type,
            details={
                "predicted": predicted,
                "all_results": results
            }
        )

    def _update_stats(self, result: EvalResult):
        """更新统计"""
        self.summary.total += 1

        # 正确/错误计数
        if result.correct:
            self.summary.correct += 1
        else:
            self.summary.wrong += 1
            if result.error_type:
                self.summary.error_types[result.error_type] += 1

        # 按场景统计
        scenario_stats = self.summary.by_scenario[result.scenario]
        scenario_stats["total"] += 1
        if result.correct:
            scenario_stats["correct"] += 1

        # 按难度统计
        difficulty_stats = self.summary.by_difficulty[result.difficulty]
        difficulty_stats["total"] += 1
        if result.correct:
            difficulty_stats["correct"] += 1

    def _compute_summary_stats(self):
        """计算汇总统计"""
        total = self.summary.total
        if total == 0:
            return

        self.summary.accuracy = self.summary.correct / total

        # 计算精确率、召回率、F1
        # 真阳性: 预期链接且正确链接
        # 假阳性: 预期NIL但链接了
        # 假阴性: 预期链接但预测NIL
        tp = sum(1 for r in self.results if r.correct and r.gold_entity_id is not None and not r.is_nil)
        fp = sum(1 for r in self.results if r.gold_entity_id is None and not r.is_nil)
        fn = sum(1 for r in self.results if r.gold_entity_id is not None and r.is_nil)

        self.summary.precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        self.summary.recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        self.summary.f1 = 2 * self.summary.precision * self.summary.recall / (self.summary.precision + self.summary.recall) if (self.summary.precision + self.summary.recall) > 0 else 0.0

        # NIL 检测指标
        nil_tp = sum(1 for r in self.results if r.correct and r.is_nil and r.gold_entity_id is None)
        nil_fp = sum(1 for r in self.results if r.gold_entity_id is not None and r.is_nil)
        nil_fn = sum(1 for r in self.results if r.gold_entity_id is None and not r.is_nil)

        self.summary.nil_precision = nil_tp / (nil_tp + nil_fp) if (nil_tp + nil_fp) > 0 else 0.0
        self.summary.nil_recall = nil_tp / (nil_tp + nil_fn) if (nil_tp + nil_fn) > 0 else 0.0
        self.summary.nil_f1 = 2 * self.summary.nil_precision * self.summary.nil_recall / (self.summary.nil_precision + self.summary.nil_recall) if (self.summary.nil_precision + self.summary.nil_recall) > 0 else 0.0

        # 共指消解准确率
        coref_samples = [r for r in self.results if r.is_coreference or "coref" in r.scenario]
        if coref_samples:
            coref_correct = sum(1 for r in coref_samples if r.correct)
            self.summary.coref_accuracy = coref_correct / len(coref_samples)

    def _print_sample_result(self, result: EvalResult):
        """打印单个样本结果"""
        status = "✅" if result.correct else "❌"
        print(f"\n{status} [{result.sample_id}] {result.scenario} ({result.difficulty})")
        print(f"   Mention: '{result.mention}'")
        print(f"   Gold: {result.gold_entity_name} ({result.gold_entity_id})")
        print(f"   Pred: {result.predicted_entity_name} ({result.predicted_entity_id})")
        print(f"   NIL: {result.is_nil}, Coref: {result.is_coreference}")
        if result.error_type:
            print(f"   Error: {result.error_type}")
        if result.resolved_from:
            print(f"   Resolved from: {result.resolved_from}")
        print(f"   Evidence: {result.evidence[:100]}...")

    def print_summary(self):
        """打印汇总结果"""
        summary = self.summary
        total = summary.total

        print("\n" + "=" * 70)
        print("📊 实体链接评测报告")
        print("=" * 70)

        print(f"\n📌 总体统计:")
        print(f"   Total: {total}")
        print(f"   Correct: {summary.correct}")
        print(f"   Wrong: {summary.wrong}")
        print(f"   Accuracy: {summary.accuracy:.4f} ({summary.accuracy * 100:.2f}%)")

        print(f"\n📌 实体链接指标:")
        print(f"   Precision: {summary.precision:.4f}")
        print(f"   Recall: {summary.recall:.4f}")
        print(f"   F1: {summary.f1:.4f}")

        print(f"\n📌 NIL 检测指标:")
        print(f"   Precision: {summary.nil_precision:.4f}")
        print(f"   Recall: {summary.nil_recall:.4f}")
        print(f"   F1: {summary.nil_f1:.4f}")

        if summary.coref_accuracy > 0:
            print(f"\n📌 共指消解准确率:")
            print(f"   Coref Accuracy: {summary.coref_accuracy:.4f}")

        print(f"\n📌 错误类型分布:")
        for error_type, count in sorted(summary.error_types.items(), key=lambda x: -x[1]):
            print(f"   {error_type}: {count} ({count/total*100:.1f}%)")

        print(f"\n📌 按场景统计:")
        for scenario, stats in sorted(summary.by_scenario.items()):
            acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            print(f"   {scenario}: {stats['correct']}/{stats['total']} ({acc*100:.1f}%)")

        print(f"\n📌 按难度统计:")
        for difficulty in ["easy", "medium", "hard"]:
            if difficulty in summary.by_difficulty:
                stats = summary.by_difficulty[difficulty]
                acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
                print(f"   {difficulty}: {stats['correct']}/{stats['total']} ({acc*100:.1f}%)")

        print("\n" + "=" * 70)

    def export_report(self, output_path: str):
        """导出评测报告为 JSON"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": self.summary.total,
                "correct": self.summary.correct,
                "wrong": self.summary.wrong,
                "accuracy": self.summary.accuracy,
                "precision": self.summary.precision,
                "recall": self.summary.recall,
                "f1": self.summary.f1,
                "nil_precision": self.summary.nil_precision,
                "nil_recall": self.summary.nil_recall,
                "nil_f1": self.summary.nil_f1,
                "coref_accuracy": self.summary.coref_accuracy,
                "error_types": dict(self.summary.error_types),
                "by_scenario": {
                    k: {"total": v["total"], "correct": v["correct"], "accuracy": v["correct"]/v["total"] if v["total"] > 0 else 0}
                    for k, v in self.summary.by_scenario.items()
                },
                "by_difficulty": {
                    k: {"total": v["total"], "correct": v["correct"], "accuracy": v["correct"]/v["total"] if v["total"] > 0 else 0}
                    for k, v in self.summary.by_difficulty.items()
                }
            },
            "results": [
                {
                    "sample_id": r.sample_id,
                    "scenario": r.scenario,
                    "difficulty": r.difficulty,
                    "mention": r.mention,
                    "gold_entity_id": r.gold_entity_id,
                    "gold_entity_name": r.gold_entity_name,
                    "predicted_entity_id": r.predicted_entity_id,
                    "predicted_entity_name": r.predicted_entity_name,
                    "confidence": r.confidence,
                    "is_nil": r.is_nil,
                    "is_coreference": r.is_coreference,
                    "resolved_from": r.resolved_from,
                    "correct": r.correct,
                    "error_type": r.error_type,
                    "evidence": r.evidence
                }
                for r in self.results
            ]
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n📄 评测报告已导出: {output_path}")

    def get_failed_samples(self) -> List[EvalResult]:
        """获取失败的样本"""
        return [r for r in self.results if not r.correct]

    def get_samples_by_scenario(self, scenario: str) -> List[EvalResult]:
        """按场景获取样本"""
        return [r for r in self.results if r.scenario == scenario]


# ============================================================
# 命令行入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="实体链接智能体评测工具")
    parser.add_argument("--dataset", type=str,
                        default="E:/Code/Python/PycharmProjects/EntityAlignmentV0/data/eval_dataset.json",
                        help="评测数据集路径")
    parser.add_argument("--config", type=str, default="config.yaml",
                        help="配置文件路径")
    parser.add_argument("--category", type=str, choices=["easy", "medium", "hard"],
                        help="按难度过滤")
    parser.add_argument("--scenario", type=str,
                        help="按场景过滤 (如 '简称匹配', '同名异义消歧')")
    parser.add_argument("--verbose", action="store_true",
                        help="详细输出")
    parser.add_argument("--export", type=str,
                        help="导出评测报告到指定路径")
    parser.add_argument("--trace-id", type=str,
                        help="查询指定 trace_id 的链接记录")
    parser.add_argument("--list-scenarios", action="store_true",
                        help="列出所有评测场景")
    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 初始化实体链接器
    linker = EntityLinker(config)

    # 如果只是查询 trace_id
    if args.trace_id:
        records = linker.get_trace(args.trace_id)
        print(f"\n📋 链接记录 (trace_id: {args.trace_id}):")
        for r in records:
            print(f"   {r['mention']} → {r['standard_name']} ({r['entity_id']})")
            print(f"      置信度: {r['confidence']}, NIL: {r['is_nil']}, 共指: {r['is_coreference']}")
            print(f"      证据: {r['evidence']}")
        return

    # 初始化评测器
    evaluator = EntityLinkerEvaluator(linker, args.dataset, verbose=args.verbose)

    # 列出场景
    if args.list_scenarios:
        scenarios = set(s.scenario for s in evaluator.dataset)
        print("\n📋 评测场景列表:")
        for s in sorted(scenarios):
            count = sum(1 for x in evaluator.dataset if x.scenario == s)
            print(f"   {s}: {count} 个样本")
        return

    # 运行评测
    summary = evaluator.run(category=args.category)

    # 打印结果
    evaluator.print_summary()

    # 如果 verbose，打印失败样本详情
    if args.verbose:
        failed = evaluator.get_failed_samples()
        if failed:
            print(f"\n❌ 失败样本详情 ({len(failed)} 个):")
            for r in failed[:10]:  # 只显示前10个
                print(f"\n   [{r.sample_id}] {r.scenario}")
                print(f"      Mention: '{r.mention}'")
                print(f"      Gold: {r.gold_entity_name}")
                print(f"      Pred: {r.predicted_entity_name}")
                print(f"      Error: {r.error_type}")
                print(f"      Evidence: {r.evidence}")

            if len(failed) > 10:
                print(f"\n   ... 还有 {len(failed) - 10} 个失败样本")

    # 导出报告
    if args.export:
        evaluator.export_report(args.export)


if __name__ == "__main__":
    main()