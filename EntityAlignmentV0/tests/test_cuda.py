from sentence_transformers import SentenceTransformer
import torch
from src.utils.config import load_config, resolve_path

config = load_config()
model = SentenceTransformer(resolve_path(config["bge_model_path"]), device='cuda')

# ===== 关键验证 =====
sentences = ["测试句子1", "测试句子2"]

# 编码时强制返回 tensor，并检查设备
embeddings = model.encode(sentences, convert_to_tensor=True)
print(f"✅ 编码结果设备: {embeddings.device}")  # 这里如果是 cuda:0 就说明在GPU上

# 更精确：检查模型参数实际在哪个设备
for name, param in model.named_parameters():
    print(f"{name}: {param.device}")
    break  # 只看第一个参数就行

# 检查是否有 GPU 内存被使用
if torch.cuda.is_available():
    print(f"GPU显存占用: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")