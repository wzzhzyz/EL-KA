# tests/test_llm_switch.py
"""
LLM 消歧开关模式切换测试脚本

测试内容：
1. LLM 关闭模式：纯 BGE/Reranker 消歧
2. LLM 开启模式：BGE/Reranker + LLM 兜底
3. 对比两种模式的效果差异
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.linker import EntityLinker
from src.models.mention import StandardMention
from src.utils.config import load_config
from src.utils.logger import logger


class LLMSwitchTester:
    """LLM 开关模式切换测试器"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"

        self.config = load_config(str(config_path))
        self.results = {"llm_off": [], "llm_on": []}

        print("\n" + "=" * 80)
        print("LLM 消歧开关模式切换测试")
        print("=" * 80)
        print(f"配置: {config_path}")
        print("=" * 80)

    def load_test_data(self, texts_path: str, ground_truth_path: str) -> List[Dict]:
        """加载测试数据"""
        with open(texts_path, "r", encoding="utf-8") as f:
            texts = [line.strip() for line in f.readlines() if line.strip()]

        with open(ground_truth_path, "r", encoding="utf-8") as f:
            gt_data = json.load(f)

        test_cases = []
        for entry in gt_data.get("entries", []):
            text_idx = entry.get("text_idx", -1)
            for exp in entry.get("expected_entities", []):
                mention = exp.get("mention", "")
                entity_id = exp.get("entity_id")
                test_cases.append({
                    "text_idx": text_idx,
                    "text": texts[text_idx] if text_idx < len(texts) else "",
                    "mention": mention,
                    "expected_entity_id": entity_id,
                    "scenario": entry.get("scenario", "")
                })

        print(f"📋 加载测试用例: {len(test_cases)} 个")
        return test_cases

    def run_test(self, test_cases: List[Dict], enable_llm: bool) -> Dict:
        """运行测试（指定 LLM 开关状态）"""
        mode = "LLM开启" if enable_llm else "LLM关闭"
        print(f"\n{'='*60}")
        print(f"测试模式: {mode}")
        print(f"{'='*60}")

        # 动态修改配置
        self.config["llm_fallback"]["enabled"] = enable_llm
        linker = EntityLinker(self.config)

        if enable_llm:
            linker.disambiguator.enable_llm()
        else:
            linker.disambiguator.disable_llm()

        print(f"  LLM状态: {'已启用' if linker.disambiguator.is_llm_enabled() else '已禁用'}")

        results = []
        passed = 0
        failed = 0

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n  [{i}/{len(test_cases)}] {test_case['scenario']}")
            print(f"    Mention: '{test_case['mention']}'")

            # 构建 StandardMention
            mention_obj = StandardMention(
                mention=test_case["mention"],
                mention_type="UNKNOWN",
                char_start=0,
                char_end=len(test_case["mention"]),
                metadata={"context": test_case["text"]}
            )

            # 执行链接
            output = linker.link_with_mentions(
                test_case["text"],
                [mention_obj.to_dict()],
                {"nil_threshold": linker.disambiguator.nil_threshold}
            )

            # 提取结果
            result = output.get("results", [])[0] if output.get("results") else {}
            actual_id = result.get("entity_id")
            actual_name = result.get("standard_entity")
            confidence = result.get("confidence", 0.0)
            method = result.get("method", "")
            evidence = result.get("evidence", "")
            is_nil = result.get("is_nil", True)

            expected_id = test_case["expected_entity_id"]
            correct = (expected_id is None and is_nil) or (expected_id == actual_id)

            if correct:
                passed += 1
                status = "✅ PASS"
            else:
                failed += 1
                status = "❌ FAIL"

            print(f"    {status} → {actual_name or 'NIL'} (置信度: {confidence:.3f}, 方法: {method})")

            results.append({
                "test_case": test_case,
                "actual_id": actual_id,
                "actual_name": actual_name,
                "confidence": confidence,
                "method": method,
                "evidence": evidence,
                "correct": correct
            })

        print(f"\n  统计: 通过 {passed}/{len(test_cases)} ({passed/len(test_cases)*100:.1f}%)")

        return {
            "mode": mode,
            "llm_enabled": enable_llm,
            "total": len(test_cases),
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / len(test_cases) * 100 if test_cases else 0,
            "results": results
        }

    def run_all(self, texts_path: str = None, ground_truth_path: str = None):
        """运行所有测试"""
        if texts_path is None:
            texts_path = Path(__file__).parent.parent / "data" / "batch_texts.txt"
        if ground_truth_path is None:
            ground_truth_path = Path(__file__).parent.parent / "data" / "batch_ground_truth.json"

        test_cases = self.load_test_data(str(texts_path), str(ground_truth_path))

        # 过滤出非 NIL 用例（用于测试消歧效果）
        non_nil_cases = [tc for tc in test_cases if tc["expected_entity_id"] is not None]

        # 测试 LLM 关闭
        result_off = self.run_test(non_nil_cases, enable_llm=False)
        self.results["llm_off"] = result_off

        # 测试 LLM 开启
        result_on = self.run_test(non_nil_cases, enable_llm=True)
        self.results["llm_on"] = result_on

        self.print_comparison()
        self.save_results()

    def print_comparison(self):
        """打印对比结果"""
        print("\n" + "=" * 80)
        print("📊 LLM 开关效果对比")
        print("=" * 80)

        off = self.results["llm_off"]
        on = self.results["llm_on"]

        print(f"\n  指标              LLM关闭          LLM开启")
        print(f"  {'-'*50}")
        print(f"  通过数            {off['passed']}/{off['total']}         {on['passed']}/{on['total']}")
        print(f"  通过率            {off['pass_rate']:.1f}%            {on['pass_rate']:.1f}%")
        print(f"  提升              -                {on['pass_rate'] - off['pass_rate']:+.1f}%")

        # 统计LLM介入次数
        llm_used = sum(1 for r in on["results"] if r["method"] and "llm" in r["method"].lower())
        print(f"  LLM介入次数       -                {llm_used}")

        # 打印LLM改善的用例
        improved = []
        for i, (r_off, r_on) in enumerate(zip(off["results"], on["results"])):
            if not r_off["correct"] and r_on["correct"]:
                improved.append(i)

        if improved:
            print(f"\n✅ LLM 改善的用例 ({len(improved)} 个):")
            for idx in improved[:10]:
                case = off["results"][idx]["test_case"]
                print(f"    - {case['mention']} ({case['scenario']})")
        else:
            print(f"\n⚠️ LLM 没有改善任何用例")

        # 打印LLM退化的用例
        degraded = []
        for i, (r_off, r_on) in enumerate(zip(off["results"], on["results"])):
            if r_off["correct"] and not r_on["correct"]:
                degraded.append(i)

        if degraded:
            print(f"\n❌ LLM 导致退化的用例 ({len(degraded)} 个):")
            for idx in degraded[:10]:
                case = off["results"][idx]["test_case"]
                print(f"    - {case['mention']} ({case['scenario']})")

    def save_results(self):
        """保存测试结果"""
        output_dir = Path("tests/output")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 转换结果
        results_data = {
            "timestamp": datetime.now().isoformat(),
            "llm_off": {
                "mode": self.results["llm_off"]["mode"],
                "pass_rate": self.results["llm_off"]["pass_rate"],
                "details": self.results["llm_off"]["results"]
            },
            "llm_on": {
                "mode": self.results["llm_on"]["mode"],
                "pass_rate": self.results["llm_on"]["pass_rate"],
                "details": self.results["llm_on"]["results"]
            }
        }

        file_path = output_dir / f"llm_switch_test_{timestamp}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)

        print(f"\n📄 测试结果已保存: {file_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="LLM 消歧开关模式切换测试")
    parser.add_argument("--texts", type=str, help="测试文本文件路径", default="../data/batch_texts.txt")
    parser.add_argument("--gt", type=str, help="标准答案文件路径", default="../data/batch_ground_truth.json")
    args = parser.parse_args()

    tester = LLMSwitchTester()
    tester.run_all(args.texts, args.gt)


if __name__ == "__main__":
    main()