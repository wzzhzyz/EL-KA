# test_hanlp_adapter.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ner.adapters.hanlp_adapter import HanLPAdapter


def main():
    text = "国家电网有限公司在华北地区新建了输电线路。"

    adapter = HanLPAdapter()
    mentions = adapter.extract(text)

    print(f"文本: {text}")
    print(f"长度: {len(text)} 字符")
    print("\n识别结果:")

    for m in mentions:
        extracted = text[m.char_start:m.char_end]
        print(f"  [{m.char_start}:{m.char_end}] '{m.mention}' (类型: {m.mention_type})")
        print(f"    提取文本: '{extracted}'")
        print(f"    匹配: {'✅' if extracted == m.mention else '❌'}")


if __name__ == "__main__":
    main()