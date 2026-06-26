# test_coreference_fastcoref.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.linker import EntityLinker
from src.utils.config import load_config


def main():
    print("=" * 60)
    print("测试共指消解 (FastCoref + XLM-RoBERTa)")
    print("=" * 60)

    config = load_config()
    linker = EntityLinker(config)

    text = "国家电网有限公司2025年营收增长5%。它在华北地区新建了输电线路，该公司还计划继续投资。"

    print(f"\n📝 输入文本: {text}")

    print("\n" + "-" * 40)
    print("❌ 不启用共指消解:")
    print("-" * 40)

    result_off = linker.link(text, {"enable_coreference": False})
    for r in result_off["results"]:
        if r.get("is_nil"):
            print(f"  ❌ {r['mention']} → NIL")
        else:
            coref = " (共指)" if r.get("is_coreference") else ""
            print(f"  ✅ {r['mention']} → {r.get('standard_entity', 'N/A')}{coref}")

    print("\n" + "-" * 40)
    print("✅ 启用共指消解:")
    print("-" * 40)

    result_on = linker.link(text, {"enable_coreference": True})
    for r in result_on["results"]:
        if r.get("is_nil"):
            print(f"  ❌ {r['mention']} → NIL")
        else:
            coref = " (共指)" if r.get("is_coreference") else ""
            method = f" [{r.get('method', '')}]" if r.get('method') else ""
            print(f"  ✅ {r['mention']} → {r.get('standard_entity', 'N/A')}{coref}{method}")

    print(f"\n📊 统计:")
    print(f"  总提及: {result_on['stats']['total_mentions']}")
    print(f"  链接: {result_on['stats']['linked']}")
    print(f"  共指解析: {result_on['stats'].get('coreference_resolved', 0)}")


if __name__ == "__main__":
    main()