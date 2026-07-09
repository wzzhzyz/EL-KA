# tests/test_e2e_entity_linking.py
import os
import json
import yaml
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field

from src.knowledge.kb_manager import KnowledgeBase
from src.knowledge.vector_index import VectorIndex
from src.core.candidate import CandidateGenerator
from src.core.disambiguate import Disambiguator
from src.models.candidate import Candidate


# ============================================================
# 错误类型定义
# ============================================================
ERROR_TYPE_RECALL = "召回错误"
ERROR_TYPE_DISAMBIGUATION = "消歧错误"
ERROR_TYPE_NIL_FALSE_NEG = "NIL假阴性（应链接却判NIL）"
ERROR_TYPE_NIL_FALSE_POS = "NIL假阳性（应NIL却链接实体）"
ERROR_TYPE_OTHER = "其他错误"

ERROR_SUB_ALIAS_MISS = "别名匹配未召回"
ERROR_SUB_VECTOR_MISS = "向量检索未召回"
ERROR_SUB_RANK_WRONG = "排序错误（正确候选非Top1）"
ERROR_SUB_SCORE_LOW = "置信度不足（低于NIL阈值）"
ERROR_SUB_NIL_MISJUDGE = "NIL边界判断失误"


@dataclass
class TestCaseResult:
    """单条测试用例结果结构"""
    text_idx: int
    text: str
    mention: str
    expected_entity_id: str
    expected_entity_name: str
    actual_entity_id: str
    actual_entity_name: str
    is_pass: bool
    error_type: str = ""
    error_subtype: str = ""
    error_detail: str = ""
    top3_candidates: List[Tuple[str, str, float]] = field(default_factory=list)


class E2EEntityLinkingTester:
    """
    实体链接端到端测试器
    输入：标注好的 mention + 对应上下文文本
    输出：全链路测试结果、失败案例分类与详情
    """

    def __init__(self, config_path: str = "./config.yaml"):
        # 优先读取项目全局配置文件，保持参数一致
        self.global_config = self._load_global_config(config_path)
        self.config = self._build_test_config()

        # 1. 初始化知识库（传入完整字典配置，适配 AdapterFactory）
        self.kb = KnowledgeBase(self.config["kb_config"])

        # 2. 初始化向量索引并构建 FAISS 索引
        self.vector_index = VectorIndex(
            model_path=self.config["vector_model_path"],
            kb=self.kb
        )
        self.vector_index.build(self.kb.get_all_entities())

        # 3. 初始化候选生成器与消歧器
        self.candidate_gen = CandidateGenerator(self.kb, self.vector_index)
        self.disambiguator = Disambiguator(self.config["disambiguate_config"])

        # 测试数据与结果存储
        self.texts: List[str] = []
        self.ground_truth: List[Dict[str, Any]] = []
        self.results: List[TestCaseResult] = []
        self.failed_cases: List[TestCaseResult] = []
        self.total_cases = 0
        self.passed_cases = 0

    @staticmethod
    def _load_global_config(config_path: str) -> Dict[str, Any]:
        """读取项目全局 config.yaml"""
        if not os.path.exists(config_path):
            print(f"⚠️  未找到全局配置文件 {config_path}，将使用默认配置")
            return {}
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _build_test_config(self) -> Dict[str, Any]:
        """基于全局配置构建测试模块配置，保持参数一致"""
        gc = self.global_config

        # 知识库配置：直接复用全局 knowledge_base 字段
        kb_config = gc.get("knowledge_base", {
            "type": "json",
            "path": "./data/energy_entities.json"
        })

        # 向量模型路径
        vector_model_path = gc.get("bge_model_path", "./models_cache/bge-large-zh-v1.5")

        # 消歧器配置：对齐全局 config 结构
        disambig_config = {
            "reranker_enabled": gc.get("reranker_enabled", True),
            "reranker_top_k": gc.get("reranker_top_k", 6),
            "reranker_weight": gc.get("reranker_weight", 0.7),
            "bge_reranker_weight": gc.get("bge_reranker_weight", 0.3),
            "reranker_model_path": gc.get("reranker_model_path", "./models_cache/bge-reranker-large"),
            "disambiguator": gc.get("disambiguator", {
                "nil_threshold": 0.45,
                "bge_llm_trigger_threshold": 0.65
            }),
            "llm_fallback": gc.get("llm_fallback", {"enabled": False})
        }

        return {
            "kb_config": kb_config,
            "vector_model_path": vector_model_path,
            "test_data_dir": "./data",
            "disambiguate_config": disambig_config
        }

    def load_test_data(self) -> None:
        """加载测试文本与标注真值"""
        data_dir = self.config["test_data_dir"]

        # 加载测试文本（按行与 text_idx 一一对应）
        text_path = os.path.join(data_dir, "batch_texts.txt")
        with open(text_path, "r", encoding="utf-8") as f:
            self.texts = [line.rstrip("\n") for line in f.readlines()]

        # 加载标注真值
        gt_path = os.path.join(data_dir, "batch_ground_truth.json")
        with open(gt_path, "r", encoding="utf-8") as f:
            gt_data = json.load(f)
            self.ground_truth = gt_data["entries"]

        print(f"✅ 测试数据加载完成：{len(self.texts)} 条文本，{len(self.ground_truth)} 条标注条目")

    def _get_entity_name(self, entity_id: str) -> str:
        """通过实体ID获取标准名称，NIL/不存在时返回对应标识"""
        if not entity_id:
            return "NIL"
        entity = self.kb.get_entity_by_id(entity_id)
        return entity.standard_name if entity else f"未知实体[{entity_id}]"

    def _classify_error(
        self,
        mention: str,
        expected_id: str,
        actual_id: str,
        candidates: List[Candidate],
        disambig_result: Dict[str, Any]
    ) -> Tuple[str, str, str]:
        """
        自动错误分类
        返回：(一级错误类型, 二级子类型, 详细说明)
        """
        candidate_ids = [c.entity.entity_id for c in candidates]
        expected_in_candidates = expected_id in candidate_ids

        # 1. NIL假阴性：预期有实体，系统判NIL
        if expected_id and not actual_id:
            if expected_in_candidates:
                score = disambig_result.get("score", 0)
                return (
                    ERROR_TYPE_NIL_FALSE_NEG,
                    ERROR_SUB_SCORE_LOW,
                    f"正确实体已召回，但消歧后分数 {score:.3f} 低于NIL阈值"
                )
            else:
                alias_entities = self.kb.get_entities_by_alias(mention)
                if expected_id not in [e.entity_id for e in alias_entities]:
                    return (ERROR_TYPE_RECALL, ERROR_SUB_ALIAS_MISS, "别名库中无对应指称，向量检索也未命中")
                return (ERROR_TYPE_RECALL, ERROR_SUB_VECTOR_MISS, "别名未精确匹配，向量检索未召回正确实体")

        # 2. NIL假阳性：预期NIL，系统错误链接
        if not expected_id and actual_id:
            score = disambig_result.get("score", 0)
            return (
                ERROR_TYPE_NIL_FALSE_POS,
                ERROR_SUB_NIL_MISJUDGE,
                f"错误链接到实体，分数 {score:.3f}，未触发NIL判定"
            )

        # 3. 实体链接错误：预期和实际都是非NIL但ID不同
        if expected_id and actual_id and expected_id != actual_id:
            if expected_in_candidates:
                rank = candidate_ids.index(expected_id) + 1
                return (
                    ERROR_TYPE_DISAMBIGUATION,
                    ERROR_SUB_RANK_WRONG,
                    f"正确实体在候选中排名第 {rank}，消歧后选中错误Top1"
                )
            else:
                return (ERROR_TYPE_RECALL, ERROR_SUB_ALIAS_MISS, "候选生成阶段完全未召回正确实体")

        return (ERROR_TYPE_OTHER, "", "未分类错误")

    def run_single_case(self, text_idx: int, text: str, expected: Dict[str, Any]) -> TestCaseResult:
        """执行单条mention的端到端测试"""
        mention = expected["mention"]
        expected_id = expected["entity_id"]
        expected_name = self._get_entity_name(expected_id)

        # 1. 候选生成
        candidates = self.candidate_gen.generate(mention, context=text)

        # 2. 消歧与NIL判定
        disambig_result = self.disambiguator.disambiguate(
            mention=mention,
            candidates=candidates,
            context=text
        )

        # 3. 提取实际结果
        actual_entity = disambig_result["entity"]
        actual_id = actual_entity.entity_id if actual_entity else None
        actual_name = actual_entity.standard_name if actual_entity else "NIL"

        # 4. 结果比对
        is_pass = (expected_id == actual_id)

        # 5. 保留Top3候选用于排查
        top3 = []
        for c in candidates[:3]:
            top3.append((c.entity.entity_id, c.entity.standard_name, round(c.score, 4)))

        # 6. 错误分类
        error_type, error_sub, error_detail = "", "", ""
        if not is_pass:
            error_type, error_sub, error_detail = self._classify_error(
                mention, expected_id, actual_id, candidates, disambig_result
            )

        return TestCaseResult(
            text_idx=text_idx,
            text=text,
            mention=mention,
            expected_entity_id=expected_id or "NIL",
            expected_entity_name=expected_name,
            actual_entity_id=actual_id or "NIL",
            actual_entity_name=actual_name,
            is_pass=is_pass,
            error_type=error_type,
            error_subtype=error_sub,
            error_detail=error_detail,
            top3_candidates=top3
        )

    def run_all_tests(self) -> None:
        """批量执行所有测试用例"""
        if not self.ground_truth:
            self.load_test_data()

        print("\n🚀 开始端到端实体链接全流程测试...\n")

        for entry in self.ground_truth:
            text_idx = entry["text_idx"]
            text = self.texts[text_idx] if text_idx < len(self.texts) else ""
            expected_entities = entry["expected_entities"]

            # 跳过纯无实体场景（如需测试整句NER+链接可扩展）
            if not expected_entities:
                continue

            for expected in expected_entities:
                self.total_cases += 1
                result = self.run_single_case(text_idx, text, expected)
                self.results.append(result)
                if result.is_pass:
                    self.passed_cases += 1
                else:
                    self.failed_cases.append(result)

    def print_failed_cases(self) -> None:
        """格式化输出所有失败用例详情"""
        if not self.failed_cases:
            print("\n🎉 全部测试用例通过！")
            return

        print("\n" + "=" * 110)
        print(f"❌ 失败用例详情汇总（共 {len(self.failed_cases)} 条）")
        print("=" * 110)

        for idx, case in enumerate(self.failed_cases, 1):
            print(f"\n【失败用例 {idx} | 文本索引: {case.text_idx}】")
            print(f"  原文上下文：{case.text}")
            print(f"  实体指称：「{case.mention}」")
            print(f"  期望结果：{case.expected_entity_name}  (ID: {case.expected_entity_id})")
            print(f"  实际结果：{case.actual_entity_name}  (ID: {case.actual_entity_id})")
            print(f"  错误分类：{case.error_type} → {case.error_subtype}")
            print(f"  错误说明：{case.error_detail}")

            if case.top3_candidates:
                print("  候选Top3：")
                for rank, (eid, name, score) in enumerate(case.top3_candidates, 1):
                    print(f"    {rank}. {name} (ID: {eid}, 分数: {score})")
            print("-" * 110)

    def print_summary(self) -> None:
        """输出整体测试统计"""
        accuracy = self.passed_cases / self.total_cases if self.total_cases > 0 else 0

        print("\n" + "=" * 65)
        print("📊 端到端测试统计总览")
        print("=" * 65)
        print(f"  总测试用例数：{self.total_cases}")
        print(f"  通过用例数：{self.passed_cases}")
        print(f"  失败用例数：{len(self.failed_cases)}")
        print(f"  整体准确率：{accuracy:.2%}")

        # 错误类型分布
        if self.failed_cases:
            print("\n  错误类型分布：")
            type_stats = {}
            for case in self.failed_cases:
                type_stats[case.error_type] = type_stats.get(case.error_type, 0) + 1
            for err_type, count in type_stats.items():
                print(f"    - {err_type}：{count} 例")
        print("=" * 65)

    def run(self) -> None:
        """执行完整测试流程"""
        self.load_test_data()
        self.run_all_tests()
        self.print_failed_cases()
        self.print_summary()


if __name__ == "__main__":
    # 默认读取项目根目录下的 config.yaml
    tester = E2EEntityLinkingTester(config_path="./config.yaml")
    tester.run()