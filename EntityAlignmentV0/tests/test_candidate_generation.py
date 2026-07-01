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
    expected_min_candidates: int = 1
    expected_contains: List[str] = field(default_factory=list)
    expected_methods: List[str] = field(default_factory=list)  # 期望包含的匹配方法


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
            "expected_methods": test_case.expected_methods,
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

        # 检查是否包含期望的方法
        candidate_methods = [c.method for c in candidates]
        for expected_method in test_case.expected_methods:
            if expected_method not in candidate_methods:
                result["warnings"].append(f"缺少期望方法: '{expected_method}'")

        # 收集候选详情
        for i, cand in enumerate(candidates, 1):
            detail = {
                "rank": i,
                "entity_id": cand.entity.entity_id,
                "standard_name": cand.entity.standard_name,
                "entity_type": cand.entity.entity_type,
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

        # 按方法分组统计
        method_counts = {}
        for detail in result["candidate_details"]:
            method = detail["method"]
            method_counts[method] = method_counts.get(method, 0) + 1

        print(f"  方法分布: {method_counts}")
        print()

        for detail in result["candidate_details"]:
            method_mark = {
                "alias_exact": "🎯",
                "alias_fuzzy": "🔍",
                "vector": "📊"
            }.get(detail["method"], "  ")

            print(f"  {method_mark} #{detail['rank']}: {detail['standard_name']}")
            print(f"      ID: {detail['entity_id']}")
            print(f"      类型: {detail['entity_type']}")
            print(f"      分数: {detail['score']:.4f}")
            print(f"      方法: {detail['method']}")
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
# 基于 energy_entities.json 的测试用例
# ============================================================

def get_test_cases() -> List[TestCase]:
    """获取候选生成测试用例（基于 energy_entities.json）"""
    return [
        # === 电网企业测试 ===
        TestCase(
            id="CG_001",
            mention="国家电网有限公司",
            description="电网企业 - 标准全称",
            expected_min_candidates=1,
            expected_contains=["国家电网有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_002",
            mention="国网",
            description="电网企业 - 两字简称（可能有多个实体共享此别名）",
            expected_min_candidates=1,
            expected_contains=["国家电网有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_003",
            mention="南方电网",
            description="电网企业 - 四字简称",
            expected_min_candidates=1,
            expected_contains=["中国南方电网有限责任公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_004",
            mention="南网",
            description="电网企业 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["中国南方电网有限责任公司"],
            expected_methods=["alias_exact"]
        ),

        # === 发电企业测试 ===
        TestCase(
            id="CG_005",
            mention="华能集团",
            description="发电企业 - 三字简称（含'集团'）",
            expected_min_candidates=1,
            expected_contains=["中国华能集团有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_006",
            mention="华能",
            description="发电企业 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["中国华能集团有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_007",
            mention="国家能源集团",
            description="发电企业 - 四字简称",
            expected_min_candidates=1,
            expected_contains=["国家能源投资集团有限责任公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_008",
            mention="国能",
            description="发电企业 - 两字简称（可能与'国网'混淆）",
            expected_min_candidates=1,
            expected_contains=["国家能源投资集团有限责任公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_009",
            mention="国家电投",
            description="发电企业 - 三字简称",
            expected_min_candidates=1,
            expected_contains=["国家电力投资集团有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_010",
            mention="华电",
            description="发电企业 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["中国华电集团有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_011",
            mention="中核集团",
            description="核电企业 - 三字简称（含'集团'）",
            expected_min_candidates=1,
            expected_contains=["中国核工业集团有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_012",
            mention="中核",
            description="核电企业 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["中国核工业集团有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_013",
            mention="中广核",
            description="核电企业 - 三字简称",
            expected_min_candidates=1,
            expected_contains=["中国广核集团有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_014",
            mention="三峡集团",
            description="水电企业 - 三字简称（含'集团'）",
            expected_min_candidates=1,
            expected_contains=["中国长江三峡集团有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_015",
            mention="三峡",
            description="水电企业 - 两字简称（可能有歧义，也指三峡水电站）",
            expected_min_candidates=1,
            expected_contains=["中国长江三峡集团有限公司"],
            expected_methods=["alias_exact"]
        ),

        # === 新能源企业测试 ===
        TestCase(
            id="CG_016",
            mention="宁德时代",
            description="新能源企业 - 四字简称",
            expected_min_candidates=1,
            expected_contains=["宁德时代新能源科技股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_017",
            mention="CATL",
            description="新能源企业 - 英文缩写",
            expected_min_candidates=1,
            expected_contains=["宁德时代新能源科技股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_018",
            mention="比亚迪",
            description="新能源企业 - 三字简称",
            expected_min_candidates=1,
            expected_contains=["比亚迪股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_019",
            mention="BYD",
            description="新能源企业 - 英文缩写",
            expected_min_candidates=1,
            expected_contains=["比亚迪股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_020",
            mention="隆基绿能",
            description="新能源企业 - 四字简称",
            expected_min_candidates=1,
            expected_contains=["隆基绿能科技股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_021",
            mention="隆基",
            description="新能源企业 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["隆基绿能科技股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_022",
            mention="天合光能",
            description="新能源企业 - 四字简称",
            expected_min_candidates=1,
            expected_contains=["天合光能股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_023",
            mention="金风科技",
            description="新能源企业 - 四字简称",
            expected_min_candidates=1,
            expected_contains=["金风科技股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_024",
            mention="金风",
            description="新能源企业 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["金风科技股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_025",
            mention="远景能源",
            description="新能源企业 - 四字简称",
            expected_min_candidates=1,
            expected_contains=["远景能源有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_026",
            mention="远景",
            description="新能源企业 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["远景能源有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_027",
            mention="阳光电源",
            description="新能源企业 - 四字简称",
            expected_min_candidates=1,
            expected_contains=["阳光电源股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_028",
            mention="亿纬锂能",
            description="新能源企业 - 四字简称",
            expected_min_candidates=1,
            expected_contains=["惠州亿纬锂能股份有限公司"],
            expected_methods=["alias_exact"]
        ),

        # === 电力设施测试 ===
        TestCase(
            id="CG_029",
            mention="三峡大坝",
            description="电力设施 - 俗称",
            expected_min_candidates=1,
            expected_contains=["三峡水电站"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_030",
            mention="白鹤滩",
            description="电力设施 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["白鹤滩水电站"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_031",
            mention="大亚湾核电站",
            description="电力设施 - 完整名称",
            expected_min_candidates=1,
            expected_contains=["大亚湾核电站"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_032",
            mention="大亚湾",
            description="电力设施 - 三字简称",
            expected_min_candidates=1,
            expected_contains=["大亚湾核电站"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_033",
            mention="张北柔性直流电网工程",
            description="电力设施 - 完整名称（10字以上）",
            expected_min_candidates=1,
            expected_contains=["张北柔性直流电网工程"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_034",
            mention="张北柔直",
            description="电力设施 - 四字简称",
            expected_min_candidates=1,
            expected_contains=["张北柔性直流电网工程"],
            expected_methods=["alias_exact"]
        ),

        # === 专业术语测试 ===
        TestCase(
            id="CG_035",
            mention="特高压直流输电",
            description="专业术语 - 完整名称",
            expected_min_candidates=1,
            expected_contains=["特高压直流输电"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_036",
            mention="UHVDC",
            description="专业术语 - 英文缩写",
            expected_min_candidates=1,
            expected_contains=["特高压直流输电"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_037",
            mention="碳中和",
            description="专业术语 - 中文名称",
            expected_min_candidates=1,
            expected_contains=["碳中和"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_038",
            mention="双碳",
            description="专业术语 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["碳中和"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_039",
            mention="抽水蓄能",
            description="专业术语 - 完整名称",
            expected_min_candidates=1,
            expected_contains=["抽水蓄能"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_040",
            mention="抽蓄",
            description="专业术语 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["抽水蓄能"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_041",
            mention="虚拟电厂",
            description="专业术语 - 中文名称",
            expected_min_candidates=1,
            expected_contains=["虚拟电厂"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_042",
            mention="VPP",
            description="专业术语 - 英文缩写",
            expected_min_candidates=1,
            expected_contains=["虚拟电厂"],
            expected_methods=["alias_exact"]
        ),

        # === 地区测试 ===
        TestCase(
            id="CG_043",
            mention="深圳市",
            description="地区 - 带'市'的全称",
            expected_min_candidates=1,
            expected_contains=["深圳市"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_044",
            mention="深圳",
            description="地区 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["深圳市"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_045",
            mention="北京市",
            description="地区 - 带'市'的全称",
            expected_min_candidates=1,
            expected_contains=["北京市"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_046",
            mention="北京",
            description="地区 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["北京市"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_047",
            mention="雄安新区",
            description="地区 - 国家级新区",
            expected_min_candidates=1,
            expected_contains=["雄安新区"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_048",
            mention="雄安",
            description="地区 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["雄安新区"],
            expected_methods=["alias_exact"]
        ),

        # === 科技企业测试 ===
        TestCase(
            id="CG_049",
            mention="华为",
            description="科技企业 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["华为技术有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_050",
            mention="腾讯",
            description="科技企业 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["腾讯控股有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_051",
            mention="阿里巴巴",
            description="科技企业 - 四字简称",
            expected_min_candidates=1,
            expected_contains=["阿里巴巴集团控股有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_052",
            mention="阿里",
            description="科技企业 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["阿里巴巴集团控股有限公司"],
            expected_methods=["alias_exact"]
        ),

        # === 金融机构测试 ===
        TestCase(
            id="CG_053",
            mention="工商银行",
            description="金融机构 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["中国工商银行股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_054",
            mention="工行",
            description="金融机构 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["中国工商银行股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_055",
            mention="ICBC",
            description="金融机构 - 英文缩写",
            expected_min_candidates=1,
            expected_contains=["中国工商银行股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_056",
            mention="招商银行",
            description="金融机构 - 四字简称",
            expected_min_candidates=1,
            expected_contains=["招商银行股份有限公司"],
            expected_methods=["alias_exact"]
        ),
        TestCase(
            id="CG_057",
            mention="招行",
            description="金融机构 - 两字简称",
            expected_min_candidates=1,
            expected_contains=["招商银行股份有限公司"],
            expected_methods=["alias_exact"]
        ),

        # === 歧义/边缘测试 ===
        TestCase(
            id="CG_058",
            mention="国网公司",
            description="歧义别名 - '国网公司'可能匹配多个实体（模糊匹配）",
            expected_min_candidates=1,
            expected_contains=["国家电网有限公司"],
            expected_methods=["alias_fuzzy", "alias_exact"]
        ),
        TestCase(
            id="CG_059",
            mention="能源",
            description="泛化查询 - 应通过向量检索返回多个能源类实体",
            expected_min_candidates=3,
            expected_contains=[],
            expected_methods=["vector"]
        ),
        TestCase(
            id="CG_060",
            mention="电力",
            description="泛化查询 - 应通过向量检索返回多个电力类实体",
            expected_min_candidates=3,
            expected_contains=[],
            expected_methods=["vector"]
        ),
        TestCase(
            id="CG_061",
            mention="不存在的实体XYZ",
            description="不存在的实体 - 应无候选",
            expected_min_candidates=0,
            expected_contains=[],
            expected_methods=[]
        ),
    ]


# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 70)
    print("🧪 候选生成模块测试 (基于 energy_entities.json)")
    print("=" * 70)

    tester = CandidateGenerationTester()
    test_cases = get_test_cases()
    print(f"\n📋 加载测试用例: {len(test_cases)} 个")

    summary = tester.run_batch(test_cases)
    tester.print_summary(summary)

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())