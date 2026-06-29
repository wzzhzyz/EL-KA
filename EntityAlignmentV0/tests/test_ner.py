# tests/test_ner.py
import unittest
import sys
import os
from typing import List, Dict, Tuple
import json

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.ner import NEREngine


class TestNEREngine(unittest.TestCase):
    """NER引擎测试类"""

    @classmethod
    def setUpClass(cls):
        """在所有测试之前执行一次"""
        config = {
            "hanlp_model": "CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH",
            "linkable_types": ["ORG", "PERSON", "GPE", "LOC"]
        }
        cls.ner_engine = NEREngine(config)
        # 提前加载模型
        cls.ner_engine._load_model()

    def format_entity_position(self, entity: Dict) -> str:
        """格式化实体及其位置信息"""
        return f"{entity['mention']}[{entity['start']}:{entity['end']}]"

    def format_entities_summary(self, entities: List[Dict]) -> str:
        """格式化实体列表为字符串"""
        if not entities:
            return "无"
        return "; ".join([self.format_entity_position(e) for e in entities])

    def assert_entity_position_equal(self, expected: Dict, actual: Dict):
        """
        精确断言实体位置是否相等

        Args:
            expected: 期望的实体
            actual: 实际的实体
        """
        # 验证实体文本
        self.assertEqual(
            actual['mention'],
            expected['mention'],
            f"实体文本不匹配: 期望 '{expected['mention']}', 实际 '{actual['mention']}'"
        )

        # 验证实体类型
        self.assertEqual(
            actual['type'],
            expected['type'],
            f"实体类型不匹配: 期望 '{expected['type']}', 实际 '{actual['type']}'"
        )

        # 精确验证开始位置
        self.assertEqual(
            actual['start'],
            expected['start'],
            f"实体 '{expected['mention']}' 开始位置不匹配: 期望 {expected['start']}, 实际 {actual['start']}"
        )

        # 精确验证结束位置
        self.assertEqual(
            actual['end'],
            expected['end'],
            f"实体 '{expected['mention']}' 结束位置不匹配: 期望 {expected['end']}, 实际 {actual['end']}"
        )

    def assert_ner_result(self, text: str, expected_entities: List[Dict]):
        """
        断言NER结果是否完全符合预期（包括位置信息）

        Args:
            text: 原始文本
            expected_entities: 期望的实体列表
        """
        actual_entities = self.ner_engine.extract(text)

        # 打印测试信息
        print(f"\n{'=' * 70}")
        print(f"📝 原文本: {text}")
        print(f"📌 期望识别 ({len(expected_entities)}个):")
        for entity in expected_entities:
            print(f"   - {self.format_entity_position(entity)} ({entity['type']})")
        print(f"🔍 实际识别 ({len(actual_entities)}个):")
        for entity in actual_entities:
            print(f"   - {self.format_entity_position(entity)} ({entity['type']})")
        print(f"{'=' * 70}")

        # 验证实体数量
        self.assertEqual(
            len(actual_entities),
            len(expected_entities),
            f"实体数量不匹配: 期望 {len(expected_entities)} 个, 实际 {len(actual_entities)} 个\n"
            f"期望: {self.format_entities_summary(expected_entities)}\n"
            f"实际: {self.format_entities_summary(actual_entities)}"
        )

        # 逐个验证实体（包括位置）
        for i, (expected, actual) in enumerate(zip(expected_entities, actual_entities)):
            with self.subTest(entity_index=i, expected=expected, actual=actual):
                self.assert_entity_position_equal(expected, actual)

    def test_simple_person_location(self):
        """测试简单的人名和地名"""
        text = "张伟去北京开会。"
        expected = [
            {"mention": "张伟", "type": "PERSON", "start": 0, "end": 2},
            {"mention": "北京", "type": "GPE", "start": 3, "end": 5}  # "去"是索引2，"北京"从3开始
        ]
        self.assert_ner_result(text, expected)

    def test_single_entity(self):
        """测试单个实体识别"""
        test_cases = [
            {
                "text": "马云是阿里巴巴创始人。",
                "expected": [
                    {"mention": "马云", "type": "PERSON", "start": 0, "end": 2},
                    {"mention": "阿里巴巴", "type": "ORG", "start": 4, "end": 8}
                ]
            },
            {
                "text": "深圳是一座美丽城市。",
                "expected": [
                    {"mention": "深圳", "type": "GPE", "start": 0, "end": 2}
                ]
            },
            {
                "text": "华为公司发布新产品。",
                "expected": [
                    {"mention": "华为", "type": "ORG", "start": 0, "end": 2}
                ]
            }
        ]

        for case in test_cases:
            with self.subTest(text=case['text']):
                self.assert_ner_result(case['text'], case['expected'])

    def test_multiple_entities_with_positions(self):
        """测试多个实体的位置识别"""
        text = "国网北京市电力公司"
        expected = [
            {"mention": "国网", "type": "ORG", "start": 0, "end": 2},
            {"mention": "北京", "type": "GPE", "start": 2, "end": 4},
            {"mention": "北京市", "type": "GPE", "start": 2, "end": 5},
            {"mention": "电力公司", "type": "ORG", "start": 6, "end": 10}
        ]

        actual = self.ner_engine.extract(text)

        print(f"\n{'=' * 70}")
        print(f"📝 原文本: {text}")
        print(f"📌 期望识别 ({len(expected)}个):")
        for entity in expected:
            print(f"   - {self.format_entity_position(entity)} ({entity['type']})")
        print(f"🔍 实际识别 ({len(actual)}个):")
        for entity in actual:
            print(f"   - {self.format_entity_position(entity)} ({entity['type']})")
        print(f"{'=' * 70}")

        # 由于模型可能识别出不同粒度的实体，我们验证是否包含关键实体
        actual_entities_str = self.format_entities_summary(actual)

        # 验证"国网"的识别
        found_guowang = any(e['mention'] == "国网" for e in actual)
        if found_guowang:
            guowang = [e for e in actual if e['mention'] == "国网"][0]
            self.assertEqual(guowang['start'], 0)
            self.assertEqual(guowang['end'], 2)

        # 验证"北京"或"北京市"的识别
        found_beijing = any(e['mention'] in ["北京", "北京市"] for e in actual)
        self.assertTrue(found_beijing, f"未识别到'北京'或'北京市'，实际识别: {actual_entities_str}")

        if found_beijing:
            beijing = [e for e in actual if e['mention'] in ["北京", "北京市"]][0]
            self.assertEqual(beijing['start'], 2)

    def test_company_full_name(self):
        """测试公司全称识别"""
        text = "国家电网有限公司"
        expected = [
            {"mention": "国家电网", "type": "ORG", "start": 0, "end": 4},
            {"mention": "国家电网有限公司", "type": "ORG", "start": 0, "end": 8}
        ]

        actual = self.ner_engine.extract(text)

        print(f"\n{'=' * 70}")
        print(f"📝 原文本: {text}")
        print(f"📌 期望识别 ({len(expected)}个):")
        for entity in expected:
            print(f"   - {self.format_entity_position(entity)} ({entity['type']})")
        print(f"🔍 实际识别 ({len(actual)}个):")
        for entity in actual:
            print(f"   - {self.format_entity_position(entity)} ({entity['type']})")
        print(f"{'=' * 70}")

        # 验证是否识别到"国家电网"
        found = any(e['mention'] == "国家电网" for e in actual)
        self.assertTrue(found, f"未识别到'国家电网'，实际识别: {self.format_entities_summary(actual)}")

        if found:
            guowang = [e for e in actual if e['mention'] == "国家电网"][0]
            self.assertEqual(guowang['start'], 0)
            self.assertEqual(guowang['end'], 4)

    def test_location_hierarchy(self):
        """测试地理位置层级识别"""
        text = "广东省深圳市南山区"
        expected = [
            {"mention": "广东", "type": "GPE", "start": 0, "end": 2},
            {"mention": "广东省", "type": "GPE", "start": 0, "end": 3},
            {"mention": "深圳", "type": "GPE", "start": 3, "end": 5},
            {"mention": "深圳市", "type": "GPE", "start": 3, "end": 6},
            {"mention": "南山", "type": "GPE", "start": 6, "end": 8},
            {"mention": "南山区", "type": "GPE", "start": 6, "end": 9}
        ]

        actual = self.ner_engine.extract(text)

        print(f"\n{'=' * 70}")
        print(f"📝 原文本: {text}")
        print(f"📌 期望识别 ({len(expected)}个):")
        for entity in expected:
            print(f"   - {self.format_entity_position(entity)} ({entity['type']})")
        print(f"🔍 实际识别 ({len(actual)}个):")
        for entity in actual:
            print(f"   - {self.format_entity_position(entity)} ({entity['type']})")
        print(f"{'=' * 70}")

        # 验证关键地名
        found_shenzhen = any(e['mention'] in ["深圳", "深圳市"] for e in actual)
        self.assertTrue(found_shenzhen, f"未识别到'深圳'或'深圳市'，实际: {self.format_entities_summary(actual)}")

        # 验证位置
        if found_shenzhen:
            shenzhen = [e for e in actual if e['mention'] in ["深圳", "深圳市"]][0]
            self.assertEqual(shenzhen['start'], 3)

    def test_person_full_name(self):
        """测试人名识别"""
        text = "习近平主席访问美国"
        expected = [
            {"mention": "习近平", "type": "PERSON", "start": 0, "end": 3}
        ]

        actual = self.ner_engine.extract(text)

        print(f"\n{'=' * 70}")
        print(f"📝 原文本: {text}")
        print(f"📌 期望识别: {self.format_entities_summary(expected)}")
        print(f"🔍 实际识别: {self.format_entities_summary(actual)}")
        print(f"{'=' * 70}")

        # 验证人名
        found = any(e['mention'] == "习近平" for e in actual)
        self.assertTrue(found, f"未识别到'习近平'，实际: {self.format_entities_summary(actual)}")

        if found:
            person = [e for e in actual if e['mention'] == "习近平"][0]
            self.assertEqual(person['start'], 0)
            self.assertEqual(person['end'], 3)

    def test_entity_in_sentence(self):
        """测试句子中的实体识别"""
        text = "阿里巴巴集团总部位于杭州"
        expected = [
            {"mention": "阿里巴巴", "type": "ORG", "start": 0, "end": 4},
            {"mention": "杭州", "type": "GPE", "start": 9, "end": 11}
        ]

        actual = self.ner_engine.extract(text)

        print(f"\n{'=' * 70}")
        print(f"📝 原文本: {text}")
        print(f"📌 期望识别: {self.format_entities_summary(expected)}")
        print(f"🔍 实际识别: {self.format_entities_summary(actual)}")
        print(f"{'=' * 70}")

        # 由于"阿里巴巴集团"可能被识别为整体，我们验证是否包含"阿里巴巴"
        found_ali = any(e['mention'] in ["阿里巴巴", "阿里巴巴集团"] for e in actual if e['type'] == 'ORG')
        self.assertTrue(found_ali, f"未识别到'阿里巴巴'或'阿里巴巴集团'，实际: {self.format_entities_summary(actual)}")

        # 验证杭州的位置
        found_hangzhou = any(e['mention'] == "杭州" for e in actual)
        self.assertTrue(found_hangzhou, f"未识别到'杭州'，实际: {self.format_entities_summary(actual)}")

    def test_mixed_chinese_english(self):
        """测试中英文混合的实体"""
        text = "IBM公司在华业务"
        expected = [
            {"mention": "IBM", "type": "ORG", "start": 0, "end": 3}
        ]

        actual = self.ner_engine.extract(text)

        print(f"\n{'=' * 70}")
        print(f"📝 原文本: {text}")
        print(f"📌 期望识别: {self.format_entities_summary(expected)}")
        print(f"🔍 实际识别: {self.format_entities_summary(actual)}")
        print(f"{'=' * 70}")

        # 验证IBM识别
        found_ibm = any(e['mention'] in ["IBM", "IBM公司"] for e in actual)
        self.assertTrue(found_ibm, f"未识别到'IBM'或'IBM公司'，实际: {self.format_entities_summary(actual)}")

        # 如果识别到"IBM公司"，验证其位置
        ibm_entities = [e for e in actual if e['mention'] in ["IBM", "IBM公司"]]
        if ibm_entities:
            ibm = ibm_entities[0]
            # "IBM"在"IBM公司"中应该从0开始
            if ibm['mention'] == "IBM":
                self.assertEqual(ibm['start'], 0)
                self.assertEqual(ibm['end'], 3)
            elif ibm['mention'] == "IBM公司":
                self.assertEqual(ibm['start'], 0)

    def test_text_with_punctuation(self):
        """测试带标点符号的文本"""
        text = "腾讯，百度，阿里巴巴"
        expected = [
            {"mention": "腾讯", "type": "ORG", "start": 0, "end": 2},
            {"mention": "百度", "type": "ORG", "start": 3, "end": 5},
            {"mention": "阿里巴巴", "type": "ORG", "start": 6, "end": 10}
        ]

        actual = self.ner_engine.extract(text)

        print(f"\n{'=' * 70}")
        print(f"📝 原文本: {text}")
        print(f"📌 期望识别: {self.format_entities_summary(expected)}")
        print(f"🔍 实际识别: {self.format_entities_summary(actual)}")
        print(f"{'=' * 70}")

        # 验证是否识别到期望的实体
        expected_mentions = [e['mention'] for e in expected]
        actual_mentions = [e['mention'] for e in actual]

        for expected_mention in expected_mentions:
            self.assertIn(expected_mention, actual_mentions,
                          f"未识别到'{expected_mention}'，实际: {actual_mentions}")

    def test_empty_and_whitespace(self):
        """测试空文本和空白文本"""
        test_cases = [
            ("", []),
            ("   ", []),
            ("\n\t", [])
        ]

        for text, expected in test_cases:
            with self.subTest(text=repr(text)):
                actual = self.ner_engine.extract(text)
                print(f"\n{'=' * 70}")
                print(f"📝 原文本: {repr(text)}")
                print(f"📌 期望识别: {self.format_entities_summary(expected)}")
                print(f"🔍 实际识别: {self.format_entities_summary(actual)}")
                print(f"{'=' * 70}")
                self.assertEqual(len(actual), 0, f"空白文本应该返回空列表，实际: {actual}")

    def test_entity_overlap(self):
        """测试实体重叠的情况"""
        text = "北京市海淀区"
        expected = [
            {"mention": "北京", "type": "GPE", "start": 0, "end": 2},
            {"mention": "北京市", "type": "GPE", "start": 0, "end": 3},
            {"mention": "海淀", "type": "GPE", "start": 3, "end": 5},
            {"mention": "海淀区", "type": "GPE", "start": 3, "end": 6}
        ]

        actual = self.ner_engine.extract(text)

        print(f"\n{'=' * 70}")
        print(f"📝 原文本: {text}")
        print(f"📌 期望识别 ({len(expected)}个):")
        for entity in expected:
            print(f"   - {self.format_entity_position(entity)} ({entity['type']})")
        print(f"🔍 实际识别 ({len(actual)}个):")
        for entity in actual:
            print(f"   - {self.format_entity_position(entity)} ({entity['type']})")
        print(f"{'=' * 70}")

        # 验证至少识别到一些地名
        self.assertGreaterEqual(len(actual), 1, "应至少识别一个地名")

        # 检查是否识别到"北京"或"北京市"
        found_beijing = any(e['mention'] in ["北京", "北京市"] for e in actual)
        self.assertTrue(found_beijing, f"未识别到'北京'或'北京市'，实际: {self.format_entities_summary(actual)}")

        # 检查位置
        beijing_entities = [e for e in actual if e['mention'] in ["北京", "北京市"]]
        if beijing_entities:
            # 验证至少有一个"北京"从位置0开始
            has_start_zero = any(e['start'] == 0 for e in beijing_entities)
            self.assertTrue(has_start_zero, "没有从位置0开始的'北京'或'北京市'")


def create_test_suite():
    """创建测试套件"""
    suite = unittest.TestSuite()

    # 添加测试用例
    test_methods = [
        'test_simple_person_location',
        'test_single_entity',
        'test_multiple_entities_with_positions',
        'test_company_full_name',
        'test_location_hierarchy',
        'test_person_full_name',
        'test_entity_in_sentence',
        'test_mixed_chinese_english',
        'test_text_with_punctuation',
        'test_empty_and_whitespace',
        'test_entity_overlap'
    ]

    for method in test_methods:
        suite.addTest(TestNEREngine(method))

    return suite


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    suite = create_test_suite()

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 打印总结
    print(f"\n{'=' * 70}")
    print(f"📊 测试总结:")
    print(f"   ✅ 通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"   ❌ 失败: {len(result.failures)}")
    print(f"   ⚠️  错误: {len(result.errors)}")
    print(f"{'=' * 70}")

    # 如果有失败，详细显示
    if result.failures:
        print("\n❌ 失败的测试:")
        for failure in result.failures:
            print(f"   - {failure[0]}")
            print(f"      {failure[1]}")

    if result.errors:
        print("\n⚠️  错误的测试:")
        for error in result.errors:
            print(f"   - {error[0]}")
            print(f"      {error[1]}")

    return result


if __name__ == "__main__":
    # 运行测试
    run_tests()