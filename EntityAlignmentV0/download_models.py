# download_models.py
import os

# ============================================================
# 使用 HuggingFace 国内镜像源（解决网络问题）
# ============================================================
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# BGE 模型缓存
os.environ["HF_HOME"] = os.path.join(PROJECT_ROOT, "models_cache", "huggingface")
os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(PROJECT_ROOT, "models_cache", "huggingface")

os.makedirs(os.path.join(PROJECT_ROOT, "models_cache", "huggingface"), exist_ok=True)
os.makedirs(os.path.join(PROJECT_ROOT, "models_cache", "bge-small-zh"), exist_ok=True)
os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)

print("=" * 60)
print("项目根目录:", PROJECT_ROOT)
print(f"HF 镜像源: {os.environ['HF_ENDPOINT']}")
print("=" * 60)

import hanlp
from sentence_transformers import SentenceTransformer


def download_models():
    print("\n[1/2] 下载 HanLP NER 模型...")
    try:
        # 下载 HanLP 模型（HanLP 不受镜像源影响）
        # 添加这个模型的下载
        ner = hanlp.load("CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH")
        print("✅ CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH 下载完成")
    except Exception as e:
        print(f"❌ 失败: {e}")

    print("\n[2/2] 下载 BGE 模型...")
    try:
        bge = SentenceTransformer("BAAI/bge-small-zh")
        bge.save(os.path.join(PROJECT_ROOT, "models_cache", "bge-small-zh"))
        print(f"✅ BGE 模型保存到: {os.path.join(PROJECT_ROOT, 'models_cache', 'bge-small-zh')}")
    except Exception as e:
        print(f"❌ BGE 模型下载失败: {e}")
        print("\n请尝试以下方法之一：")
        print("1. 检查网络连接，或切换网络环境")
        print("2. 手动下载模型文件到 ./models_cache/bge-small-zh/")
        print("   下载地址: https://hf-mirror.com/BAAI/bge-small-zh")

    print("\n" + "=" * 60)
    print("模型下载完成！")
    print("=" * 60)


if __name__ == "__main__":
    download_models()