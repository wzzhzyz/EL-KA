import torch
from transformers import AutoTokenizer

if __name__ == '__main__':
    tokenizer=AutoTokenizer.from_pretrained('../models_cache/finetuned_bge_reranker_large1')
    print(tokenizer.tokenize('[*]国网[/*]2025年特高压直流输电工程累计输送电量超过2000亿千瓦时。'))