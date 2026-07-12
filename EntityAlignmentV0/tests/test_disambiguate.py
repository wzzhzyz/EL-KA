# tests/test_disambiguate.py
"""
消歧模块测试脚本 - 基于 disambiguation_test.json 数据集

测试内容：
1. 高置信样本测试（精确匹配）
2. 中置信样本测试（多候选消歧）
3. 低置信样本测试（容错兜底）
4. NIL样本测试（实体不在KB、集合指代、共指代词）
5. Reranker精排效果验证
6. 置信度分数范围验证
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from sympy import false

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.disambiguate import Disambiguator
from src.knowledge.kb_manager import KnowledgeBase
from src.knowledge.vector_index import VectorIndex
from src.core.candidate import CandidateGenerator
from src.models.entity import StandardEntity
from src.models.candidate import Candidate
from src.utils.config import load_config


@dataclass
class TestCase:
    """测试用例数据结构"""
    id: str
    text: str
    mention: str
    gold_entity: Optional[str]
    confidence_level: str
    kb_status: str
    expected_bge_score_range: List[float]
    expected_nil: bool
    reason: str
    scenario: str
    nil_reason: Optional[str] = None


@dataclass
class FailedCase:
    """失败用例数据结构 - 新增 query 和 doc 字段"""
    test_id: str
    text: str
    mention: str
    scenario: str
    expected_entity: str
    actual_entity: str
    expected_nil: bool
    actual_nil: bool
    expected_score_range: List[float]
    actual_score: float
    method: str
    evidence: str
    error_type: str
    error_message: str = ""
    # 🔥 新增字段
    query: str = ""  # 发送给 Reranker 的 query（带标记的上下文）
    doc: str = ""  # 发送给 Reranker 的 doc（候选实体描述）
    candidates_info: str = ""  # 候选实体简要信息（用于调试）


class DisambiguatorDatasetTester:
    """基于数据集的消歧器测试类"""

    def __init__(self, config_path: str = None):
        """初始化测试器"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"

        self.config = load_config(str(config_path))
        self.disambiguator = Disambiguator(self.config)
        self.test_results = []
        self.failed_cases: List[FailedCase] = []
        self.passed = 0
        self.failed = 0
        self.test_cases: List[TestCase] = []

        # 初始化知识库和相关组件（在加载数据集时初始化）
        self._kb = None
        self._vector_index = None
        self._candidate_gen = None
        self._entity_id_to_name = {}
        self._entity_id_to_entity = {}

        print("\n" + "=" * 80)
        print("消歧模块数据集测试")
        print("=" * 80)
        print(f"配置: {config_path}")
        print(f"Reranker: {'启用' if self.disambiguator.enable_reranker else '禁用'}")
        if self.disambiguator.enable_reranker:
            print(
                f"  模型: {self.disambiguator._reranker.model.config._name_or_path if hasattr(self.disambiguator._reranker, 'model') else '已加载'}")
        print(f"NIL阈值: {self.disambiguator.nil_threshold}")
        print(f"LLM触发阈值: {self.disambiguator.llm_trigger_threshold}")
        print(f"LLM兜底: {'启用' if self.disambiguator.enable_llm else '禁用'}")
        print("=" * 80)

    def _init_knowledge_base(self):
        """初始化知识库和候选生成器"""
        if self._kb is None:
            print("\n📚 加载知识库...")
            self._kb = KnowledgeBase(self.config["knowledge_base"])
            print(f"   ✅ 加载 {len(self._kb.get_all_entities())} 个实体")

            # 构建实体映射
            for entity in self._kb.get_all_entities():
                self._entity_id_to_name[entity.entity_id] = entity.standard_name
                self._entity_id_to_entity[entity.entity_id] = entity

            # 初始化向量索引
            print("📦 构建向量索引...")
            self._vector_index = VectorIndex(self.config["bge_model_path"], kb=self._kb)
            self._vector_index.build(self._kb.get_all_entities())

            # 初始化候选生成器
            self._candidate_gen = CandidateGenerator(self._kb, self._vector_index)
            print("✅ 知识库组件初始化完成")

    def load_dataset(self, dataset_path: str = None) -> List[TestCase]:
        """加载测试数据集"""
        if dataset_path is None:
            dataset_path = Path(__file__).parent.parent / "data" / "disambiguation_test.json"

        if not os.path.exists(dataset_path):
            print(f"❌ 数据集不存在: {dataset_path}")
            return []

        with open(dataset_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 初始化知识库
        self._init_knowledge_base()

        test_cases = []
        for sample in data.get("samples", []):
            test_cases.append(TestCase(
                id=sample.get("id", "UNKNOWN"),
                text=sample.get("text", ""),
                mention=sample.get("mention", ""),
                gold_entity=sample.get("gold_entity"),
                confidence_level=sample.get("confidence_level", "unknown"),
                kb_status=sample.get("kb_status", "unknown"),
                expected_bge_score_range=sample.get("expected_bge_score_range", [0.0, 1.0]),
                expected_nil=sample.get("expected_nil", False),
                reason=sample.get("reason", ""),
                scenario=sample.get("scenario", ""),
                nil_reason=sample.get("nil_reason", None)
            ))

        self.test_cases = test_cases
        print(f"\n📋 加载测试用例: {len(test_cases)} 个")

        # 打印统计信息
        by_confidence = {}
        by_kb_status = {}
        for tc in test_cases:
            by_confidence[tc.confidence_level] = by_confidence.get(tc.confidence_level, 0) + 1
            by_kb_status[tc.kb_status] = by_kb_status.get(tc.kb_status, 0) + 1

        print(f"  按置信度: {by_confidence}")
        print(f"  按KB状态: {by_kb_status}")

        return test_cases

    def get_entity_by_id(self, entity_id: str) -> Optional[StandardEntity]:
        """根据实体ID获取实体"""
        if self._kb is None:
            return None
        return self._kb.get_entity_by_id(entity_id)

    def get_candidates_for_mention(self, mention: str, context: str) -> List[Candidate]:
        """为mention生成候选实体（使用知识库）"""
        if self._candidate_gen is None:
            self._init_knowledge_base()

        return self._candidate_gen.generate(mention, top_k=50, context=context)

    def _get_entity_type_from_context(self, mention: str, text: str) -> str:
        """从上下文中提取实体类型线索"""
        text_lower = text.lower()
        mention_pos = text.find(mention)
        if mention_pos == -1:
            return ""

        start = max(0, mention_pos - 50)
        end = min(len(text), mention_pos + len(mention) + 50)
        context_window = text[start:end]

        if any(kw in context_window for kw in ["公司", "集团", "有限", "企业", "总部", "子公司"]):
            return "ORG"
        if any(kw in context_window for kw in ["电站", "基地", "电厂", "水电站", "光伏"]):
            return "POWER_FACILITY"
        if any(kw in context_window for kw in ["工程", "技术", "标准", "专利", "研发"]):
            return "TECHNICAL_TERM"
        if any(kw in context_window for kw in ["市", "省", "区", "县"]):
            return "GPE"

        return ""

    def run_single_test(self, test_case: TestCase) -> Tuple[bool, Optional[FailedCase]]:
        """运行单个测试用例"""
        try:
            # 生成候选（使用增强的上下文）
            candidates = self.get_candidates_for_mention(test_case.mention, test_case.text)

            # 如果没有候选，检查是否期望NIL
            if not candidates:
                if test_case.expected_nil:
                    return True, None
                else:
                    failed = FailedCase(
                        test_id=test_case.id,
                        text=test_case.text,
                        mention=test_case.mention,
                        scenario=test_case.scenario,
                        expected_entity=test_case.gold_entity or "NIL",
                        actual_entity="NIL (无候选)",
                        expected_nil=test_case.expected_nil,
                        actual_nil=True,
                        expected_score_range=test_case.expected_bge_score_range,
                        actual_score=0.0,
                        method="none",
                        evidence="无候选实体",
                        error_type="wrong_entity",
                        error_message="没有候选实体但期望非NIL",
                        query="",
                        doc="",
                        candidates_info="无候选"
                    )
                    return False, failed

            # 获取mention类型（从上下文推断）
            mention_type = self._get_entity_type_from_context(test_case.mention, test_case.text)

            # 🔥 在消歧前，构建 query 和 doc（用于失败用例输出）
            query = self.disambiguator._build_query(test_case.mention, test_case.text)

            # 构建候选信息（用于调试）
            candidates_info_list = []
            for c in candidates[:5]:
                candidates_info_list.append(f"{c.entity.standard_name}({c.score:.3f})")
            candidates_info = "; ".join(candidates_info_list)

            # 执行消歧（传入mention_type增强语义）
            result = self.disambiguator.disambiguate(
                test_case.mention, candidates, test_case.text, mention_type
            )

            actual_entity = result.get("entity")
            actual_score = result.get("score", 0.0)
            actual_method = result.get("method", "unknown")
            actual_evidence = result.get("evidence", "")
            actual_nil = actual_entity is None
            actual_name = actual_entity.standard_name if actual_entity else "NIL"

            # 获取期望实体名称
            expected_name = test_case.gold_entity
            if test_case.gold_entity:
                expected_entity = self.get_entity_by_id(test_case.gold_entity)
                if expected_entity:
                    expected_name = expected_entity.standard_name

            # 获取被选中的 doc（候选实体描述）
            selected_doc = ""
            if actual_entity:
                selected_doc = self.disambiguator._build_passage(actual_entity)
            elif candidates:
                # 如果结果为 NIL，取第一个候选的 doc 作为参考
                selected_doc = self.disambiguator._build_passage(candidates[0].entity)

            # 检查NIL状态
            if actual_nil != test_case.expected_nil:
                failed = FailedCase(
                    test_id=test_case.id,
                    text=test_case.text,
                    mention=test_case.mention,
                    scenario=test_case.scenario,
                    expected_entity=expected_name or test_case.gold_entity or "NIL",
                    actual_entity=actual_name,
                    expected_nil=test_case.expected_nil,
                    actual_nil=actual_nil,
                    expected_score_range=test_case.expected_bge_score_range,
                    actual_score=actual_score,
                    method=actual_method,
                    evidence=actual_evidence,
                    error_type="nil_mismatch",
                    error_message=f"NIL状态不匹配: 期望NIL={test_case.expected_nil}, 实际NIL={actual_nil}",
                    query=query,
                    doc=selected_doc,
                    candidates_info=candidates_info
                )
                return False, failed

            # 如果期望非NIL，检查实体是否正确
            if not test_case.expected_nil and test_case.gold_entity:
                if actual_entity is None or actual_entity.entity_id != test_case.gold_entity:
                    failed = FailedCase(
                        test_id=test_case.id,
                        text=test_case.text,
                        mention=test_case.mention,
                        scenario=test_case.scenario,
                        expected_entity=expected_name or test_case.gold_entity,
                        actual_entity=actual_name,
                        expected_nil=test_case.expected_nil,
                        actual_nil=actual_nil,
                        expected_score_range=test_case.expected_bge_score_range,
                        actual_score=actual_score,
                        method=actual_method,
                        evidence=actual_evidence,
                        error_type="wrong_entity",
                        error_message=f"实体不匹配: 期望 {expected_name}, 实际 {actual_name}",
                        query=query,
                        doc=selected_doc,
                        candidates_info=candidates_info
                    )
                    return False, failed

            # 检查分数范围（提供容差）
            if test_case.expected_bge_score_range and len(test_case.expected_bge_score_range) == 2:
                low, high = test_case.expected_bge_score_range

                if test_case.expected_nil:
                    if actual_score > 0.55:
                        if test_case.confidence_level in ["high", "medium"]:
                            failed = FailedCase(
                                test_id=test_case.id,
                                text=test_case.text,
                                mention=test_case.mention,
                                scenario=test_case.scenario,
                                expected_entity=expected_name or test_case.gold_entity or "NIL",
                                actual_entity=actual_name,
                                expected_nil=test_case.expected_nil,
                                actual_nil=actual_nil,
                                expected_score_range=test_case.expected_bge_score_range,
                                actual_score=actual_score,
                                method=actual_method,
                                evidence=actual_evidence,
                                error_type="score_out_of_range",
                                error_message=f"NIL样本分数异常: 期望 <= {high:.2f}, 实际 {actual_score:.2f}",
                                query=query,
                                doc=selected_doc,
                                candidates_info=candidates_info
                            )
                            return False, failed
                else:
                    if not (low - 0.1 <= actual_score <= high + 0.1):
                        if test_case.confidence_level in ["low"] and actual_score >= low - 0.2:
                            pass
                        else:
                            failed = FailedCase(
                                test_id=test_case.id,
                                text=test_case.text,
                                mention=test_case.mention,
                                scenario=test_case.scenario,
                                expected_entity=expected_name or test_case.gold_entity or "NIL",
                                actual_entity=actual_name,
                                expected_nil=test_case.expected_nil,
                                actual_nil=actual_nil,
                                expected_score_range=test_case.expected_bge_score_range,
                                actual_score=actual_score,
                                method=actual_method,
                                evidence=actual_evidence,
                                error_type="score_out_of_range",
                                error_message=f"分数超出范围: 期望 [{low:.2f}, {high:.2f}], 实际 {actual_score:.2f}",
                                query=query,
                                doc=selected_doc,
                                candidates_info=candidates_info
                            )
                            return False, failed

            return True, None

        except Exception as e:
            import traceback
            traceback.print_exc()

            # 尝试构建 query 和 doc（即使出错）
            try:
                query = self.disambiguator._build_query(test_case.mention, test_case.text)
                doc = ""
            except:
                query = ""
                doc = ""

            failed = FailedCase(
                test_id=test_case.id,
                text=test_case.text,
                mention=test_case.mention,
                scenario=test_case.scenario,
                expected_entity=test_case.gold_entity or "NIL",
                actual_entity="EXCEPTION",
                expected_nil=test_case.expected_nil,
                actual_nil=True,
                expected_score_range=test_case.expected_bge_score_range,
                actual_score=0.0,
                method="exception",
                evidence=str(e),
                error_type="exception",
                error_message=f"执行异常: {str(e)}",
                query=query,
                doc=doc,
                candidates_info=""
            )
            return False, failed

    def run_all_tests(self):
        """运行所有测试"""
        test_cases = self.load_dataset()

        if not test_cases:
            print("❌ 没有测试用例，退出")
            return

        print("\n开始执行消歧测试...")
        print("-" * 80)

        total = len(test_cases)
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[{i}/{total}] 测试: {test_case.id} - {test_case.scenario}")
            print(f"  Mention: '{test_case.mention}'")
            print(f"  置信度: {test_case.confidence_level}")
            print(f"  期望NIL: {test_case.expected_nil}")
            if test_case.gold_entity:
                entity = self.get_entity_by_id(test_case.gold_entity)
                if entity:
                    print(f"  期望实体: {entity.standard_name}")

            passed, failed = self.run_single_test(test_case)

            if passed:
                self.passed += 1
                print(f"  ✅ PASS")
            else:
                self.failed += 1
                self.failed_cases.append(failed)
                print(f"  ❌ FAIL: {failed.error_type}")
                print(f"     期望: {failed.expected_entity}")
                print(f"     实际: {failed.actual_entity}")
                if failed.actual_score > 0:
                    print(f"     分数: {failed.actual_score:.3f} (期望范围: {failed.expected_score_range})")

        self.print_summary()
        self.print_failed_cases()
        self.save_results()

    def print_summary(self):
        """打印测试汇总"""
        print("\n" + "=" * 80)
        print("测试汇总")
        print("=" * 80)

        total = self.passed + self.failed
        print(f"总测试数: {total}")
        print(f"通过: {self.passed} ✅")
        print(f"失败: {self.failed} ❌")
        print(f"通过率: {self.passed / total * 100:.1f}%" if total > 0 else "通过率: 0%")

        # 按置信度统计
        print("\n📊 按置信度统计:")
        for conf in ["high", "medium", "low", "nil_high"]:
            total_conf = sum(1 for tc in self.test_cases if tc.confidence_level == conf)
            if total_conf > 0:
                failed_ids = {fc.test_id for fc in self.failed_cases}
                passed_conf = sum(1 for tc in self.test_cases
                                  if tc.confidence_level == conf and tc.id not in failed_ids)
                rate = passed_conf / total_conf * 100
                print(f"  {conf}: {passed_conf}/{total_conf} ({rate:.1f}%)")

        # 按KB状态统计
        print("\n📊 按KB状态统计:")
        for status in ["in_kb", "nil"]:
            total_status = sum(1 for tc in self.test_cases if tc.kb_status == status)
            if total_status > 0:
                failed_ids = {fc.test_id for fc in self.failed_cases}
                passed_status = sum(1 for tc in self.test_cases
                                    if tc.kb_status == status and tc.id not in failed_ids)
                rate = passed_status / total_status * 100
                print(f"  {status}: {passed_status}/{total_status} ({rate:.1f}%)")

        # 按错误类型统计
        if self.failed_cases:
            print("\n📊 错误类型分布:")
            error_types = {}
            for case in self.failed_cases:
                error_types[case.error_type] = error_types.get(case.error_type, 0) + 1
            for err_type, count in error_types.items():
                print(f"  {err_type}: {count}")

        # 统计信息 - 安全获取
        try:
            stats = self.disambiguator.get_stats()
            # 确保所有值都是可序列化的基本类型
            safe_stats = {}
            for key, value in stats.items():
                if isinstance(value, (int, float, str, bool)) or value is None:
                    safe_stats[key] = value
                else:
                    safe_stats[key] = str(value)

            print(f"\n消歧器统计:")
            print(f"  Reranker调用: {safe_stats.get('reranker_calls', 0)}")
            print(f"  Reranker使用: {safe_stats.get('reranker_used', 0)}")
            print(f"  LLM调用: {safe_stats.get('llm_calls', 0)}")
            print(f"  LLM缓存命中: {safe_stats.get('llm_cache_hits', 0)}")
            print(f"  NIL(分数): {safe_stats.get('nil_by_score', 0)}")
            print(f"  NIL(LLM): {safe_stats.get('nil_by_llm', 0)}")
        except Exception as e:
            print(f"\n⚠️ 无法获取消歧器统计信息: {e}")

    def print_failed_cases(self):
        """打印所有失败用例详情 - 🔥 新增 query、doc、candidates_info 输出"""
        if not self.failed_cases:
            print("\n✅ 所有测试用例通过！")
            return

        print("\n" + "=" * 80)
        print(f"❌ 失败用例详情 (共 {len(self.failed_cases)} 个)")
        print("=" * 80)

        for i, case in enumerate(self.failed_cases, 1):
            print(f"\n{'=' * 60}")
            print(f"【失败用例 #{i}】{case.test_id}")
            print(f"{'=' * 60}")
            print(f"  场景: {case.scenario}")
            print(f"  🔍 Mention: '{case.mention}'")
            print(f"  📝 完整文本: {case.text[:200]}{'...' if len(case.text) > 200 else ''}")
            print(f"\n  📌 期望实体: {case.expected_entity}")
            print(f"  📌 实际实体: {case.actual_entity}")
            print(f"  🎯 期望NIL: {case.expected_nil}")
            print(f"  🎯 实际NIL: {case.actual_nil}")
            print(f"  📊 期望分数范围: [{case.expected_score_range[0]:.2f}, {case.expected_score_range[1]:.2f}]")
            print(f"  📊 实际分数: {case.actual_score:.4f}")
            print(f"  🔧 消歧方法: {case.method}")

            # 🔥 新增：输出 query、doc、候选信息
            print(f"\n  📤 QUERY (带标记的上下文):")
            print(f"     {case.query[:300]}{'...' if len(case.query) > 300 else ''}")

            print(f"\n  📥 DOC (候选实体描述):")
            print(f"     {case.doc[:300]}{'...' if len(case.doc) > 300 else ''}")

            if case.candidates_info:
                print(f"\n  📋 候选实体 (前5个):")
                print(f"     {case.candidates_info}")

            print(f"\n  💬 判断依据: {case.evidence[:200]}{'...' if len(case.evidence) > 200 else ''}")
            print(f"  ❌ 错误类型: {case.error_type}")
            print(f"  💡 错误信息: {case.error_message}")
            print(f"{'=' * 60}")

    def save_results(self):
        """保存测试结果 - 🔥 新增 query、doc、candidates_info 字段"""
        output_dir = Path("tests/output")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 转换失败用例为可序列化格式
        failed_cases_data = []
        for case in self.failed_cases:
            failed_cases_data.append({
                "test_id": case.test_id,
                "text": case.text[:500],
                "mention": case.mention,
                "scenario": case.scenario,
                "expected_entity": case.expected_entity,
                "actual_entity": case.actual_entity,
                "expected_nil": case.expected_nil,
                "actual_nil": case.actual_nil,
                "expected_score_range": case.expected_score_range,
                "actual_score": case.actual_score,
                "method": case.method,
                "evidence": case.evidence,
                "error_type": case.error_type,
                "error_message": case.error_message,
                "query": case.query,
                "doc": case.doc,
                "candidates_info": case.candidates_info
            })

        # 安全获取统计信息
        stats_data = {}
        try:
            raw_stats = self.disambiguator.get_stats()
            for key, value in raw_stats.items():
                if isinstance(value, (int, float, str, bool)) or value is None:
                    stats_data[key] = value
                else:
                    stats_data[key] = str(value)
        except Exception as e:
            stats_data = {"error": f"无法获取统计信息: {e}"}

        # 保存详细结果
        file_path = output_dir / f"disambiguate_dataset_test_{timestamp}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "nil_threshold": self.disambiguator.nil_threshold,
                    "llm_trigger_threshold": self.disambiguator.llm_trigger_threshold,
                    "llm_enabled": self.disambiguator.llm_config.get("enabled","false"),
                    "reranker_enabled": self.disambiguator.enable_reranker
                },
                "summary": {
                    "total": self.passed + self.failed,
                    "passed": self.passed,
                    "failed": self.failed,
                    "pass_rate": f"{self.passed / (self.passed + self.failed) * 100:.1f}%" if (
                                                                                                          self.passed + self.failed) > 0 else "0%"
                },
                "stats": stats_data,
                "failed_cases": failed_cases_data
            }, f, ensure_ascii=False, indent=2)

        print(f"\n📄 测试结果已保存: {file_path}")

        # 如果有失败用例，单独保存失败用例文件（含完整 query 和 doc）
        if self.failed_cases:
            failed_file_path = output_dir / f"failed_cases_{timestamp}.json"
            with open(failed_file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "total_failed": len(self.failed_cases),
                    "failed_cases": failed_cases_data
                }, f, ensure_ascii=False, indent=2)
            print(f"📄 失败用例已单独保存: {failed_file_path}")


def run_quick_test():
    """快速测试（禁用LLM）"""
    import yaml
    from src.utils.config import get_project_root

    config_path = Path(get_project_root()) / "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    config["llm_fallback"]["enabled"] = False

    tester = DisambiguatorDatasetTester(str(config_path))
    tester.disambiguator = Disambiguator(config)
    tester.disambiguator.enable_llm = False

    print("\n⚠️ 快速测试模式（LLM已禁用）")
    tester.run_all_tests()


def run_reranker_test():
    """测试Reranker效果对比"""
    import yaml
    from src.utils.config import get_project_root

    config_path = Path(get_project_root()) / "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    config["llm_fallback"]["enabled"] = False
    config["reranker_enabled"] = True

    print("\n🔍 Reranker测试模式")
    tester = DisambiguatorDatasetTester(str(config_path))
    tester.disambiguator = Disambiguator(config)
    tester.disambiguator.enable_llm = False
    tester.disambiguator.enable_reranker = True

    tester.run_all_tests()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='消歧模块数据集测试')
    parser.add_argument('--quick', action='store_true', help='快速测试（禁用LLM）')
    parser.add_argument('--reranker', action='store_true', help='Reranker测试')
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--dataset', type=str, help='数据集路径',
                        default='data/disambiguation_test.json')
    args = parser.parse_args()

    if args.quick:
        run_quick_test()
    elif args.reranker:
        run_reranker_test()
    else:
        tester = DisambiguatorDatasetTester(args.config)
        tester.run_all_tests()


if __name__ == "__main__":
    main()