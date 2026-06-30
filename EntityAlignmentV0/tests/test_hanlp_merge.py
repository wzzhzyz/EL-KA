# tests/test_ner_merge.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ner.adapters.hanlp_adapter import HanLPAdapter


def main():
    print("=" * 70)
    print("🔬 测试 NER 合并去重效果")
    print("=" * 70)

    adapter = HanLPAdapter()

    # 测试各种场景
    test_texts = [
        "小米公司创始人雷军表示，未来将加大在印度市场的投资。",
        "国家电网有限公司在华北地区新建了输电线路。",
        "中石油2025年净利润增长5%。",
        "国家电网有限公司是中国最大的电力企业。",
        "国网在华北新建了线路。",
    ]

    for text in test_texts:
        print(f"\n📝 {text}")
        print("-" * 50)

        mentions = adapter.extract(text)

        if not mentions:
            print("  ⚠️ 未识别到实体")
            continue

        # 按位置排序
        mentions.sort(key=lambda x: (x.char_start, x.char_end))

        for m in mentions:
            extracted = text[m.char_start:m.char_end]
            match = "✅" if extracted == m.mention else "❌"
            print(f"  [{m.char_start}:{m.char_end}] '{m.mention}' ({m.mention_type})")
            print(f"      提取: '{extracted}' {match}")


if __name__ == "__main__":
    main()