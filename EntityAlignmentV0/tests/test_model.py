# test_model.py
print("=" * 50)
print("测试模型加载...")
print("=" * 50)

# 1. 测试 BGE 模型
print("\n[1/2] 测试 BGE 模型加载...")
try:
    from sentence_transformers import SentenceTransformer
    import os

    model_path = "../models_cache/bge-small-zh"

    # 检查模型文件是否存在
    if os.path.exists(model_path):
        print(f"   ✅ 模型文件夹存在: {model_path}")
        files = os.listdir(model_path)
        print(f"   文件列表: {files}")
    else:
        print(f"   ❌ 模型文件夹不存在: {model_path}")
        exit(1)

    # 尝试加载
    print("   正在加载模型...")
    model = SentenceTransformer(model_path)
    print("   ✅ BGE 模型加载成功！")

    # 测试编码
    print("   测试文本编码...")
    emb = model.encode("测试文本")
    print(f"   ✅ 编码成功，向量维度: {emb.shape}")

except Exception as e:
    print(f"   ❌ 加载失败: {e}")
    exit(1)

# 2. 测试 HanLP NER
print("\n[2/2] 测试 HanLP NER 模型...")
try:
    import hanlp

    # HanLP 模型会自动从缓存加载
    print("   正在加载 NER 模型...")
    ner = hanlp.load("COARSE_ELECTRA_SMALL_ZH")
    print("   ✅ HanLP NER 模型加载成功！")

    # 测试识别
    text = "国家电网有限公司在华北地区"
    result = ner(text)
    print(f"   测试文本: {text}")
    print(f"   识别结果: {result}")

except Exception as e:
    print(f"   ❌ 加载失败: {e}")
    exit(1)

print("\n" + "=" * 50)
print("🎉 所有模型加载测试通过！可以开始开发了！")
print("=" * 50)