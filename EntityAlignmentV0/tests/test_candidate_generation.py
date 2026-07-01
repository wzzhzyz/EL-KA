# tests/test_candidate_generation.py
import sys
import os
import json
from typing import List, Dict, Any
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.candidate import CandidateGenerator
from src.knowledge.kb_manager import KnowledgeBase
from src.knowledge.vector_index import VectorIndex
from src.models.candidate import Candidate
from src.models.entity import StandardEntity
from src.utils.config import load_config
from src.utils.logger import logger


@dataclass
class TestCase:
    """候选生成测试用例"""
    id: str
    mention: str
    description: str
    expected_min_candidates: int = 1  # 期望的最少候选数
    expected_contains: List[str] = field(default_factory=list)  # 期望包含的实体名称


class CandidateGenerationTester:
    """候选生成模块测试器"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)

        # 初始化知识库
        self.kb = KnowledgeBase(self.config["knowledge_base"])

        # 初始化向量索引
        self.vector_index = VectorIndex(self.config["bge_model_path"])
        self.vector_index.build(self.kb.get_all_entities())

        # 初始化候选生成器
        self.candidate_gen = CandidateGenerator(self.kb, self.vector_index)

        self.results = []

    def run_test_case(self, test_case: TestCase) -> Dict[str, Any]:
        """运行单个测试用例"""
        logger.info(f"\n{'=' * 60}")
        logger.info(f"测试用例: {test_case.id} - {test_case.description}")
        logger.info(f"输入 mention: '{test_case.mention}'")
        logger.info(f"{'=' * 60}")

        # 生成候选
        candidates = self.candidate_gen.generate(test_case.mention, top_k=10)

        # 构建结果
        result = {
            "test_id": test_case.id,
            "mention": test_case.mention,
            "description": test_case.description,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "candidate_details": [],
            "expected_min": test_case.expected_min_candidates,
            "expected_contains": test_case.expected_contains,
            "passed": True,
            "errors": [],
            "warnings": []
        }

        # 检查最少候选数
        if len(candidates) < test_case.expected_min_candidates:
            result["passed"] = False
            result["errors"].append(
                f"候选数不足: 期望至少 {test_case.expected_min_candidates} 个, 实际 {len(candidates)} 个"
            )

        # 检查是否包含期望的实体
        candidate_names = [c.entity.standard_name for c in candidates]
        for expected_name in test_case.expected_contains:
            if expected_name not in candidate_names:
                result["passed"] = False
                result["errors"].append(f"缺少期望实体: '{expected_name}'")

        # 收集候选详情
        for i, cand in enumerate(candidates, 1):
            detail = {
                "rank": i,
                "entity_id": cand.entity.entity_id,
                "standard_name": cand.entity.standard_name,
                "score": cand.score,
                "method": cand.method,
                "metadata": cand.metadata
            }
            result["candidate_details"].append(detail)

        # 打印候选信息
        self._print_candidates(result)

        self.results.append(result)
        return result

    def _print_candidates(self, result: Dict[str, Any]):
        """打印候选信息"""
        print(f"\n📋 候选列表 (共 {result['candidate_count']} 个):")
        print("-" * 70)

        if result['candidate_count'] == 0:
            print("  ⚠️ 无候选")
            return

        for detail in result["candidate_details"]:
            # 根据方法显示不同颜色/标记
            method_mark = {
                "alias_exact": "🎯",
                "alias_fuzzy": "🔍",
                "vector": "📊"
            }.get(detail["method"], "  ")

            print(f"  {method_mark} #{detail['rank']}: {detail['standard_name']}")
            print(f"      ID: {detail['entity_id']}")
            print(f"      分数: {detail['score']:.4f}")
            print(f"      方法: {detail['method']}")
            if detail.get("metadata"):
                print(f"      元数据: {detail['metadata']}")
            print()

    def run_batch(self, test_cases: List[TestCase]) -> Dict[str, Any]:
        """批量运行测试"""
        logger.info(f"\n{'=' * 70}")
        logger.info(f"🧪 开始候选生成批量测试，共 {len(test_cases)} 个用例")
        logger.info(f"{'=' * 70}")

        passed_count = 0
        failed_count = 0

        for test_case in test_cases:
            result = self.run_test_case(test_case)
            if result["passed"]:
                passed_count += 1
            else:
                failed_count += 1

        summary = {
            "total": len(test_cases),
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate": passed_count / len(test_cases) if test_cases else 0,
            "results": self.results
        }

        logger.info(f"\n📊 测试完成: 通过 {passed_count}, 失败 {failed_count}, 通过率 {summary['pass_rate']:.1%}")
        return summary

    def print_summary(self, summary: Dict[str, Any]):
        """打印测试总结"""
        print("\n" + "=" * 70)
        print("📊 候选生成测试总结")
        print("=" * 70)
        print(f"  总用例数: {summary['total']}")
        print(f"  ✅ 通过: {summary['passed']}")
        print(f"  ❌ 失败: {summary['failed']}")
        print(f"  📈 通过率: {summary['pass_rate']:.1%}")

        if summary["failed"] > 0:
            print("\n" + "-" * 70)
            print("❌ 失败用例详情:")
            print("-" * 70)
            for result in summary["results"]:
                if not result["passed"]:
                    print(f"\n  {result['test_id']}: {result['description']}")
                    print(f"  mention: '{result['mention']}'")
                    print(f"  候选数: {result['candidate_count']}")
                    for error in result["errors"]:
                        print(f"  ⚠️ {error}")


# ============================================================
# 测试用例定义
# ============================================================

def get_test_cases() -> List[TestCase]:
    """获取候选生成测试用例"""
    return [
        # === 标准名称测试 ===
        TestCase(
            id="CG_001",
            mention="国家电网有限公司",
            description="标准全称 - 应精确匹配",
            expected_min_candidates=1,
            expected_contains=["国家电网有限公司"]
        ),
        TestCase(
            id="CG_002",
            mention="中国石油天然气集团有限公司",
            description="标准全称 - 石油",
            expected_min_candidates=1,
            expected_contains=["中国石油天然气集团有限公司"]
        ),

        # === 别名测试（含歧义） ===
        TestCase(
            id="CG_003",
            mention="国网",
            description="简称 - 可能有多个实体共享同一别名",
            expected_min_candidates=2,
            expected_contains=["国家电网有限公司"]
        ),
        TestCase(
            id="CG_004",
            mention="中石油",
            description="三字简称 - 石油",
            expected_min_candidates=1,
            expected_contains=["中国石油天然气集团有限公司"]
        ),
        TestCase(
            id="CG_005",
            mention="中石化",
            description="三字简称 - 石化",
            expected_min_candidates=1,
            expected_contains=["中国石油化工集团有限公司"]
        ),
        TestCase(
            id="CG_006",
            mention="南网",
            description="两字简称 - 南方电网",
            expected_min_candidates=1,
            expected_contains=["中国南方电网有限责任公司"]
        ),
        TestCase(
            id="CG_007",
            mention="华能",
            description="两字简称 - 华能国际",
            expected_min_candidates=1,
            expected_contains=["华能国际电力股份有限公司"]
        ),

        # === 歧义别名测试 ===
        TestCase(
            id="CG_008",
            mention="宁德时代",
            description="新能源企业 - 全称/简称",
            expected_min_candidates=1,
            expected_contains=["宁德时代新能源科技股份有限公司"]
        ),
        TestCase(
            id="CG_009",
            mention="中核",
            description="两字简称 - 中核集团",
            expected_min_candidates=1,
            expected_contains=["中国核工业集团有限公司"]
        ),

        # === 向量检索测试（无别名匹配） ===
        TestCase(
            id="CG_010",
            mention="电力巨头",
            description="无别名匹配 - 应通过向量检索召回",
            expected_min_candidates=1,
            expected_contains=[]
        ),
        TestCase(
            id="CG_011",
            mention="新能源公司",
            description="无别名匹配 - 应通过向量检索召回",
            expected_min_candidates=1,
            expected_contains=[]
        ),

        # === 边界测试 ===
        TestCase(
            id="CG_012",
            mention="不存在的实体名称XYZ",
            description="不存在的实体 - 应无候选或极少候选",
            expected_min_candidates=0,
            expected_contains=[]
        ),
        TestCase(
            id="CG_013",
            mention="",
            description="空字符串 - 应无候选",
            expected_min_candidates=0,
            expected_contains=[]
        ),

        # === 多别名歧义测试 ===
        TestCase(
            id="CG_014",
            mention="国网公司",
            description="含'国网'的别名 - 应匹配多个实体",
            expected_min_candidates=1,
            expected_contains=[]
        ),
    ]


# ============================================================
# 详细输出测试（用于调试）
# ============================================================

def test_single_mention(mention: str, top_k: int = 10):
    """测试单个 mention 并打印详细信息"""
    print("\n" + "=" * 70)
    print(f"🔬 单条测试: '{mention}'")
    print("=" * 70)

    config = load_config()
    kb = KnowledgeBase(config["knowledge_base"])
    vector_index = VectorIndex(config["bge_model_path"])
    vector_index.build(kb.get_all_entities())
    candidate_gen = CandidateGenerator(kb, vector_index)

    candidates = candidate_gen.generate(mention, top_k=top_k)

    print(f"\n📋 候选列表 (共 {len(candidates)} 个):")
    print("-" * 50)

    if not candidates:
        print("  ⚠️ 无候选")
        return

    for i, cand in enumerate(candidates, 1):
        method_mark = {
            "alias_exact": "🎯",
            "alias_fuzzy": "🔍",
            "vector": "📊"
        }.get(cand.method, "  ")

        print(f"\n  {method_mark} #{i}: {cand.entity.standard_name}")
        print(f"      ID: {cand.entity.entity_id}")
        print(f"      类型: {cand.entity.entity_type}")
        print(f"      分数: {cand.score:.4f}")
        print(f"      方法: {cand.method}")
        if cand.metadata:
            print(f"      元数据: {cand.metadata}")

    # 打印所有候选的分数对比
    print("\n" + "-" * 50)
    print("📊 分数对比:")
    for i, cand in enumerate(candidates, 1):
        print(f"  #{i}: {cand.entity.standard_name[:20]:20s} → {cand.score:.4f} ({cand.method})")


# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 70)
    print("🧪 候选生成模块测试")
    print("=" * 70)

    # 创建测试器
    tester = CandidateGenerationTester()

    # 获取测试用例
    test_cases = get_test_cases()
    print(f"\n📋 加载测试用例: {len(test_cases)} 个")

    # 运行测试
    summary = tester.run_batch(test_cases)

    # 打印总结
    tester.print_summary(summary)

    return 0 if summary["failed"] == 0 else 1


# ============================================================
# 交互式测试
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="候选生成模块测试")
    parser.add_argument("--mention", "-m", type=str, help="测试单个 mention")
    parser.add_argument("--top_k", "-k", type=int, default=10, help="返回候选数量")
    parser.add_argument("--batch", "-b", action="store_true", help="运行批量测试")

    args = parser.parse_args()

    if args.mention:
        test_single_mention(args.mention, args.top_k)
    else:
        sys.exit(main())
    # test_single_mention("国网")