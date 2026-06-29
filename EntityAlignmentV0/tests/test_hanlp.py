# tests/test_hanlp_raw.py
"""
HanLP 原始输出测试模块
不对NER输出做任何加工处理，直接观察模型的原始识别能力
"""

import sys
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hanlp
from src.utils.config import load_config
from src.utils.logger import logger


class HanLPRawTester:
    """HanLP 原始输出测试器 - 不做任何加工处理"""

    def __init__(self, model_name: str = None):
        self.config = load_config()
        self.model_name = model_name or self.config["ner"].get(
            "hanlp_model",
            "CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH"
        )
        self._model = None
        self.results = []

        # 实体类型映射（仅用于显示，不用于过滤）
        self.type_mapping = {
            'ORGANIZATION': 'ORG',
            'ORG': 'ORG',
            'nt': 'ORG',
            'PERSON': 'PERSON',
            'nr': 'PERSON',
            'LOCATION': 'GPE',
            'LOC': 'GPE',
            'ns': 'GPE',
            'GPE': 'GPE'
        }

    def _load_model(self):
        """加载HanLP模型"""
        if self._model is None:
            logger.info(f"📦 加载HanLP模型: {self.model_name}")
            self._model = hanlp.load(self.model_name)
            logger.info("✅ 模型加载完成")

    def _get_raw_output(self, text: str) -> Dict:
        """
        获取HanLP的原始输出，不做任何加工

        Returns:
            Dict: 包含原始输出的所有信息
        """
        self._load_model()
        result = self._model(text)

        raw_output = {
            "text": text,
            "raw_result": result,
            "all_entities": [],
            "ner_sources": {}
        }

        # 检查是否是 HanLP Document 对象
        if hasattr(result, 'to_dict'):
            result_dict = result.to_dict()
            raw_output["result_dict"] = result_dict

            # 提取所有NER源的数据
            ner_keys = [key for key in result_dict.keys() if 'ner' in key]
            for key in ner_keys:
                ner_data = result_dict[key]
                entities = []
                if ner_data:
                    for item in ner_data:
                        if isinstance(item, (tuple, list)) and len(item) >= 4:
                            entities.append({
                                "text": str(item[0]),
                                "type": str(item[1]),
                                "begin": int(item[2]),
                                "end": int(item[3])
                            })
                raw_output["ner_sources"][key] = entities

            # 汇总所有实体（去重）
            all_entities = []
            seen = set()
            for source, entities in raw_output["ner_sources"].items():
                for ent in entities:
                    key = f"{ent['text']}_{ent['type']}_{ent['begin']}_{ent['end']}"
                    if key not in seen:
                        seen.add(key)
                        all_entities.append(ent)
            raw_output["all_entities"] = all_entities

        # 如果result是列表格式
        elif isinstance(result, list):
            entities = []
            for item in result:
                if isinstance(item, dict):
                    entities.append({
                        "text": item.get("text", ""),
                        "type": item.get("type", ""),
                        "begin": item.get("begin", 0),
                        "end": item.get("end", 0)
                    })
                elif isinstance(item, (tuple, list)) and len(item) >= 4:
                    entities.append({
                        "text": str(item[0]),
                        "type": str(item[1]),
                        "begin": int(item[2]) if len(item) > 2 else 0,
                        "end": int(item[3]) if len(item) > 3 else 0
                    })
            raw_output["all_entities"] = entities
            raw_output["result_list"] = result

        return raw_output

    def test_single(self, text: str, expected: Optional[List[Dict]] = None) -> Dict:
        """
        测试单个文本的原始输出

        Args:
            text: 输入文本
            expected: 期望的实体列表（可选）

        Returns:
            Dict: 测试结果
        """
        result = {
            "text": text,
            "expected": expected or [],
            "raw_entities": [],
            "expected_mentions": [e["mention"] for e in (expected or [])],
            "actual_mentions": [],
            "all_ner_sources": {},
            "passed": False,
            "errors": [],
            "warnings": []
        }

        try:
            raw_output = self._get_raw_output(text)
            result["all_ner_sources"] = raw_output["ner_sources"]
            result["raw_entities"] = raw_output["all_entities"]

            # 提取所有实体的mention（保留所有类型）
            result["actual_mentions"] = [e["text"] for e in raw_output["all_entities"]]

            # 如果有期望结果，进行对比
            if expected:
                expected_mentions = [e["mention"] for e in expected]
                actual_mentions = result["actual_mentions"]

                # 检查遗漏
                missing = set(expected_mentions) - set(actual_mentions)
                if missing:
                    result["errors"].append(f"遗漏实体: {list(missing)}")

                # 检查多余
                extra = set(actual_mentions) - set(expected_mentions)
                if extra:
                    result["warnings"].append(f"额外识别: {list(extra)}")

                # 检查类型匹配（只检查期望中有的实体）
                for exp in expected:
                    exp_mention = exp["mention"]
                    exp_type = exp["type"]
                    # 在原始实体中查找匹配的mention
                    matches = [e for e in raw_output["all_entities"] if e["text"] == exp_mention]
                    if matches:
                        for match in matches:
                            raw_type = match["type"]
                            # 尝试映射类型
                            mapped_type = self.type_mapping.get(raw_type, raw_type)
                            if mapped_type != exp_type:
                                result["warnings"].append(
                                    f"类型差异: '{exp_mention}' 期望 {exp_type}, 原始类型 {raw_type} (映射后 {mapped_type})"
                                )

                result["passed"] = len(result["errors"]) == 0
            else:
                result["passed"] = True
                result["warnings"].append("无期望结果，仅记录原始输出")

        except Exception as e:
            result["errors"].append(f"执行错误: {str(e)}")
            result["passed"] = False

        return result

    def run_batch(self, test_cases: List[Dict]) -> Dict:
        """
        批量运行测试用例

        Args:
            test_cases: 测试用例列表

        Returns:
            Dict: 批量测试结果汇总
        """
        logger.info(f"🧪 开始HanLP原始输出测试，共 {len(test_cases)} 个用例")

        self.results = []
        passed_count = 0
        failed_count = 0

        for i, case in enumerate(test_cases):
            text = case.get("text", "")
            expected = case.get("expected", [])

            result = self.test_single(text, expected)
            self.results.append(result)

            if result["passed"]:
                passed_count += 1
            else:
                failed_count += 1

            # 打印简要进度
            status = "✅" if result["passed"] else "❌"
            mentions = result["actual_mentions"]
            mentions_str = ", ".join(mentions[:3]) + ("..." if len(mentions) > 3 else "")
            logger.info(f"  [{i + 1}/{len(test_cases)}] {status} {text[:25]}... -> [{mentions_str}]")

        summary = {
            "total": len(test_cases),
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate": passed_count / len(test_cases) if test_cases else 0,
            "results": self.results
        }

        logger.info(f"📊 测试完成: 通过 {passed_count}, 失败 {failed_count}, 通过率 {summary['pass_rate']:.1%}")

        return summary

    def print_detailed_report(self, summary: Dict):
        """打印详细测试报告"""
        print("\n" + "=" * 80)
        print("📊 HanLP 原始输出测试报告")
        print("=" * 80)
        print(f"  📋 总用例数: {summary['total']}")
        print(f"  ✅ 通过: {summary['passed']}")
        print(f"  ❌ 失败: {summary['failed']}")
        print(f"  📈 通过率: {summary['pass_rate']:.1%}")

        # 统计实体类型分布
        type_stats = {}
        for result in summary["results"]:
            for ent in result["raw_entities"]:
                ent_type = ent.get("type", "UNKNOWN")
                type_stats[ent_type] = type_stats.get(ent_type, 0) + 1

        if type_stats:
            print("\n" + "-" * 80)
            print("📊 原始实体类型分布:")
            print("-" * 80)
            for ent_type, count in sorted(type_stats.items(), key=lambda x: -x[1]):
                print(f"  {ent_type}: {count}")

        # 打印失败用例详情
        if summary["failed"] > 0:
            print("\n" + "-" * 80)
            print("❌ 失败用例详情:")
            print("-" * 80)
            for result in summary["results"]:
                if not result["passed"]:
                    print(f"\n📝 文本: {result['text']}")
                    print(f"   期望: {result['expected_mentions']}")
                    print(f"   实际: {result['actual_mentions']}")
                    for error in result["errors"]:
                        print(f"   ⚠️ {error}")
                    if result["warnings"]:
                        for warning in result["warnings"]:
                            print(f"   💡 {warning}")
                    # 打印各NER源的输出
                    if result["all_ner_sources"]:
                        print("   🔍 各NER源输出:")
                        for source, entities in result["all_ner_sources"].items():
                            if entities:
                                ents = [f"{e['text']}({e['type']})" for e in entities]
                                print(f"      {source}: {ents}")

    def save_report(self, summary: Dict, output_file: str = None):
        """保存详细报告到JSON文件"""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"reports/hanlp_raw_test_{timestamp}.json"

        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        report = {
            "timestamp": datetime.now().isoformat(),
            "model_name": self.model_name,
            "summary": {
                "total": summary["total"],
                "passed": summary["passed"],
                "failed": summary["failed"],
                "pass_rate": summary["pass_rate"]
            },
            "details": []
        }

        for r in summary["results"]:
            report["details"].append({
                "text": r["text"],
                "expected": r["expected"],
                "expected_mentions": r["expected_mentions"],
                "actual_mentions": r["actual_mentions"],
                "raw_entities": r["raw_entities"],
                "all_ner_sources": r["all_ner_sources"],
                "passed": r["passed"],
                "errors": r["errors"],
                "warnings": r["warnings"]
            })

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"📄 详细报告已保存: {output_file}")
        return output_file


# ============================================================
# 测试用例定义（精简版，重点测试边界情况）
# ============================================================

def get_test_cases() -> List[Dict]:
    """获取测试用例（重点测试边界情况）"""
    return [
        # === 基础组织机构测试 ===
        {
            "text": "国家电网有限公司2025年营收增长5%。",
            "expected": [{"mention": "国家电网有限公司", "type": "ORG"}]
        },
        {
            "text": "中国南方电网有限责任公司2024年财报发布。",
            "expected": [{"mention": "中国南方电网有限责任公司", "type": "ORG"}]
        },
        {
            "text": "华能国际电力股份有限公司在华东地区有多个项目。",
            "expected": [{"mention": "华能国际电力股份有限公司", "type": "ORG"}, {"mention": "华东地区", "type": "GPE"}]
        },
        {
            "text": "中国石油天然气集团有限公司2024年净利润增长10%。",
            "expected": [{"mention": "中国石油天然气集团有限公司", "type": "ORG"}]
        },
        {
            "text": "国家能源投资集团有限责任公司在宁夏新建光伏电站。",
            "expected": [{"mention": "国家能源投资集团有限责任公司", "type": "ORG"}, {"mention": "宁夏", "type": "GPE"}]
        },

        # === 地区名称测试（重点问题区域） ===
        {
            "text": "华北地区新建了输电线路。",
            "expected": [{"mention": "华北地区", "type": "GPE"}]
        },
        {
            "text": "华东地区有多个项目正在建设中。",
            "expected": [{"mention": "华东地区", "type": "GPE"}]
        },
        {
            "text": "华中地区电网负荷创历史新高。",
            "expected": [{"mention": "华中地区", "type": "GPE"}]
        },
        {
            "text": "华南地区电力需求快速增长。",
            "expected": [{"mention": "华南地区", "type": "GPE"}]
        },
        {
            "text": "西南地区水电资源丰富。",
            "expected": [{"mention": "西南地区", "type": "GPE"}]
        },
        {
            "text": "西北地区光伏发电装机容量快速增长。",
            "expected": [{"mention": "西北地区", "type": "GPE"}]
        },
        {
            "text": "东北地区电网2025年改造升级。",
            "expected": [{"mention": "东北地区", "type": "GPE"}]
        },

        # === 简称测试 ===
        {
            "text": "国网在华北新建了输电线路。",
            "expected": []
        },
        {
            "text": "国家电投2025年光伏发电量增长。",
            "expected": []
        },
        {
            "text": "中广核2025年核电安全运营。",
            "expected": []
        },
        {
            "text": "华能集团2025年新能源装机突破。",
            "expected": []
        },

        # === 复合地名测试 ===
        {
            "text": "上海市浦东新区建成大型光储充一体化电站。",
            "expected": [{"mention": "上海市浦东新区", "type": "GPE"}]
        },
        {
            "text": "公司地址：北京市西城区金融大街。",
            "expected": [{"mention": "北京市西城区", "type": "GPE"}]
        },
        {
            "text": "新疆维吾尔自治区2025年新能源装机突破。",
            "expected": [{"mention": "新疆维吾尔自治区", "type": "GPE"}]
        },
        {
            "text": "内蒙古自治区2025年风电项目并网。",
            "expected": [{"mention": "内蒙古自治区", "type": "GPE"}]
        },

        # === 多实体测试 ===
        {
            "text": "国家电网有限公司在华北地区新建了输电线路。",
            "expected": [{"mention": "国家电网有限公司", "type": "ORG"}, {"mention": "华北地区", "type": "GPE"}]
        },
        {
            "text": "国家电网有限公司在华北、华东、华中和华南地区均有业务布局。",
            "expected": [{"mention": "国家电网有限公司", "type": "ORG"}, {"mention": "华北地区", "type": "GPE"},
                         {"mention": "华东地区", "type": "GPE"}, {"mention": "华中地区", "type": "GPE"},
                         {"mention": "华南地区", "type": "GPE"}]
        },
        {
            "text": "华北地区、华东地区、华中地区、华南地区、西南地区、西北地区、东北地区均有电力项目。",
            "expected": [{"mention": "华北地区", "type": "GPE"}, {"mention": "华东地区", "type": "GPE"},
                         {"mention": "华中地区", "type": "GPE"}, {"mention": "华南地区", "type": "GPE"},
                         {"mention": "西南地区", "type": "GPE"}, {"mention": "西北地区", "type": "GPE"},
                         {"mention": "东北地区", "type": "GPE"}]
        },

        # === 边界情况 ===
        {
            "text": "",
            "expected": []
        },
        {
            "text": "这是一个没有任何实体的纯文本测试。",
            "expected": []
        },
        {
            "text": "2025年，公司营收达到100亿元。",
            "expected": []
        },
        {
            "text": "国家电网公司国家电网公司重复实体测试。",
            "expected": [{"mention": "国家电网公司", "type": "ORG"}]
        },
    ]


# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 80)
    print("🔬 HanLP 原始输出测试")
    print("=" * 80)
    print("说明: 本测试不对NER输出做任何加工处理，直接观察模型原始识别能力")
    print("=" * 80)

    # 创建测试器
    tester = HanLPRawTester()

    # 获取测试用例
    test_cases = get_test_cases()
    print(f"\n📋 加载了 {len(test_cases)} 个测试用例\n")

    # 运行测试
    summary = tester.run_batch(test_cases)

    # 打印详细报告
    tester.print_detailed_report(summary)

    # 保存报告
    tester.save_report(summary)

    # 返回退出码
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())