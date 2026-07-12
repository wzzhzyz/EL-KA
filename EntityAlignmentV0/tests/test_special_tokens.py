import os
import sys
from pathlib import Path
from transformers import AutoTokenizer

# ============================================================
# 1. 找到正确的模型路径
# ============================================================

# 方法1：使用绝对路径（推荐）
# 请将下面的路径替换为你的实际模型路径
model_path = r"/models_cache/finetuned_bge_reranker_large1"

# 方法2：使用相对路径（相对于当前工作目录）
# model_path = "./finetuned_bge_reranker_large"

# 方法3：从配置文件读取（需要先加载配置）
# from src.utils.config import load_config
# config = load_config("config.yaml")
# model_path = config.get("reranker_model_path", "./finetuned_bge_reranker_large")

# ============================================================
# 2. 检查路径是否存在
# ============================================================

print(f"模型路径: {model_path}")
print(f"路径是否存在: {os.path.exists(model_path)}")

if not os.path.exists(model_path):
    # 尝试查找可能的模型目录
    print("\n❌ 模型路径不存在！正在查找可能的目录...")

    # 查找当前目录下的 finetuned_* 目录
    current_dir = Path.cwd()
    for item in current_dir.iterdir():
        if item.is_dir() and item.name.startswith("finetuned"):
            print(f"  找到: {item}")

    # 查找父目录
    parent_dir = current_dir.parent
    for item in parent_dir.iterdir():
        if item.is_dir() and item.name.startswith("finetuned"):
            print(f"  找到: {item}")

    sys.exit(1)

# ============================================================
# 3. 检查必要的文件
# ============================================================

required_files = ["pytorch_model.bin", "config.json", "tokenizer.json"]
missing_files = [f for f in required_files if not os.path.exists(os.path.join(model_path, f))]

if missing_files:
    print(f"\n⚠️ 缺少必要文件: {missing_files}")
    print(f"目录内容: {os.listdir(model_path)}")
else:
    print("\n✅ 所有必要文件都存在")

# ============================================================
# 4. 加载 tokenizer 并验证
# ============================================================

print("\n" + "=" * 60)
print("加载 tokenizer...")
print("=" * 60)

try:
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    print(f"✅ Tokenizer 加载成功")
    print(f"   词表大小: {len(tokenizer)}")
except Exception as e:
    print(f"❌ Tokenizer 加载失败: {e}")
    sys.exit(1)

# ============================================================
# 5. 检查 [*] 和 [/*] 是否在词表中
# ============================================================

print("\n" + "=" * 60)
print("检查自定义标记...")
print("=" * 60)

vocab = tokenizer.get_vocab()
has_star_start = '[*]' in vocab
has_star_end = '[/*]' in vocab

print(f"'[*]' 在词表中: {has_star_start}")
print(f"'[/*]' 在词表中: {has_star_end}")

# 如果在词表中，显示 token ID
if has_star_start:
    print(f"   '[*]' token ID: {vocab['[*]']}")
if has_star_end:
    print(f"   '[/*]' token ID: {vocab['[/*]']}")

# ============================================================
# 6. 测试分词行为
# ============================================================

print("\n" + "=" * 60)
print("测试分词行为...")
print("=" * 60)

text = "[*]苹果[/*]公司"
print(f"原始文本: {text}")

tokens = tokenizer.tokenize(text)
print(f"分词结果: {tokens}")

token_ids = tokenizer.encode(text, add_special_tokens=False)
print(f"Token IDs: {token_ids}")

# 解码验证
decoded = tokenizer.decode(token_ids)
print(f"解码还原: {decoded}")

# ============================================================
# 7. 判断标记是否生效
# ============================================================

print("\n" + "=" * 60)
print("判断结果...")
print("=" * 60)

if has_star_start and has_star_end:
    # 检查分词结果是否包含完整的 [*] 和 [/*]
    if '[*]' in tokens and '[/*]' in tokens:
        print("✅ [*] 和 [/*] 在词表中，且分词时被识别为整体！")
        print("   标记在训练和推理中都会生效。")
    else:
        print("⚠️ [*] 和 [/*] 在词表中，但分词时被拆分了！")
        print(f"   实际分词: {tokens}")
        print("   可能原因: tokenizer 的添加操作未正确保存。")
else:
    print("❌ [*] 和 [/*] 不在词表中！")
    print("   标记在训练和推理中都不会生效。")
    print("\n解决方案:")
    print("   1. 在 disambiguate.py 的加载逻辑中添加标记（已存在）")
    print("   2. 如果训练时没有添加，需要重新训练")

# ============================================================
# 8. 如果标记不在词表中，尝试动态添加
# ============================================================

if not (has_star_start and has_star_end):
    print("\n" + "=" * 60)
    print("尝试动态添加标记...")
    print("=" * 60)

    try:
        special_tokens = ["[*]", "[/*]"]
        added = tokenizer.add_tokens(special_tokens)
        print(f"添加了 {added} 个新 token")

        # 重新检查
        vocab = tokenizer.get_vocab()
        has_star_start = '[*]' in vocab
        has_star_end = '[/*]' in vocab

        print(f"'[*]' 在词表中: {has_star_start}")
        print(f"'[/*]' 在词表中: {has_star_end}")

        if has_star_start and has_star_end:
            print("✅ 动态添加成功！")
            print("   ⚠️ 注意: 这只会影响当前运行的 tokenizer")
            print("   模型权重未扩展，需要调用 model.resize_token_embeddings()")
        else:
            print("❌ 动态添加失败")

    except Exception as e:
        print(f"❌ 动态添加失败: {e}")