import torch
import torch.nn as nn

# 模拟数据
logits = torch.tensor([[2.3]])  # 模型输出
labels = torch.tensor([[1.0]])  # 正样本

# 方式1：BCEWithLogitsLoss（推荐，数值稳定）
loss_fn = nn.BCEWithLogitsLoss()
loss1 = loss_fn(logits, labels)
print(f"BCEWithLogitsLoss: {loss1.item():.4f}")

# 方式2：手动 Sigmoid + BCELoss（等价，但数值不稳定）
probs = torch.sigmoid(logits)
loss_fn2 = nn.BCELoss()
loss2 = loss_fn2(probs, labels)
print(f"手动 Sigmoid + BCELoss: {loss2.item():.4f}")

# 两者结果完全一样
# BCEWithLogitsLoss: 0.0941
# 手动 Sigmoid + BCELoss: 0.0941