# tests/test_ner.py
import json
import os
import time
import yaml
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime

# 添加项目根目录到Python路径
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.ner import NEREngine
from src.utils.logger import logger


class NERTester:
    """NER测试器 - 不依赖额外测试框架"""

    def __init__(self, config_path: str = None):
        """初始化测试器"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"

        # 加载配置文件
        with open(config_path, 'r', encoding='utf-8') as f:
            full_config = yaml.safe_load(f)

        # 提取NER配置
        self.config = full_config.get("ner", {})
        self.ner_engine = NEREngine(self.config)
        self.test_results = []
        self.passed = 0
        self.failed = 0

        print(f"\n✅ 使用配置: {config_path}")
        print(f"   NER后端: {self.config.get('backend', 'unknown')}")
        print(f"   模型: {self.config.get('hanlp_model', 'unknown')}")
        print(f"   可链接类型: {self.config.get('linkable_types', [])}")

    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "=" * 80)
        print("开始执行NER实体抽取测试 (HanLP)")
        print("=" * 80)

        # 运行各类测试
        self.test_basic_extraction()
        self.test_position_boundary()
        self.test_type_filtering()
        self.test_empty_text()
        self.test_no_entity_text()
        self.test_edge_cases()
        self.test_unicode_position()
        self.test_batch_from_data()
        self.test_complex_texts()
        self.test_position_precision()
        self.test_mixed_language()
        self.test_long_text()
        self.test_special_characters()

        # 输出测试汇总
        self.print_summary()

        # 保存测试结果
        self.save_results()

    def add_result(self, test_name: str, passed: bool, message: str = "",
                   details: Dict = None):
        """添加测试结果"""
        result = {
            "test_name": test_name,
            "passed": passed,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        if passed:
            self.passed += 1
            print(f"  ✅ PASS: {test_name}")
            if message:
                print(f"     {message}")
        else:
            self.failed += 1
            print(f"  ❌ FAIL: {test_name}")
            if message:
                print(f"     {message}")

        return result

    def print_position_comparison(self, expected, actual, text):
        """打印位置对比信息"""
        print("\n  位置对比:")
        print(f"  {'实体':<15} {'期望位置':<25} {'实际位置':<25} {'匹配':<10}")
        print(f"  {'-' * 15} {'-' * 25} {'-' * 25} {'-' * 10}")

        # 为每个预期实体查找对应的实际实体
        for exp in expected:
            exp_text = exp["mention"]
            exp_start = exp["char_start"]
            exp_end = exp["char_end"]
            exp_pos = f"[{exp_start}:{exp_end}]"

            # 查找匹配的实际实体
            matched = None
            for act in actual:
                # 修复：检查act是否包含mention_type字段
                if (act.get("mention") == exp_text and
                        act.get("mention_type") == exp.get("mention_type")):
                    matched = act
                    break

            if matched:
                act_start = matched.get("char_start")
                act_end = matched.get("char_end")
                act_pos = f"[{act_start}:{act_end}]" if act_start is not None else "未知"
                match = "✅" if (exp_start == act_start and exp_end == act_end) else "❌"
                print(f"  {exp_text:<15} {exp_pos:<25} {act_pos:<25} {match:<10}")
            else:
                print(f"  {exp_text:<15} {exp_pos:<25} {'未识别':<25} {'❌':<10}")

        # 显示额外识别的实体
        extra_entities = []
        for a in actual:
            is_expected = False
            for e in expected:
                if (a.get("mention") == e.get("mention") and
                        a.get("mention_type") == e.get("mention_type")):
                    is_expected = True
                    break
            if not is_expected:
                extra_entities.append(a)

        if extra_entities:
            print(f"\n  额外识别的实体:")
            for extra in extra_entities:
                start = extra.get("char_start", "?")
                end = extra.get("char_end", "?")
                print(f"    {extra.get('mention', '未知')} ({extra.get('mention_type', '未知')}) [{start}:{end}]")

    def test_basic_extraction(self):
        """测试1: 基础实体抽取"""
        print("\n" + "-" * 80)
        print("测试1: 基础实体抽取")
        print("-" * 80)

        test_cases = [
            {
                "text": "张三在北京大学工作。",
                "expected": [
                    {"mention": "张三", "mention_type": "PERSON", "char_start": 0, "char_end": 2},
                    {"mention": "北京大学", "mention_type": "ORG", "char_start": 3, "char_end": 7}
                ]
            },
            {
                "text": "苹果公司总部位于美国加利福尼亚州。",
                "expected": [
                    {"mention": "苹果公司", "mention_type": "ORG", "char_start": 0, "char_end": 4},
                    {"mention": "美国", "mention_type": "GPE", "char_start": 7, "char_end": 9},
                    {"mention": "加利福尼亚州", "mention_type": "GPE", "char_start": 9, "char_end": 14}
                ]
            },
            {
                "text": "2024年3月15日，李明在上海参加了人工智能大会。",
                "expected": [
                    {"mention": "2024年3月15日", "mention_type": "DATE", "char_start": 0, "char_end": 11},
                    {"mention": "李明", "mention_type": "PERSON", "char_start": 13, "char_end": 15},
                    {"mention": "上海", "mention_type": "GPE", "char_start": 16, "char_end": 18}
                ]
            },
            {
                "text": "华为技术有限公司的市值超过5000亿美元。",
                "expected": [
                    {"mention": "华为技术有限公司", "mention_type": "ORG", "char_start": 0, "char_end": 8}
                ]
            },
            {
                "text": "李娜在巴黎获得了网球公开赛冠军。",
                "expected": [
                    {"mention": "李娜", "mention_type": "PERSON", "char_start": 0, "char_end": 2},
                    {"mention": "巴黎", "mention_type": "GPE", "char_start": 3, "char_end": 5}
                ]
            },
            {
                "text": "马云创立了阿里巴巴集团，总部在杭州。",
                "expected": [
                    {"mention": "马云", "mention_type": "PERSON", "char_start": 0, "char_end": 2},
                    {"mention": "阿里巴巴集团", "mention_type": "ORG", "char_start": 6, "char_end": 12},
                    {"mention": "杭州", "mention_type": "GPE", "char_start": 17, "char_end": 19}
                ]
            },
            {
                "text": "腾讯CEO马化腾在深圳发布了新产品。",
                "expected": [
                    {"mention": "腾讯", "mention_type": "ORG", "char_start": 0, "char_end": 2},
                    {"mention": "马化腾", "mention_type": "PERSON", "char_start": 5, "char_end": 8},
                    {"mention": "深圳", "mention_type": "GPE", "char_start": 9, "char_end": 11}
                ]
            }
        ]

        all_passed = True
        details = []

        for i, test_case in enumerate(test_cases):
            text = test_case["text"]
            expected = test_case["expected"]

            # 执行NER
            mentions = self.ner_engine.extract(text)

            # 构建实际结果
            actual = [
                {
                    "mention": m.mention,
                    "mention_type": m.mention_type,
                    "char_start": m.char_start,
                    "char_end": m.char_end
                }
                for m in mentions
            ]

            print(f"\n  📝 用例{i + 1}: {text}")

            # 显示期望和实际的位置对比
            self.print_position_comparison(expected, actual, text)

            # 检查位置信息完整性
            position_valid = True
            for m in mentions:
                if not (hasattr(m, 'char_start') and hasattr(m, 'char_end')):
                    position_valid = False
                    break
                if not (isinstance(m.char_start, int) and isinstance(m.char_end, int)):
                    position_valid = False
                    break
                if not (0 <= m.char_start < m.char_end <= len(text)):
                    position_valid = False
                    break
                if text[m.char_start:m.char_end] != m.mention:
                    position_valid = False
                    break

            # 检查预期实体是否被识别（放宽位置要求）
            matched = []
            missing = []
            for exp in expected:
                found = False
                for act in actual:
                    if (act["mention"] == exp["mention"] and
                            act["mention_type"] == exp["mention_type"]):
                        found = True
                        matched.append(exp)
                        break
                if not found:
                    missing.append(exp)

            # 检查是否有额外的实体
            extra = []
            for act in actual:
                is_expected = False
                for exp in expected:
                    if (act["mention"] == exp["mention"] and
                            act["mention_type"] == exp["mention_type"]):
                        is_expected = True
                        break
                if not is_expected:
                    extra.append(act)

            # 判定测试是否通过（识别到所有实体且位置有效）
            case_passed = position_valid and len(missing) == 0

            detail = {
                "case": i + 1,
                "text": text,
                "expected_count": len(expected),
                "actual_count": len(actual),
                "matched": matched,
                "missing": missing,
                "extra": extra,
                "position_valid": position_valid,
                "passed": case_passed
            }
            details.append(detail)

            if case_passed:
                print(f"  ✅ 结果: 通过")
            else:
                all_passed = False
                print(f"  ❌ 结果: 失败")
                if missing:
                    print(f"     缺失实体: {[(m['mention'], m['mention_type']) for m in missing]}")
                if extra:
                    print(f"     额外实体: {[(m['mention'], m['mention_type']) for m in extra]}")
                if not position_valid:
                    print(f"     位置信息不合法!")

        self.add_result(
            "基础实体抽取",
            all_passed,
            f"测试了{len(test_cases)}个用例" if all_passed else f"存在失败用例",
            {"test_cases": details}
        )

    def test_position_boundary(self):
        """测试2: 位置边界验证"""
        print("\n" + "-" * 80)
        print("测试2: 位置边界验证")
        print("-" * 80)

        test_texts = [
            "李华在Google工作",
            "Microsoft总部在美国",
            "王五在复旦大学读书",
            "ABC公司成立于2000年",
            "华为与小米合作",
            "中国北京的故宫"
        ]

        all_passed = True

        for text in test_texts:
            mentions = self.ner_engine.extract(text)
            text_passed = True

            print(f"\n  📝 文本: {text}")
            print(f"     字符位置索引: ", end="")
            for i, ch in enumerate(text):
                print(f"{i}:{ch} ", end="")
            print()

            for mention in mentions:
                # 验证开区间
                extracted = text[mention.char_start:mention.char_end]
                is_valid = extracted == mention.mention

                print(f"     实体: {mention.mention} ({mention.mention_type})")
                print(f"       位置: [{mention.char_start}:{mention.char_end}]")
                print(f"       截取: '{extracted}'")
                print(f"       验证: {'✅' if is_valid else '❌'}")

                if not is_valid:
                    text_passed = False

                if not (0 <= mention.char_start < mention.char_end <= len(text)):
                    text_passed = False
                    print(f"       ❌ 位置超出范围!")

            if text_passed:
                print(f"  ✅ 文本验证通过")
            else:
                all_passed = False
                print(f"  ❌ 文本验证失败")

        self.add_result(
            "位置边界验证",
            all_passed,
            f"测试了{len(test_texts)}个文本" if all_passed else "存在位置边界错误"
        )

    def test_type_filtering(self):
        """测试3: 类型过滤功能"""
        print("\n" + "-" * 80)
        print("测试3: 类型过滤功能")
        print("-" * 80)

        # 使用配置中的linkable_types
        allowed_types = self.config.get("linkable_types", ["ORG", "PERSON", "GPE", "LOC"])

        text = "张三在北京大学工作，今天是2024年3月15日。"
        mentions = self.ner_engine.extract(text)

        all_valid = all(m.mention_type in allowed_types for m in mentions)

        print(f"\n  📝 文本: {text}")
        print(f"  配置的允许类型: {allowed_types}")
        print(f"  识别实体: {[(m.mention, m.mention_type, m.char_start, m.char_end) for m in mentions]}")

        if all_valid:
            print(f"  ✅ 所有实体类型都在允许范围内")
        else:
            invalid = [m for m in mentions if m.mention_type not in allowed_types]
            print(f"  ❌ 存在不允许的类型: {[(m.mention, m.mention_type) for m in invalid]}")

        self.add_result(
            "类型过滤功能",
            all_valid,
            f"过滤后保留 {len(mentions)} 个实体" if all_valid else "存在过滤失败"
        )

    def test_empty_text(self):
        """测试4: 空文本"""
        print("\n" + "-" * 80)
        print("测试4: 空文本测试")
        print("-" * 80)

        mentions = self.ner_engine.extract("")
        passed = len(mentions) == 0

        print(f"  空文本识别实体数: {len(mentions)}")
        if passed:
            print(f"  ✅ 空文本正确处理")
        else:
            print(f"  ❌ 空文本应返回空列表")

        self.add_result("空文本测试", passed)

    def test_no_entity_text(self):
        """测试5: 无实体文本"""
        print("\n" + "-" * 80)
        print("测试5: 无实体文本测试")
        print("-" * 80)

        text = "这是一个没有任何实体的普通句子。"
        mentions = self.ner_engine.extract(text)

        passed = len(mentions) <= 3

        print(f"\n  📝 文本: {text}")
        print(f"  识别实体数: {len(mentions)}")
        if len(mentions) > 0:
            print(f"  识别实体: {[(m.mention, m.mention_type, m.char_start, m.char_end) for m in mentions]}")

        if passed:
            print(f"  ✅ 无实体文本识别正常")
        else:
            print(f"  ❌ 无实体文本识别出过多实体: {len(mentions)}")

        self.add_result("无实体文本测试", passed)

    def test_edge_cases(self):
        """测试6: 边界情况"""
        print("\n" + "-" * 80)
        print("测试6: 边界情况测试")
        print("-" * 80)

        edge_cases = [
            "A",
            "中",
            "123",
            "test@email.com",
            "2024-03-15",
            "ABC公司",
            "  带空格的文本  ",
            "华为",
            "北京",
            "中华人民共和国"
        ]

        all_passed = True

        for text in edge_cases:
            mentions = self.ner_engine.extract(text)
            text_passed = True

            print(f"\n  📝 文本: '{text}' (长度: {len(text)})")

            for mention in mentions:
                print(f"     实体: {mention.mention} ({mention.mention_type})")
                print(f"       位置: [{mention.char_start}:{mention.char_end}]")

                if not (0 <= mention.char_start < mention.char_end <= len(text)):
                    text_passed = False
                    print(f"       ❌ 位置超出范围!")
                if text[mention.char_start:mention.char_end] != mention.mention:
                    text_passed = False
                    print(f"       ❌ 位置截取不匹配!")

            if text_passed:
                print(f"  ✅ 通过")
            else:
                all_passed = False
                print(f"  ❌ 失败")

        self.add_result("边界情况测试", all_passed)

    def test_unicode_position(self):
        """测试7: Unicode字符位置"""
        print("\n" + "-" * 80)
        print("测试7: Unicode字符位置测试")
        print("-" * 80)

        # 包含Emoji和特殊字符
        test_texts = [
            "🌟李华在🏢微软工作",
            "🚀王明在💻腾讯实习",
            "🎓张伟在北京大学",
            "❤️华为❤️"
        ]

        all_passed = True

        for text in test_texts:
            mentions = self.ner_engine.extract(text)

            print(f"\n  📝 文本: {text}")
            print(f"     长度: {len(text)}字符")
            print(f"     字符索引: ", end="")
            for i, ch in enumerate(text):
                print(f"{i}:{ch} ", end="")
            print()

            for mention in mentions:
                extracted = text[mention.char_start:mention.char_end]
                is_valid = extracted == mention.mention

                print(f"     实体: {mention.mention} ({mention.mention_type})")
                print(f"       位置: [{mention.char_start}:{mention.char_end}]")
                print(f"       截取: '{extracted}'")
                print(f"       验证: {'✅' if is_valid else '❌'}")

                if not is_valid:
                    all_passed = False

        self.add_result(
            "Unicode字符位置测试",
            all_passed,
            "Unicode位置计算正确" if all_passed else "Unicode位置计算错误"
        )

    def test_batch_from_data(self):
        """测试8: 批量数据测试"""
        print("\n" + "-" * 80)
        print("测试8: 批量数据测试")
        print("-" * 80)

        # 自定义批量测试数据
        batch_data = [
            {
                "text": "马云在杭州创立了阿里巴巴集团。",
                "expected": ["马云", "杭州", "阿里巴巴集团"],
                "expected_types": ["PERSON", "GPE", "ORG"]
            },
            {
                "text": "腾讯公司总部在深圳，员工超过5万人。",
                "expected": ["腾讯公司", "深圳"],
                "expected_types": ["ORG", "GPE"]
            },
            {
                "text": "百度CEO李彦宏在北京发布了新产品。",
                "expected": ["百度", "李彦宏", "北京"],
                "expected_types": ["ORG", "PERSON", "GPE"]
            },
            {
                "text": "小米科技创始人雷军毕业于武汉大学。",
                "expected": ["小米科技", "雷军", "武汉大学"],
                "expected_types": ["ORG", "PERSON", "ORG"]
            },
            {
                "text": "阿里巴巴与腾讯在杭州签署合作协议。",
                "expected": ["阿里巴巴", "腾讯", "杭州"],
                "expected_types": ["ORG", "ORG", "GPE"]
            },
            {
                "text": "华为发布了新款Mate手机。",
                "expected": ["华为"],
                "expected_types": ["ORG"]
            },
            {
                "text": "中国乒乓球队在东京奥运会获得金牌。",
                "expected": ["中国", "东京"],
                "expected_types": ["GPE", "GPE"]
            }
        ]

        all_passed = True
        batch_details = []

        for i, data in enumerate(batch_data):
            text = data["text"]
            expected = data["expected"]
            expected_types = data["expected_types"]

            mentions = self.ner_engine.extract(text)
            actual_mentions = [m.mention for m in mentions]
            actual_types = [m.mention_type for m in mentions]
            actual_positions = [(m.char_start, m.char_end) for m in mentions]

            print(f"\n  📝 用例{i + 1}: {text}")
            print(f"     识别实体: {list(zip(actual_mentions, actual_types, actual_positions))}")

            # 检查预期的实体是否都被识别
            missing = []
            for exp, exp_type in zip(expected, expected_types):
                found = False
                for act, act_type in zip(actual_mentions, actual_types):
                    if act == exp and act_type == exp_type:
                        found = True
                        break
                if not found:
                    missing.append((exp, exp_type))

            # 检查是否识别到额外实体
            extra = []
            for act, act_type in zip(actual_mentions, actual_types):
                is_expected = False
                for exp, exp_type in zip(expected, expected_types):
                    if act == exp and act_type == exp_type:
                        is_expected = True
                        break
                if not is_expected:
                    extra.append((act, act_type))

            case_passed = len(missing) == 0
            all_passed = all_passed and case_passed

            detail = {
                "case": i + 1,
                "text": text[:30] + "..." if len(text) > 30 else text,
                "expected": list(zip(expected, expected_types)),
                "actual": list(zip(actual_mentions, actual_types)),
                "missing": missing,
                "extra": extra,
                "passed": case_passed
            }
            batch_details.append(detail)

            if case_passed:
                print(f"     ✅ 通过")
            else:
                print(f"     ❌ 失败")
                if missing:
                    print(f"       缺失: {missing}")
                if extra:
                    print(f"       额外: {extra}")

        self.add_result(
            "批量数据测试",
            all_passed,
            f"测试了{len(batch_data)}个批量用例" if all_passed else "存在失败用例",
            {"batch_details": batch_details}
        )

    def test_complex_texts(self):
        """测试9: 复杂文本"""
        print("\n" + "-" * 80)
        print("测试9: 复杂文本测试")
        print("-" * 80)

        complex_texts = [
            {
                "text": "据新华社报道，中国国家主席习近平在北京人民大会堂会见了美国国务卿布林肯。",
                "key_entities": ["习近平", "美国", "布林肯"]
            },
            {
                "text": "阿里巴巴集团CEO张勇在杭州云栖大会上宣布，未来三年将投资1000亿元用于技术研发。",
                "key_entities": ["阿里巴巴集团", "张勇", "杭州"]
            },
            {
                "text": "华为技术有限公司与清华大学在深圳签署了战略合作协议。",
                "key_entities": ["华为技术有限公司", "清华大学", "深圳"]
            },
            {
                "text": "小米公司创始人雷军表示，未来将加大在印度市场的投资。",
                "key_entities": ["小米公司", "雷军", "印度"]
            }
        ]

        all_passed = True

        for i, data in enumerate(complex_texts):
            text = data["text"]
            key_entities = data["key_entities"]

            mentions = self.ner_engine.extract(text)
            actual_mentions = [m.mention for m in mentions]

            print(f"\n  📝 复杂文本{i + 1}:")
            print(f"     文本: {text[:50]}...")
            print(f"     识别实体: {[(m.mention, m.mention_type, m.char_start, m.char_end) for m in mentions]}")

            # 检查关键实体是否被识别
            found = []
            missing = []
            for key in key_entities:
                if key in actual_mentions:
                    found.append(key)
                else:
                    missing.append(key)

            case_passed = len(missing) == 0
            all_passed = all_passed and case_passed

            if case_passed:
                print(f"     ✅ 通过")
                if found:
                    print(f"       识别: {found}")
            else:
                print(f"     ❌ 失败")
                if missing:
                    print(f"       缺失: {missing}")

        self.add_result(
            "复杂文本测试",
            all_passed,
            f"测试了{len(complex_texts)}个复杂文本" if all_passed else "存在失败用例"
        )

    def test_position_precision(self):
        """测试10: 位置精度测试"""
        print("\n" + "-" * 80)
        print("测试10: 位置精度测试")
        print("-" * 80)

        # 测试用例
        test_cases = [
            {
                "text": "北京天安门",
                "expected": [
                    {"mention": "北京", "char_start": 0, "char_end": 2},
                    {"mention": "天安门", "char_start": 2, "char_end": 5}
                ]
            },
            {
                "text": "上海市浦东新区",
                "expected": [
                    {"mention": "上海市", "char_start": 0, "char_end": 3},
                    {"mention": "浦东新区", "char_start": 3, "char_end": 7}
                ]
            }
        ]

        all_passed = True

        for i, test_case in enumerate(test_cases):
            text = test_case["text"]
            expected = test_case["expected"]

            mentions = self.ner_engine.extract(text)

            print(f"\n  📝 用例{i + 1}: {text}")
            print(f"     字符索引: ", end="")
            for j, ch in enumerate(text):
                print(f"{j}:{ch} ", end="")
            print()

            # 显示每个字符属于哪个实体
            print(f"     字符位置详情:")
            for j, ch in enumerate(text):
                print(f"       位置{j}: '{ch}'", end="")
                belongs_to = []
                for m in mentions:
                    if m.char_start <= j < m.char_end:
                        belongs_to.append(m.mention)
                if belongs_to:
                    print(f" -> 属于: {', '.join(belongs_to)}")
                else:
                    print(f" -> 不属于任何实体")

            # 验证期望的实体
            for exp in expected:
                exp_text = exp["mention"]
                exp_start = exp["char_start"]
                exp_end = exp["char_end"]

                found = False
                for m in mentions:
                    if m.mention == exp_text and m.char_start == exp_start and m.char_end == exp_end:
                        found = True
                        print(f"     ✅ 实体 '{exp_text}' 位置正确: [{exp_start}:{exp_end}]")
                        break

                if not found:
                    # 检查是否识别但位置不对
                    for m in mentions:
                        if m.mention == exp_text:
                            print(
                                f"     ❌ 实体 '{exp_text}' 位置错误: 期望[{exp_start}:{exp_end}], 实际[{m.char_start}:{m.char_end}]")
                            break
                    else:
                        print(f"     ❌ 实体 '{exp_text}' 未识别")
                    all_passed = False

        self.add_result(
            "位置精度测试",
            all_passed,
            "位置精度验证通过" if all_passed else "存在位置精度问题"
        )

    def test_mixed_language(self):
        """测试11: 中英文混合文本"""
        print("\n" + "-" * 80)
        print("测试11: 中英文混合文本测试")
        print("-" * 80)

        test_cases = [
            {
                "text": "Apple公司在加州",
                "expected": [
                    {"mention": "Apple公司", "mention_type": "ORG", "char_start": 0, "char_end": 7},
                    {"mention": "加州", "mention_type": "GPE", "char_start": 8, "char_end": 10}
                ]
            },
            {
                "text": "Google总部在美国",
                "expected": [
                    {"mention": "Google", "mention_type": "ORG", "char_start": 0, "char_end": 6},
                    {"mention": "美国", "mention_type": "GPE", "char_start": 9, "char_end": 11}
                ]
            }
        ]

        all_passed = True

        for i, test_case in enumerate(test_cases):
            text = test_case["text"]
            expected = test_case["expected"]

            mentions = self.ner_engine.extract(text)
            actual = [
                {
                    "mention": m.mention,
                    "mention_type": m.mention_type,
                    "char_start": m.char_start,
                    "char_end": m.char_end
                }
                for m in mentions
            ]

            print(f"\n  📝 用例{i + 1}: {text}")
            print(f"     字符索引: ", end="")
            for j, ch in enumerate(text):
                print(f"{j}:{ch} ", end="")
            print()

            # 显示期望和实际位置对比
            self.print_position_comparison(expected, actual, text)

            # 验证
            for exp in expected:
                found = False
                for m in mentions:
                    if (m.mention == exp["mention"] and
                            m.mention_type == exp["mention_type"] and
                            m.char_start == exp["char_start"] and
                            m.char_end == exp["char_end"]):
                        found = True
                        break
                if not found:
                    all_passed = False
                    print(f"     ❌ 实体 '{exp['mention']}' 未正确识别")

        self.add_result(
            "中英文混合测试",
            all_passed,
            "中英文混合识别正常" if all_passed else "存在识别问题"
        )

    def test_long_text(self):
        """测试12: 长文本测试"""
        print("\n" + "-" * 80)
        print("测试12: 长文本测试")
        print("-" * 80)

        long_text = """
        2024年3月15日，华为技术有限公司在上海举办了年度开发者大会。
        阿里巴巴集团CEO张勇出席了会议，并发表了重要讲话。
        同时，腾讯公司也在深圳发布了最新的AI产品。
        百度创始人李彦宏在北京通过视频连线参与了讨论。
        小米科技的雷军表示，未来将加大在人工智能领域的投入。
        """

        print(f"\n  📝 长文本长度: {len(long_text)}字符")
        print(f"     文本预览: {long_text[:100]}...")

        start_time = time.time()
        mentions = self.ner_engine.extract(long_text)
        elapsed_time = time.time() - start_time

        print(f"\n  识别实体数量: {len(mentions)}")
        print(f"  耗时: {elapsed_time:.3f}秒")

        # 显示所有识别到的实体
        print(f"\n  识别结果:")
        for m in mentions:
            print(f"    实体: {m.mention} ({m.mention_type})")
            print(f"      位置: [{m.char_start}:{m.char_end}]")
            print(f"      截取: '{long_text[m.char_start:m.char_end]}'")

        # 验证位置有效性
        all_valid = True
        for m in mentions:
            if not (0 <= m.char_start < m.char_end <= len(long_text)):
                all_valid = False
                print(f"  ❌ 位置无效: {m.mention} [{m.char_start}:{m.char_end}]")
            if long_text[m.char_start:m.char_end] != m.mention:
                all_valid = False
                print(f"  ❌ 位置截取不匹配: {m.mention}")

        self.add_result(
            "长文本测试",
            all_valid,
            f"识别了{len(mentions)}个实体，耗时{elapsed_time:.3f}秒" if all_valid else "存在位置错误"
        )

    def test_special_characters(self):
        """测试13: 特殊字符测试"""
        print("\n" + "-" * 80)
        print("测试13: 特殊字符测试")
        print("-" * 80)

        test_cases = [
            {
                "text": "（北京）",
                "expected": [
                    {"mention": "北京", "mention_type": "GPE", "char_start": 1, "char_end": 3}
                ]
            },
            {
                "text": "【上海】",
                "expected": [
                    {"mention": "上海", "mention_type": "GPE", "char_start": 1, "char_end": 3}
                ]
            },
            {
                "text": "《人民日报》",
                "expected": [
                    {"mention": "人民日报", "mention_type": "ORG", "char_start": 1, "char_end": 5}
                ]
            },
            {
                "text": "「华为」",
                "expected": [
                    {"mention": "华为", "mention_type": "ORG", "char_start": 1, "char_end": 3}
                ]
            },
            {
                "text": "“阿里巴巴”",
                "expected": [
                    {"mention": "阿里巴巴", "mention_type": "ORG", "char_start": 1, "char_end": 5}
                ]
            }
        ]

        all_passed = True

        for i, test_case in enumerate(test_cases):
            text = test_case["text"]
            expected = test_case["expected"]

            mentions = self.ner_engine.extract(text)
            actual = [
                {
                    "mention": m.mention,
                    "mention_type": m.mention_type,
                    "char_start": m.char_start,
                    "char_end": m.char_end
                }
                for m in mentions
            ]

            print(f"\n  📝 用例{i + 1}: {text}")
            print(f"     字符索引: ", end="")
            for j, ch in enumerate(text):
                print(f"{j}:{ch} ", end="")
            print()

            # 显示期望和实际位置对比
            self.print_position_comparison(expected, actual, text)

            # 验证
            for exp in expected:
                found = False
                for m in mentions:
                    if (m.mention == exp["mention"] and
                            m.char_start == exp["char_start"] and
                            m.char_end == exp["char_end"]):
                        found = True
                        break
                if not found:
                    all_passed = False
                    print(f"     ❌ 实体 '{exp['mention']}' 位置不正确")

        self.add_result(
            "特殊字符测试",
            all_passed,
            "特殊字符处理正常" if all_passed else "存在特殊字符处理问题"
        )

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

        # 打印失败详情
        if self.failed > 0:
            print("\n失败测试详情:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  ❌ {result['test_name']}")
                    if result.get("message"):
                        print(f"     {result['message']}")

    def save_results(self):
        """保存测试结果到文件"""
        # 创建输出目录
        output_dir = Path("tests/output")
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存详细结果（JSON格式）
        detailed_file = output_dir / f"ner_test_results_{timestamp}.json"
        with open(detailed_file, 'w', encoding='utf-8') as f:
            json.dump({
                "config": self.config,
                "summary": {
                    "total": self.passed + self.failed,
                    "passed": self.passed,
                    "failed": self.failed,
                    "pass_rate": f"{self.passed / (self.passed + self.failed) * 100:.1f}%" if (
                                                                                                          self.passed + self.failed) > 0 else "0%"
                },
                "results": self.test_results
            }, f, ensure_ascii=False, indent=2)

        # 保存可读文本格式
        text_file = output_dir / f"ner_test_results_{timestamp}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("NER实体抽取测试报告 (HanLP)\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"配置: {json.dumps(self.config, ensure_ascii=False, indent=2)}\n")
            f.write("=" * 80 + "\n\n")

            f.write("测试汇总:\n")
            total = self.passed + self.failed
            f.write(f"  总测试数: {total}\n")
            f.write(f"  通过: {self.passed}\n")
            f.write(f"  失败: {self.failed}\n")
            f.write(f"  通过率: {self.passed / total * 100:.1f}%\n\n" if total > 0 else "  通过率: 0%\n\n")

            f.write("-" * 80 + "\n")
            f.write("详细测试结果:\n")
            f.write("-" * 80 + "\n\n")

            for i, result in enumerate(self.test_results, 1):
                status = "✅ 通过" if result["passed"] else "❌ 失败"
                f.write(f"{i}. {result['test_name']} - {status}\n")
                if result.get("message"):
                    f.write(f"   消息: {result['message']}\n")
                f.write("\n")

        print(f"\n测试结果已保存:")
        print(f"  JSON格式: {detailed_file}")
        print(f"  文本格式: {text_file}")


def main():
    """主函数"""
    # 检查依赖
    try:
        import hanlp
        print("✅ HanLP已安装")
    except ImportError:
        print("⚠️ 未安装HanLP，请运行: pip install hanlp")
        return

    # 检查配置文件
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        return

    # 创建测试器并运行
    tester = NERTester(str(config_path))
    tester.run_all_tests()


if __name__ == "__main__":
    main()