import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from fastcoref import FCoref

# 使用 XLM-RoBERTa（多语言模型，支持中文）
model = FCoref(
    model_name_or_path="xlm-roberta-base",  # 或 "xlm-roberta-base"
    device="cpu"
)

text = "国家电网有限公司2025年营收增长5%。它在华北地区新建了输电线路。"
preds = model.predict(text)
clusters = preds.get_clusters(as_strings=True)
print(clusters)