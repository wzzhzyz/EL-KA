# tests/test_ner_with_eval_dataset.py
"""
使用评测数据集测试NER能力
从 eval_dataset.json 中提取 mention，测试 NER 模型是否能正确识别
"""

import sys
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.ner import NEREngine
from src.utils.config import load_config
from src.utils.logger import logger


class NEREvalDatasetTester:
    """使用评测数据集测试 NER 能力"""

    def __init__(self, dataset_path: str = None):
        self.config = load_config()
        self.ner = NEREngine(self.config["ner"])
        self.results = []

        # 加载数据集 - 自动查找多个可能路径
        if dataset_path is None:
            possible_paths = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval_dataset.json"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "eval_dataset.json"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "eval_dataset.json"),
                "eval_dataset.json",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    dataset_path = path
                    break
            else:
                dataset_path = possible_paths[0]

        self.dataset_path = dataset_path
        self.dataset = self._load_dataset()

        # 统计信息
        self.stats = {
            "total_mentions": 0,
            "success": 0,
            "partial": 0,
            "missed": 0,
            "type_error": 0,
            "error": 0,
            "by_scenario": {},
            "by_difficulty": {},
        }

        # 收集所有不符合预期的结果
        self.unexpected_results = []

    def _load_dataset(self) -> Dict:
        """加载评测数据集"""
        if not os.path.exists(self.dataset_path):
            logger.warning(f"⚠️ 数据集文件不存在: {self.dataset_path}")
            logger.info(f"📌 请将 eval_dataset.json 放在以下位置之一:")
            logger.info(f"   - 项目根目录: {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/")
            logger.info(f"   - data/ 目录: {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/data/")
            return {"samples": []}

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        logger.info(f"📚 加载评测数据集: {self.dataset_path}")
        logger.info(f"   📋 共 {len(data.get('samples', []))} 个样本")
        logger.info(f"   📝 版本: {data.get('dataset_metadata', {}).get('version', 'unknown')}")
        return data

    def _get_all_entity_mentions(self, entities: List[Dict]) -> List[str]:
        """获取所有实体mention"""
        return [e.get("mention", "") for e in entities]

    def _get_entities_detail(self, entities: List[Dict]) -> List[Dict]:
        """获取实体详细信息"""
        return [
            {
                "mention": e.get("mention", ""),
                "type": e.get("type", ""),
                "start": e.get("start", -1),
                "end": e.get("end", -1)
            }
            for e in entities
        ]

    def _check_mention_match(self, mention: str, start: int, end: int,
                             entities: List[Dict]) -> Tuple[str, Optional[Dict], List[Dict]]:
        """
        检查mention是否被识别

        Returns:
            (匹配状态, 匹配的实体, 重叠的实体列表)
        """
        matched_entity = None
        overlapping = []
        exact_match = None

        for ent in entities:
            ent_text = ent.get("mention", "")
            ent_start = ent.get("start", -1)
            ent_end = ent.get("end", -1)

            # 完全精确匹配
            if ent_text == mention and ent_start == start and ent_end == end:
                exact_match = ent
                matched_entity = ent
                break

            # 边界重叠但文本不完全匹配
            if ent_start < end and ent_end > start:
                overlapping.append(ent)
                if not matched_entity:
                    matched_entity = ent

        if exact_match:
            return "exact", exact_match, []
        elif matched_entity:
            return "partial", matched_entity, overlapping
        else:
            return "missed", None, []

    def _check_type_match(self, expected_type: str, actual_type: str) -> Tuple[bool, str, str]:
        """检查实体类型是否匹配"""
        type_mapping = {
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

        mapped_actual = type_mapping.get(actual_type, actual_type)

        if mapped_actual == expected_type:
            return True, "类型匹配", ""
        elif expected_type in ['ORG', 'GPE', 'PERSON'] and mapped_actual in ['ORG', 'GPE', 'PERSON']:
            return True, f"类型映射匹配: {actual_type}->{mapped_actual} (期望{expected_type})", ""
        else:
            return False, "类型不匹配", f"期望 {expected_type}, 实际 {actual_type}(映射为{mapped_actual})"

    def _infer_entity_type(self, sample: Dict) -> str:
        """从样本推断实体类型"""
        mention = sample.get("mention", "")
        scenario = sample.get("scenario", "")
        gold_entity = sample.get("gold_entity")

        # 从candidate_entities推断
        candidates = sample.get("candidate_entities", [])
        if candidates:
            # 如果能从KB获取类型更好，这里简化处理
            pass

        # 根据地名特征推断
        if mention.endswith("地区") or mention.endswith("市") or mention.endswith("省"):
            return "GPE"

        # 根据常见组织推断
        org_keywords = ["集团", "公司", "有限", "电力", "能源", "电网", "石油", "石化", "核电", "核工业"]
        if any(kw in mention for kw in org_keywords):
            return "ORG"

        # 根据场景推断
        if scenario in ["简称匹配", "完整名称匹配", "英文别名匹配", "同名异义消歧"]:
            return "ORG"

        if scenario in ["上下文消歧", "长文本多mention共指验证"]:
            return "ORG"

        return "ORG"  # 默认

    def test_sample(self, sample: Dict) -> Dict:
        """测试单个样本的NER识别能力"""
        text = sample.get("text", "")
        mention = sample.get("mention", "")
        mention_start = sample.get("mention_start", 0)
        mention_end = sample.get("mention_end", len(mention))
        gold_entity = sample.get("gold_entity")
        gold_entity_name = sample.get("gold_entity_name")
        scenario = sample.get("scenario", "unknown")
        difficulty = sample.get("difficulty", "unknown")
        expected_result = sample.get("expected_result", {})

        result = {
            "sample_id": sample.get("id", "unknown"),
            "text": text,
            "mention": mention,
            "mention_start": mention_start,
            "mention_end": mention_end,
            "gold_entity": gold_entity,
            "gold_entity_name": gold_entity_name,
            "scenario": scenario,
            "difficulty": difficulty,
            "expected_result": expected_result,
            "ner_entities": [],
            "ner_mentions": [],
            "match_status": "unknown",
            "matched_entity": None,
            "matched_entity_detail": None,
            "overlapping_entities": [],
            "type_match": False,
            "type_detail": "",
            "is_expected": False,
            "errors": [],
            "warnings": [],
            "all_ner_output": []
        }

        try:
            # 执行NER
            entities = self.ner.extract(text)
            result["ner_entities"] = entities
            result["ner_mentions"] = self._get_all_entity_mentions(entities)
            result["all_ner_output"] = self._get_entities_detail(entities)

            # 检查mention是否被识别
            match_status, matched_ent, overlapping = self._check_mention_match(
                mention, mention_start, mention_end, entities
            )

            result["match_status"] = match_status
            result["matched_entity"] = matched_ent
            if matched_ent:
                result["matched_entity_detail"] = {
                    "mention": matched_ent.get("mention", ""),
                    "type": matched_ent.get("type", ""),
                    "start": matched_ent.get("start", -1),
                    "end": matched_ent.get("end", -1)
                }
            result["overlapping_entities"] = overlapping

            # 判断是否预期
            expected_linked = expected_result.get("linked", False)

            if match_status == "exact":
                # 精确匹配成功
                expected_type = self._infer_entity_type(sample)
                type_ok, type_status, type_detail = self._check_type_match(
                    expected_type, matched_ent.get("type", "")
                )
                result["type_match"] = type_ok
                result["type_detail"] = type_detail

                if type_ok:
                    result["is_expected"] = True
                    result["status"] = "success"
                else:
                    result["is_expected"] = False
                    result["status"] = "type_error"
                    result["errors"].append(type_detail)
            elif match_status == "partial":
                # 部分匹配
                result["is_expected"] = False
                result["status"] = "partial"
                result["errors"].append(f"部分匹配: 期望 '{mention}'，实际识别为 '{matched_ent.get('mention')}'")
                if overlapping:
                    result["errors"].append(f"重叠实体: {[e.get('mention') for e in overlapping]}")
            else:
                # 完全未识别
                result["is_expected"] = False
                result["status"] = "missed"
                result["errors"].append(f"完全未识别: 期望 '{mention}'")

            # 检查是否有多余的实体（不在期望中）
            expected_mentions = []
            # 从样本中提取所有期望的mention
            if "expected_result" in sample and "expected_mentions" in sample.get("expected_result", {}):
                expected_mentions = sample["expected_result"].get("expected_mentions", [])

            # 如果有多个mention期望，检查NER是否识别了多余的
            # 这里简化处理

        except Exception as e:
            result["status"] = "error"
            result["is_expected"] = False
            result["errors"].append(f"执行错误: {str(e)}")

        return result

    def run_all_tests(self) -> Dict:
        """运行所有测试"""
        samples = self.dataset.get("samples", [])
        logger.info(f"🧪 开始NER评测，共 {len(samples)} 个样本")

        self.results = []
        self.unexpected_results = []

        status_counts = {"success": 0, "partial": 0, "missed": 0, "type_error": 0, "error": 0}
        scenario_stats = {}
        difficulty_stats = {}

        # 过滤出有mention的样本
        valid_samples = [s for s in samples if s.get("mention")]

        if not valid_samples:
            logger.warning("⚠️ 没有找到包含mention的样本")
            return self.stats

        for i, sample in enumerate(valid_samples):
            result = self.test_sample(sample)
            self.results.append(result)

            status = result["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

            # 收集不符合预期的结果
            if not result["is_expected"]:
                self.unexpected_results.append(result)

            # 按场景统计
            scenario = result["scenario"]
            if scenario not in scenario_stats:
                scenario_stats[scenario] = {"total": 0, "success": 0, "partial": 0, "missed": 0, "type_error": 0}
            scenario_stats[scenario]["total"] += 1
            if status in scenario_stats[scenario]:
                scenario_stats[scenario][status] += 1

            # 按难度统计
            difficulty = result["difficulty"]
            if difficulty not in difficulty_stats:
                difficulty_stats[difficulty] = {"total": 0, "success": 0, "partial": 0, "missed": 0, "type_error": 0}
            difficulty_stats[difficulty]["total"] += 1
            if status in difficulty_stats[difficulty]:
                difficulty_stats[difficulty][status] += 1

            status_icon = {"success": "✅", "partial": "🟡", "missed": "❌", "type_error": "⚠️", "error": "💥"}.get(status,
                                                                                                                "❓")
            logger.info(
                f"  [{i + 1}/{len(valid_samples)}] {status_icon} {result['sample_id']}: '{result['mention']}' -> {status}")

        total = len(self.results)
        self.stats = {
            "total_mentions": total,
            "success": status_counts["success"],
            "partial": status_counts["partial"],
            "missed": status_counts["missed"],
            "type_error": status_counts["type_error"],
            "error": status_counts["error"],
            "success_rate": status_counts["success"] / total if total > 0 else 0,
            "recall": (status_counts["success"] + status_counts["partial"]) / total if total > 0 else 0,
            "by_scenario": scenario_stats,
            "by_difficulty": difficulty_stats,
            "unexpected_count": len(self.unexpected_results)
        }

        logger.info(f"📊 NER评测完成:")
        logger.info(f"   ✅ 完全匹配: {status_counts['success']}")
        logger.info(f"   🟡 部分匹配: {status_counts['partial']}")
        logger.info(f"   ❌ 完全未识别: {status_counts['missed']}")
        logger.info(f"   ⚠️ 类型错误: {status_counts['type_error']}")
        logger.info(f"   💥 执行错误: {status_counts['error']}")
        logger.info(f"   📈 召回率: {self.stats['recall']:.1%}")
        logger.info(f"   📈 精确匹配率: {self.stats['success_rate']:.1%}")
        logger.info(f"   ⚠️ 不符合预期: {len(self.unexpected_results)}")

        return self.stats

    def print_detailed_report(self):
        """打印详细报告"""
        print("\n" + "=" * 80)
        print("📊 NER 评测报告 - 基于评测数据集")
        print("=" * 80)

        metadata = self.dataset.get("dataset_metadata", {})
        print(f"  数据集: {metadata.get('name', 'unknown')}")
        print(f"  版本: {metadata.get('version', 'unknown')}")
        print(f"  总样本数: {metadata.get('total_samples', 0)}")
        print(f"  测试mentions: {self.stats['total_mentions']}")
        print()

        print("📈 整体表现:")
        print(f"  ✅ 完全匹配: {self.stats['success']} ({self.stats['success_rate']:.1%})")
        print(f"  🟡 部分匹配: {self.stats['partial']}")
        print(f"  ❌ 完全未识别: {self.stats['missed']}")
        print(f"  ⚠️ 类型错误: {self.stats['type_error']}")
        print(f"  💥 执行错误: {self.stats['error']}")
        print(f"  📈 召回率: {self.stats['recall']:.1%}")
        print(f"  ⚠️ 不符合预期总数: {self.stats['unexpected_count']}")
        print()

        # 按场景统计
        if self.stats["by_scenario"]:
            print("-" * 80)
            print("📊 按场景分类:")
            print("-" * 80)
            for scenario, stats in sorted(self.stats["by_scenario"].items()):
                total = stats["total"]
                success = stats["success"]
                partial = stats["partial"]
                missed = stats["missed"]
                type_error = stats["type_error"]
                success_rate = success / total if total > 0 else 0
                recall = (success + partial) / total if total > 0 else 0
                print(f"  {scenario}:")
                print(f"    总数: {total}, 成功: {success}({success_rate:.1%}), 召回: {recall:.1%}")
                if missed > 0:
                    print(f"    ❌ 未识别: {missed}")
                if type_error > 0:
                    print(f"    ⚠️ 类型错误: {type_error}")

        # 按难度统计
        if self.stats["by_difficulty"]:
            print()
            print("-" * 80)
            print("📊 按难度分类:")
            print("-" * 80)
            for difficulty, stats in sorted(self.stats["by_difficulty"].items()):
                total = stats["total"]
                success = stats["success"]
                partial = stats["partial"]
                missed = stats["missed"]
                success_rate = success / total if total > 0 else 0
                recall = (success + partial) / total if total > 0 else 0
                print(f"  {difficulty.upper()}:")
                print(f"    总数: {total}, 成功: {success}({success_rate:.1%}), 召回: {recall:.1%}")
                if missed > 0:
                    print(f"    ❌ 未识别: {missed}")

        # ============================================================
        # 打印所有不符合预期的结果（完整详情）
        # ============================================================
        if self.unexpected_results:
            print()
            print("=" * 80)
            print(f"❌ 不符合预期的结果详情 (共 {len(self.unexpected_results)} 个)")
            print("=" * 80)

            for idx, r in enumerate(self.unexpected_results, 1):
                print(f"\n{'=' * 70}")
                print(f"【{idx}/{len(self.unexpected_results)}】 {r['sample_id']} - {r['scenario']}")
                print(f"{'=' * 70}")

                # 原文本
                print(f"\n📝 原文本:")
                print(f"   {r['text']}")

                # 期望的mention
                print(f"\n🎯 期望识别:")
                print(f"   mention: '{r['mention']}'")
                print(f"   位置: [{r['mention_start']}:{r['mention_end']}]")
                if r.get('gold_entity_name'):
                    print(f"   gold_entity: {r['gold_entity_name']} ({r.get('gold_entity')})")
                if r.get('expected_result'):
                    expected = r['expected_result']
                    print(
                        f"   expected_result: linked={expected.get('linked')}, correct_entity={expected.get('correct_entity')}")

                # NER识别结果
                print(f"\n🔍 NER识别结果 (共 {len(r['ner_entities'])} 个实体):")
                if r['ner_entities']:
                    for ent in r['ner_entities']:
                        ent_text = ent.get("mention", "")
                        ent_type = ent.get("type", "")
                        ent_start = ent.get("start", -1)
                        ent_end = ent.get("end", -1)
                        print(f"   - '{ent_text}' ({ent_type}) [{ent_start}:{ent_end}]")
                else:
                    print(f"   (未识别到任何实体)")

                # 匹配状态
                print(f"\n📊 匹配状态: {r['match_status']}")
                if r.get('matched_entity_detail'):
                    matched = r['matched_entity_detail']
                    print(
                        f"   匹配实体: '{matched['mention']}' ({matched['type']}) [{matched['start']}:{matched['end']}]")

                # 错误详情
                if r['errors']:
                    print(f"\n❌ 错误:")
                    for error in r['errors']:
                        print(f"   - {error}")

                # 警告
                if r['warnings']:
                    print(f"\n⚠️ 警告:")
                    for warning in r['warnings']:
                        print(f"   - {warning}")

                # 类型匹配
                if r['status'] == 'type_error':
                    print(f"\n⚠️ 类型错误详情: {r.get('type_detail', '')}")

                print(f"\n📌 状态: {r['status']}")
                print(f"   {'✅ 符合预期' if r['is_expected'] else '❌ 不符合预期'}")
                print(f"   {r['difficulty'].upper()} 难度")

    def save_report(self, output_file: str = None):
        """保存测试报告"""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"reports/ner_eval_report_{timestamp}.json"

        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        report = {
            "timestamp": datetime.now().isoformat(),
            "dataset": {
                "path": self.dataset_path,
                "metadata": self.dataset.get("dataset_metadata", {})
            },
            "stats": self.stats,
            "unexpected_results": self.unexpected_results,
            "all_results": self.results
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"📄 详细报告已保存: {output_file}")
        return output_file


# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 80)
    print("🔬 NER 评测 - 使用评测数据集")
    print("=" * 80)

    dataset_path = None
    if len(sys.argv) > 1:
        dataset_path = sys.argv[1]

    tester = NEREvalDatasetTester(dataset_path)
    tester.run_all_tests()
    tester.print_detailed_report()
    tester.save_report()

    # 返回退出码
    return 1 if tester.stats['unexpected_count'] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())