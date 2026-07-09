# tests/quick_ner.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.ner import NEREngine
from src.utils.config import load_config


def main():
    config = load_config()
    ner = NEREngine(config["ner"])

    texts = [
        "国家电网有限公司在华北地区新建了输电线路。",
        "国网在华北新建了线路。",
        "中石油2025年净利润增长5%。",
        "宁德时代新能源科技股份有限公司在华南地区有布局。",
        "国家电网有限公司2025年营收增长5%。它在华北地区新建了输电线路。",
    ]

    print("=" * 70)
    print("快速 NER 测试（含位置验证）")
    print("=" * 70)

    all_passed = True

    for i, text in enumerate(texts, 1):
        print(f"\n[{i}] 📝 {text}")
        print(f"    长度: {len(text)} 字符")

        mentions = ner.extract(text)

        if not mentions:
            print("    ⚠️ 未识别到实体")
            continue

        for m in mentions:
            extracted = text[m.char_start:m.char_end]
            match = "✅" if extracted == m.mention else "❌"
            print(f"    [{m.char_start}:{m.char_end}] '{m.mention}' ({m.mention_type})")
            print(f"       提取: '{extracted}' {match}")

            if extracted != m.mention:
                all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ 所有文本的位置验证通过")
    else:
        print("❌ 存在位置提取不匹配的问题")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())