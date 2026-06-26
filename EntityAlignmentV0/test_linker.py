# test_linker.py
from src.core.linker import EntityLinker
from src.utils.config import load_config


def main():
    print("=" * 60)
    print("测试实体链接核心链路")
    print("=" * 60)

    # 加载配置
    config = load_config()

    # 创建链接器
    print("\n📦 初始化实体链接器...")
    linker = EntityLinker(config)

    # 测试文本
    texts = [
        "国家电网有限公司在华北地区新建了输电线路。",
        "中石油2025年净利润增长5%。",
        "华能国际电力股份有限公司在华东地区有多个项目。",
    ]

    for text in texts:
        print("\n" + "-" * 40)
        print(f"📝 输入文本: {text}")
        print("-" * 40)

        # 执行链接
        result = linker.link(text)

        # 输出结果
        print(f"\n📊 统计: 总计 {result['stats']['total_mentions']} 个实体, "
              f"链接 {result['stats']['linked']} 个, NIL {result['stats']['nil']} 个")

        for r in result["results"]:
            if r.get("is_nil"):
                print(f"  ❌ {r['mention']} ({r['type']}) → NIL")
            else:
                print(f"  ✅ {r['mention']} ({r['type']}) → {r['standard_entity']} (置信度: {r['confidence']:.3f})")

        print(f"\n🔗 trace_id: {result['trace_id']}")


if __name__ == "__main__":
    main()