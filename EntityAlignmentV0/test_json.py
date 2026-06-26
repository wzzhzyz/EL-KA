# test_json.py
import json

print("验证 knowledge_base.json 文件...")

try:
    with open("data/knowledge_base.json", "r", encoding="utf-8") as f:
        content = f.read()
        print(f"文件大小: {len(content)} 字节")

        if not content.strip():
            print("❌ 文件为空！请复制上面的 JSON 内容到文件中")
            exit(1)

        data = json.loads(content)
        print(f"✅ JSON 格式正确！共 {len(data)} 个实体")

        # 显示前3个实体
        for i, entity in enumerate(data[:3]):
            print(f"  {i + 1}. {entity['standard_name']} ({entity['entity_id']})")

except FileNotFoundError:
    print("❌ 文件不存在！请创建 data/knowledge_base.json")
except json.JSONDecodeError as e:
    print(f"❌ JSON 格式错误: {e}")
    print("请检查文件是否有语法错误")