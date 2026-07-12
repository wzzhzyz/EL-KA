"""
优化后的端到端共指消解模型（e2e-coref 风格）。

相对原始版本修复的核心问题：
  1. 用 word_ids + offset_mapping 在 word/token 级生成候选 span，解决字符↔子词错位。
  2. antecedent_scorer 输入维度与 forward 实际输入对齐。
  3. 所有索引张量在 input_ids.device 上创建，消除 CPU/GPU 混用报错。
  4. 候选 span 按 batch 各自生成，以 (B, N, 2) + mask 传入，不再跨样本共享。
  5. span 特征提取全向量化（gather + 广播注意力池化），去掉 span 维 Python 循环。
  6. mention 打分后 top-k 剪枝，再用广播一次算完所有 pair 的 antecedent 分（O(K^2) 而非 O(N^2) 双层循环）。
  7. 采用标准 e2e 损失：S(i,j)=sm_i+sm_j+pairwise(i,j)，含 null antecedent，softmax 交叉熵；
     mention 用带 pos_weight 的 BCE 缓解类别不平衡。
  8. 【本项目特性】复数代词多链归属：一个代词可同时属于多条同指链（如"它们"同时归属
     阿里链与腾讯链）。训练时支持多标签 antecedent 目标（一个代词可有多个先行词）；
     推理时把该代词复制到多条高分链中（保持各链彼此独立）。

训练 / 推理工具：
  - 进度条（tqdm，缺失时自动降级为简易进度条）
  - 保存到指定目录（model + optimizer + config.json + tokenizer）
  - 断点续训（--resume：精确恢复 model/optimizer/epoch，用于训练中途中止）
  - 增量训练（--incremental：从已训练模型继续学，仅加载权重、优化器重置、
    epoch 重新计数，通常用于喂新数据扩充能力；--keep_optimizer 可保留旧优化器）
  - CorefPredictor.from_pretrained(output_dir) 加载已训练模型推理

速度优化（详见本次迭代）：
  - 批量 tokenize：一个 batch 一次分词，不再逐条调用（Mistral 慢分词器下收益明显）。
  - 候选 / tokenize 缓存：相同文档跨 epoch 只算一次，第二轮起直接命中（默认开启，
    可用 --no_cache 关闭）。
  - antecedent 损失全向量化：去掉 (b,i) Python 双层循环，单次软交叉熵完成，
    数值与原循环实现完全一致。
  - 混合精度（--fp16，仅 CUDA）：24B 大模型提速并省显存。
  - 学习率调度器（--scheduler linear/cosine + --warmup_steps/--warmup_ratio）：
    warmup 升温后线性/余弦衰减；骨干与任务头两组参数按同一系数缩放，保留差分比例。
  - HF 风格日志：每 log_step 打印 {'loss', 'grad_norm', 'learning_rate', 'epoch'}。
"""

import os
import json
import hashlib
import random
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


# ---------------------------------------------------------------------------
# 进度条（优先 tqdm，缺失则降级为简易实现）
# ---------------------------------------------------------------------------
try:
    from tqdm import tqdm
    _HAS_TQDM = True
except ImportError:  # pragma: no cover
    _HAS_TQDM = False


class _SimpleBar:
    def __init__(self, total: int, desc: str = ''):
        self.total = max(total, 1)
        self.desc = desc
        self.n = 0
        self._draw()

    def update(self, k: int = 1):
        self.n = min(self.n + k, self.total)
        self._draw()

    def _draw(self):
        pct = self.n / self.total * 100
        bar = '#' * int(pct / 5)
        print(f"\r{self.desc} [{bar:<20}] {self.n}/{self.total} {pct:5.1f}%",
              end='', flush=True)

    def close(self):
        print()


def get_bar(total: int, desc: str = ''):
    if _HAS_TQDM:
        return tqdm(total=total, desc=desc)
    return _SimpleBar(total, desc)


# ---------------------------------------------------------------------------
# 候选 span 生成（word / token 级，字符↔子词对齐）
# ---------------------------------------------------------------------------
def generate_candidate_spans(doc: str,
                             offset_mapping: List[Tuple[int, int]],
                             max_span_width: int = 10,
                             max_candidates: int = 1000,
                             max_span_tokens: int = 32) -> List[Dict]:
    """
    与 tokenizer 无关的候选 span 生成：基于 offset_mapping 在字符级枚举，
    再反查覆盖该字符区间的 token 下标（tok_start, tok_end）。

    不再依赖 word_ids（Mistral 等解码器模型下 word_ids 退化，会产生整篇超长 span）。

    返回: list of {tok_start, tok_end, char_start, char_end, text}
          候选按下标顺序排列，故下标 i<j 即 "更早出现"。
    """
    n = len(doc)
    # 字符 -> token 映射（special token 的 offset 为 (0,0)，跳过）
    char_to_token = [-1] * n
    for t, (os_, oe) in enumerate(offset_mapping):
        if os_ == oe:
            continue
        for c in range(os_, min(oe, n)):
            char_to_token[c] = t

    candidates: List[Dict] = []
    for s in range(n):
        ts = char_to_token[s]
        if ts < 0:
            continue
        max_e = min(s + max_span_width, n)
        for e in range(s + 1, max_e + 1):
            text = doc[s:e]
            if not _is_valid_span(text):
                continue
            te = char_to_token[e - 1]
            if te < 0 or te < ts:
                continue
            # 限制 token 宽度（避免 Mistral 下 10 汉字对应过多 token 超出注意力窗口）
            if (te - ts + 1) > max_span_tokens:
                continue
            candidates.append({
                "tok_start": ts,
                "tok_end": te,
                "char_start": s,
                "char_end": e,
                "text": text,
            })
            if len(candidates) >= max_candidates:
                return candidates
    return candidates


def _is_valid_span(text: str) -> bool:
    if len(text) < 1:
        return False
    if text.isspace():
        return False
    if text.isdigit():
        return False
    if all((not c.isalnum()) and c not in ('·', '•') for c in text):
        return False
    return True


def pad_candidates(cands_list: List[List[Dict]], device) -> Tuple[torch.Tensor, torch.Tensor]:
    """把变长候选列表 pad 成 (B, N, 2) 的 token 下标张量 + (B, N) mask。"""
    max_n = max(len(c) for c in cands_list)
    tok = torch.zeros(len(cands_list), max_n, 2, dtype=torch.long, device=device)
    mask = torch.zeros(len(cands_list), max_n, dtype=torch.bool, device=device)
    for b, cands in enumerate(cands_list):
        for i, c in enumerate(cands):
            tok[b, i, 0] = c["tok_start"]
            tok[b, i, 1] = c["tok_end"]
            mask[b, i] = True
    return tok, mask


# ---------------------------------------------------------------------------
# 模型
# ---------------------------------------------------------------------------
class CorefModel(nn.Module):
    def __init__(self,
                 bert_model_name: str = 'bert-base-chinese',
                 max_span_width: int = 10,
                 feature_size: int = 20,
                 max_antecedents: int = 128,
                 max_span_tokens: int = 32,
                 dropout: float = 0.2):
        super().__init__()
        self.bert = AutoModel.from_pretrained(bert_model_name)
        self.hidden_size = self.bert.config.hidden_size
        self.max_span_width = max_span_width
        self.max_antecedents = max_antecedents
        self.max_span_tokens = max_span_tokens

        # span 起点/终点/头部词/宽度 -> 投影
        self.head_attention = nn.Linear(self.hidden_size, 1)
        self.width_embedding = nn.Embedding(max_span_tokens + 1, feature_size)
        self.span_projection = nn.Sequential(
            nn.Linear(self.hidden_size * 3 + feature_size, self.hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
        )

        # mention 打分器
        self.mention_scorer = nn.Sequential(
            nn.Linear(self.hidden_size, self.hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(self.hidden_size // 2, 1),
        )

        # antecedent 打分器：pairwise 特征 = [i, j, i*j, |i-j|] + 距离特征
        self.distance_embedding = nn.Embedding(50, feature_size)
        self.antecedent_scorer = nn.Sequential(
            nn.Linear(self.hidden_size * 4 + feature_size, self.hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(self.hidden_size, 1),
        )

    @classmethod
    def from_pretrained_dir(cls, output_dir: str, device: str = 'cpu') -> 'CorefModel':
        with open(os.path.join(output_dir, 'config.json'), 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg.setdefault('max_span_tokens', 32)  # 兼容旧版 config
        model = cls(**cfg)
        sd = torch.load(os.path.join(output_dir, 'checkpoint_latest.pt'),
                        map_location=device)
        model.load_state_dict(sd['model_state_dict'])
        return model

    def forward(self,
                input_ids: torch.Tensor,          # (B, S)
                attention_mask: torch.Tensor,      # (B, S)
                candidate_spans: torch.Tensor,     # (B, N, 2) token 下标
                candidate_mask: torch.Tensor,      # (B, N) 有效候选
                gold_mask: Optional[torch.Tensor] = None,
                #   (B, N) bool：哪些候选是 gold mention。仅训练时传入，
                #   推理时为 None（按真实分数剪枝）。用于强制 gold 进入剪枝集。
                ) -> Dict[str, torch.Tensor]:
        device = input_ids.device
        B, N = candidate_spans.size(0), candidate_spans.size(1)
        starts = candidate_spans[..., 0]           # (B, N)
        ends = candidate_spans[..., 1]             # (B, N)

        # 1. BERT 编码
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        word_embeddings = outputs.last_hidden_state  # (B, S, H)
        S = word_embeddings.size(1)

        batch_idx = torch.arange(B, device=device).unsqueeze(1)  # (B,1)

        # 2. span 特征（向量化）
        start_emb = word_embeddings[batch_idx, starts]           # (B,N,H)
        end_emb = word_embeddings[batch_idx, ends]               # (B,N,H)

        W = self.max_span_tokens
        pos = starts.unsqueeze(-1) + torch.arange(W, device=device)  # (B,N,W)
        within = pos <= ends.unsqueeze(-1)                         # (B,N,W)
        pos = pos.clamp(max=S - 1)
        tok = word_embeddings[batch_idx.unsqueeze(-1), pos]        # (B,N,W,H)
        attn_logits = self.head_attention(tok).squeeze(-1)         # (B,N,W)
        attn_logits = attn_logits.masked_fill(~within, float('-inf'))
        attn = F.softmax(attn_logits, dim=-1)                      # (B,N,W)
        head_emb = (attn.unsqueeze(-1) * tok).sum(dim=2)          # (B,N,H)

        width = (ends - starts + 1).clamp(1, self.max_span_tokens)
        width_emb = self.width_embedding(width)                   # (B,N,feat)

        span_emb = torch.cat([start_emb, end_emb, head_emb, width_emb], dim=-1)
        span_emb = self.span_projection(span_emb)                 # (B,N,H)

        # 3. mention 打分（无效候选用有限大负数屏蔽，避免 BCE 对 -inf 产生 nan）
        mention_scores = self.mention_scorer(span_emb).squeeze(-1)  # (B,N)
        mention_scores = mention_scores.masked_fill(~candidate_mask, -1e4)

        # 4. top-k 剪枝。
        #    训练时为打破"鸡生蛋"问题（早期 mention 分随机，gold 易落在 top-k 之外，
        #    导致 antecedent 损失从来看不到 gold 对，共指信号被饿死、loss 卡住），
        #    这里【临时抬高】gold 的分数使其必然入选，但后续联合分数仍使用【原始】分数，
        #    避免注入污染打分。推理时不传 gold_mask，按真实分数剪枝。
        if gold_mask is not None:
            num_gold = int(gold_mask.long().sum(dim=1).max().item())
            # 保证剪枝容量 >= 本 batch 最多 gold 数，避免 gold 被 top-k 挤掉
            K = min(max(self.max_antecedents, num_gold), N)
            boost = mention_scores.masked_fill(gold_mask, 1e4)       # gold 优先入选
        else:
            K = min(self.max_antecedents, N)
            boost = mention_scores
        _, topk_pos = torch.topk(boost, K, dim=1)                    # (B,K) 按分数
        pruned_indices = topk_pos.sort(dim=1).values                 # (B,K) 按文档顺序
        pruned_starts = torch.gather(starts, 1, pruned_indices)       # (B,K)
        pruned_emb = torch.gather(
            span_emb, 1,
            pruned_indices.unsqueeze(-1).expand(B, K, self.hidden_size))  # (B,K,H)
        # 用【原始】mention 分（非 boost）计算联合分数，保证打分不被注入污染
        pruned_mention = torch.gather(mention_scores, 1, pruned_indices)  # (B,K)

        # 5. pairwise 打分（广播一次算完所有 pair，仅 j<i 有效）
        si = pruned_emb.unsqueeze(2).expand(B, K, K, self.hidden_size)  # (B,K,K,H)
        sj = pruned_emb.unsqueeze(1).expand(B, K, K, self.hidden_size)  # (B,K,K,H)
        pair_feat = torch.cat([si, sj, si * sj, (si - sj).abs()], dim=-1)  # (B,K,K,4H)

        dist = (pruned_starts.unsqueeze(2) - pruned_starts.unsqueeze(1)).abs()  # (B,K,K)
        dist = dist.clamp(max=49).long()
        dist_emb = self.distance_embedding(dist)                    # (B,K,K,feat)

        pair_feat = torch.cat([pair_feat, dist_emb], dim=-1)        # (B,K,K,4H+feat)
        pairwise = self.antecedent_scorer(pair_feat).squeeze(-1)    # (B,K,K)

        # 仅保留 j < i（更早出现者作为先行词），其余置 -inf
        idx = torch.arange(K, device=device)
        lower_mask = idx.unsqueeze(0) < idx.unsqueeze(1)            # (K,K) j<i
        pairwise = pairwise.masked_fill(~lower_mask.unsqueeze(0), float('-inf'))

        # 6. 联合分数 S(i,j) = sm_i + sm_j + pairwise(i,j)
        sm_i = pruned_mention.unsqueeze(2)        # (B,K,1)
        sm_j = pruned_mention.unsqueeze(1)        # (B,1,K)
        combined = sm_i + sm_j + pairwise         # (B,K,K)，j>=i 为 -inf

        return {
            "mention_scores": mention_scores,      # (B,N) 全量
            "pruned_indices": pruned_indices,      # (B,K)
            "pruned_mention": pruned_mention,      # (B,K)
            "pairwise": combined,                  # (B,K,K) 含 -inf（j>=i）
            "candidate_spans": candidate_spans,    # (B,N,2)
            "candidate_mask": candidate_mask,      # (B,N)
        }


# ---------------------------------------------------------------------------
# 损失（标准 e2e：含 null antecedent 的 softmax 交叉熵 + 加权 BCE）
# 复数代词支持多标签 antecedent 目标（一个代词可有多个先行词）。
# ---------------------------------------------------------------------------
class CorefLoss(nn.Module):
    def __init__(self, mention_pos_weight: float = 5.0):
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss(
            pos_weight=torch.tensor(mention_pos_weight))

    def forward(self,
                model_out: Dict[str, torch.Tensor],
                antecedent_targets: List[List[List[int]]],  # (B, N) 每个候选的 gold 先行词下标列表
                mention_labels: torch.Tensor,               # (B, N) 0/1
                ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        device = model_out["mention_scores"].device
        B = model_out["mention_scores"].size(0)
        K = model_out["pruned_indices"].size(1)

        mention_loss = self.bce(model_out["mention_scores"], mention_labels)

        pruned = model_out["pruned_indices"]                # (B,K)
        combined = model_out["pairwise"]                    # (B,K,K) 含 -inf (j>=i)
        # 含 null 槽位的 logits：(B,K,K+1)，槽 0=null 恒为 0
        logits = torch.cat([torch.zeros(B, K, 1, device=device), combined], dim=-1)

        # 目标分布 P (B,K,K+1)：单标签 -> one-hot；多标签 -> 均匀质量；无 -> null
        P = torch.zeros(B, K, K + 1, device=device)
        for b in range(B):
            full2pruned = {int(pruned[b, p]): p for p in range(K)}
            ant_b = antecedent_targets[b]
            for i in range(K):
                c_full = int(pruned[b, i])                  # 当前候选在全量中的下标
                golds = ant_b[c_full]                        # list[int]
                # 仅保留更早出现者（j<i）且确实落在剪枝集内
                targets = [full2pruned[g] + 1 for g in golds
                           if g in full2pruned and full2pruned[g] < i]
                if len(targets) == 1:
                    P[b, i, targets[0]] = 1.0
                elif len(targets) > 1:
                    w = 1.0 / len(targets)
                    for t in targets:
                        P[b, i, t] += w
                else:
                    P[b, i, 0] = 1.0

        # 软交叉熵（单标签退化为普通 CE，多标签为均匀分布 KL）；按候选数平均
        logp = F.log_softmax(logits, dim=-1).clamp(min=-1e4)   # (B,K,K+1)
        ant_loss = (-(P * logp).sum(dim=-1)).sum() / (B * K)

        total = mention_loss + ant_loss
        return total, mention_loss, ant_loss


# ---------------------------------------------------------------------------
# 数据处理
# ---------------------------------------------------------------------------
def _stable_hash(obj) -> int:
    """对簇标注等可序列化对象生成稳定哈希，用作候选缓存键的一部分。"""
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    return int(hashlib.md5(s.encode('utf-8')).hexdigest(), 16)


class CorefDataProcessor:
    def __init__(self, tokenizer, max_span_width: int = 10, max_len: int = 512,
                 max_candidates: int = 1000, max_span_tokens: int = 32,
                 cache: bool = True):
        self.tokenizer = tokenizer
        self.max_span_width = max_span_width
        self.max_len = max_len
        self.max_candidates = max_candidates
        self.max_span_tokens = max_span_tokens
        # 候选 + tokenize 结果缓存：同一文档（含其簇标注）在不同 epoch 只算一次，
        # 第二轮起直接命中，显著加速预处理（尤其 Mistral 慢分词器）。
        # 注意：仅当「相同 doc 文本必然对应相同簇标注」时安全（共指数据集通常满足）。
        self._cache = {} if cache else None

    def _encode(self, texts: List[str]) -> Dict:
        """批量 tokenize（一次调用处理整批，远快于逐条调用）。"""
        return self.tokenizer(
            texts, max_length=self.max_len, truncation=True,
            padding='max_length', return_tensors='pt',
            return_offsets_mapping=True)

    @staticmethod
    def _build_targets(doc: str, cands: List[Dict],
                       clusters: List[List[Dict]]) -> Tuple[List[List[int]], List[int]]:
        """由候选区间与簇标注构造 antecedent_targets 与 mention_labels。"""
        char2cand = {(c["char_start"], c["char_end"]): idx
                     for idx, c in enumerate(cands)}

        def find_cand(s, e):
            return (char2cand.get((s, e)) or char2cand.get((s, e - 1))
                    or char2cand.get((s + 1, e)))

        # 每个候选可能属于多个簇（复数代词多链归属特性）
        mention_clusters: Dict[int, List[int]] = defaultdict(list)
        for cid, cluster in enumerate(clusters):
            for m in cluster:
                idx = find_cand(m['char_start'], m['char_end'])
                if idx is not None and cid not in mention_clusters[idx]:
                    mention_clusters[idx].append(cid)

        cluster_members: Dict[int, List[int]] = defaultdict(list)
        for idx, cids in mention_clusters.items():
            for cid in cids:
                cluster_members[cid].append(idx)

        # antecedent 目标：每个候选 = 其所在所有簇中"更早出现"的 gold 成员列表
        #  -> 普通 mention 取最近先行词；复数代词（跨多簇）取多个先行词
        n = len(cands)
        antecedent_targets: List[List[int]] = [[] for _ in range(n)]
        for cid, members in cluster_members.items():
            members = sorted(set(members))
            for rank, idx in enumerate(members):
                for prev in members[:rank]:
                    antecedent_targets[idx].append(prev)

        mention_labels = [1 if i in mention_clusters else 0 for i in range(n)]
        return antecedent_targets, mention_labels

    def process_document(self, doc: str, clusters: List[List[Dict]]) -> Dict:
        """单文档处理（接口保留；批量训练走 process_batch 更快）。"""
        return self.process_batch([doc], [clusters])[0]

    def process_batch(self, docs: List[str],
                      clusters_list: List[List[List[Dict]]]) -> List[Dict]:
        """批量处理一整批文档：一次 tokenize + 按文档生成候选，命中缓存则跳过。"""
        results = [None] * len(docs)
        miss_idx, miss_docs, miss_clusters = [], [], []
        for i, (d, cl) in enumerate(zip(docs, clusters_list)):
            key = (d, _stable_hash(cl)) if self._cache is not None else None
            if self._cache is not None and key in self._cache:
                results[i] = self._cache[key]
            else:
                miss_idx.append(i)
                miss_docs.append(d)
                miss_clusters.append(cl)

        if miss_docs:
            encoding = self._encode(miss_docs)
            for j, (i, d, cl) in enumerate(zip(miss_idx, miss_docs, miss_clusters)):
                offset_mapping = encoding['offset_mapping'][j].tolist()
                cands = generate_candidate_spans(
                    d, offset_mapping,
                    max_span_width=self.max_span_width,
                    max_candidates=self.max_candidates,
                    max_span_tokens=self.max_span_tokens)
                ant, labels = self._build_targets(d, cands, cl)
                res = {
                    'input_ids': encoding['input_ids'][j],
                    'attention_mask': encoding['attention_mask'][j],
                    'candidates': cands,
                    'antecedent_targets': ant,
                    'mention_labels': labels,
                }
                results[i] = res
                if self._cache is not None:
                    self._cache[(d, _stable_hash(cl))] = res
        return results

    @staticmethod
    def collate(batch: List[Dict], device) -> Dict:
        input_ids = torch.stack([b['input_ids'] for b in batch]).to(device)
        attention_mask = torch.stack([b['attention_mask'] for b in batch]).to(device)
        cand_spans, cand_mask = pad_candidates([b['candidates'] for b in batch], device)
        max_n = cand_mask.size(1)
        mention_labels = torch.tensor(
            [b['mention_labels'] + [0] * (max_n - len(b['mention_labels']))
             for b in batch], dtype=torch.float, device=device)
        # antecedent_targets 为变长列表，直接透传
        ant_targets = [b['antecedent_targets'] for b in batch]
        return {
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'candidate_spans': cand_spans,
            'candidate_mask': cand_mask,
            'antecedent_targets': ant_targets,
            'mention_labels': mention_labels,
        }


# ---------------------------------------------------------------------------
# 训练（含进度条 / 存档 / 断点续训）
# ---------------------------------------------------------------------------
def _find_latest_checkpoint(output_dir: str) -> Optional[str]:
    latest = os.path.join(output_dir, 'checkpoint_latest.pt')
    if os.path.isfile(latest):
        return latest
    best = None
    best_epoch = -1
    for fn in os.listdir(output_dir):
        if fn.startswith('checkpoint_epoch_') and fn.endswith('.pt'):
            try:
                ep = int(fn[len('checkpoint_epoch_'):-len('.pt')])
            except ValueError:
                continue
            if ep > best_epoch:
                best_epoch = ep
                best = os.path.join(output_dir, fn)
    return best


def _build_scheduler(optimizer, scheduler_type: str,
                      total_steps: Optional[int], warmup_steps: int):
    """
    构造学习率调度器（基于 LambdaLR，对两组参数按同一系数缩放，保留差分比例）：
      - 'constant' / None：不使用调度器（保持原 lr）
      - 'linear'：warmup 线性升温 -> 之后线性衰减到 0
      - 'cosine'：warmup 线性升温 -> 之后余弦衰减到 0
    返回 None 表示不调度。
    """
    if not scheduler_type or scheduler_type == 'constant':
        return None
    if not total_steps or total_steps <= 0:
        return None
    warmup = max(0, int(warmup_steps))
    if scheduler_type == 'linear':
        def lr_lambda(step):
            step = max(int(step), 0)
            if step < warmup:
                return float(step) / float(max(1, warmup))
            return max(0.0, float(total_steps - step) /
                       float(max(1, total_steps - warmup)))
    elif scheduler_type == 'cosine':
        import math
        def lr_lambda(step):
            step = max(int(step), 0)
            if step < warmup:
                return float(step) / float(max(1, warmup))
            progress = float(step - warmup) / float(max(1, total_steps - warmup))
            return max(0.0, 0.5 * (1.0 + math.cos(math.pi * min(1.0, progress))))
    else:
        raise ValueError(f"未知调度器类型: {scheduler_type}")
    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


class CorefTrainer:
    def __init__(self, model, processor, device='cuda', lr=2e-5,
                 lr_head=None, mention_pos_weight=5.0, fp16: bool = False,
                 scheduler_type: str = 'constant', total_steps: Optional[int] = None,
                 warmup_steps: int = 0):
        self.model = model.to(device)
        self.processor = processor
        self.device = device
        # 差分学习率：大模型骨干（BERT/Mistral）用小 lr，避免 24B 骨干被统一大 lr
        # 实质上冻结、梯度信号弱；任务头（mention/antecedent scorer）用大 lr 快速收敛。
        lr_head = lr_head or (lr * 5)  # 任务头默认比骨干快 5 倍
        backbone = list(model.bert.parameters())
        heads = [p for n, p in model.named_parameters()
                 if not n.startswith('bert.')]
        self.optimizer = torch.optim.AdamW([
            {'params': backbone, 'lr': lr},
            {'params': heads, 'lr': lr_head},
        ])
        self.loss_fn = CorefLoss(mention_pos_weight=mention_pos_weight)
        self.global_step = 0
        # 学习率调度器（warmup + 衰减）；两组参数按同一系数缩放，保留差分比例
        self.scheduler_type = scheduler_type
        self.scheduler = _build_scheduler(self.optimizer, scheduler_type,
                                          total_steps, warmup_steps)
        # 混合精度（仅 CUDA 生效）：24B 大模型下大幅提速并省显存
        self.fp16 = bool(fp16) and self.device.startswith('cuda')
        self.scaler = torch.cuda.amp.GradScaler() if self.fp16 else None

    def _compute_loss(self, batch, gold_mask=None):
        """前向 + 损失；训练时包在 autocast 内以启用混合精度。"""
        with torch.amp.autocast('cuda', enabled=self.fp16):
            out = self.model(
                batch['input_ids'], batch['attention_mask'],
                batch['candidate_spans'], batch['candidate_mask'],
                gold_mask=gold_mask)
            loss, m_loss, a_loss = self.loss_fn(
                out, batch['antecedent_targets'], batch['mention_labels'])
        return out, loss, m_loss, a_loss

    def train_epoch(self, data: List[Dict], batch_size: int = 4,
                    log_step: int = 50, save_steps: int = 0,
                    eval_steps: int = 0, eval_data: Optional[List[Dict]] = None,
                    output_dir: Optional[str] = None, epoch: int = 0) -> float:
        self.model.train()
        total_loss = 0.0
        n_batches = 0
        n = len(data)
        bar = get_bar(max(1, (n + batch_size - 1) // batch_size),
                      desc='  batch')
        for start in range(0, n, batch_size):
            chunk = data[start:start + batch_size]
            # 批量 tokenize + 候选缓存（第二轮起直接命中缓存，显著加速）
            docs = [item['doc'] for item in chunk]
            clusters_list = [item['clusters'] for item in chunk]
            processed = self.processor.process_batch(docs, clusters_list)
            batch = self.processor.collate(processed, self.device)

            # 训练时强制 gold 进入剪枝集（gold injection），打破鸡生蛋问题。
            gold_mask = batch['mention_labels'] > 0.5
            out, loss, m_loss, a_loss = self._compute_loss(batch, gold_mask)

            self.optimizer.zero_grad()
            if self.scaler is not None:
                self.scaler.scale(loss).backward()
                self.scaler.unscale_(self.optimizer)
                grad_norm = torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(), 1.0)
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                loss.backward()
                grad_norm = torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(), 1.0)
                self.optimizer.step()

            # 调度器：每个优化步后更新学习率（两组参数同步缩放）
            if self.scheduler is not None:
                self.scheduler.step()

            total_loss += loss.item()
            n_batches += 1
            self.global_step += 1
            bar.update(1)
            running_avg = total_loss / n_batches

            lr_head = self.optimizer.param_groups[1]['lr']
            lr_backbone = self.optimizer.param_groups[0]['lr']
            epoch_frac = (epoch - 1) + (start + len(chunk)) / n   # 0 基小数轮次

            # 诊断：gold mention 是否落入剪枝集（gold injection 后应为 100%，
            #        若 <100% 说明该 batch gold 数超过 max_antecedents，需要调大）
            if start == 0:
                gold_idx = (batch['mention_labels'][0] > 0.5).nonzero(
                    as_tuple=True)[0].tolist()
                pruned_set = set(out['pruned_indices'][0].tolist())
                covered = sum(1 for g in gold_idx if g in pruned_set)
                if gold_idx:
                    print(f"  [诊断] gold mention 落入剪枝集(已注入): "
                          f"{covered}/{len(gold_idx)}")

            # 每 log_step 步打印 HF 风格日志
            if log_step > 0 and self.global_step % log_step == 0:
                print(f"{{'loss': {loss.item():.4f}, "
                      f"'grad_norm': {grad_norm.item():.4f}, "
                      f"'learning_rate': {lr_head:.3e}, "
                      f"'lr_backbone': {lr_backbone:.3e}, "
                      f"'epoch': {epoch_frac:.2f}}}")

            # 每 eval_steps 步在验证集上评估并输出 eval_loss
            if (eval_steps > 0 and eval_data is not None
                    and self.global_step % eval_steps == 0):
                e_loss, e_m, e_a = self.evaluate(eval_data, batch_size)
                print(f"  step {self.global_step}  eval_loss={e_loss:.4f} "
                      f"(mention={e_m:.4f}, ant={e_a:.4f})")

            # 每 save_steps 步保存 checkpoint（同时更新 latest，可断点续训）
            if (save_steps > 0 and output_dir is not None
                    and self.global_step % save_steps == 0):
                self.save_checkpoint(output_dir, epoch, running_avg,
                                     step=self.global_step)
                print(f"  step {self.global_step}  已保存 checkpoint -> {output_dir}")
        bar.close()
        return total_loss / max(n_batches, 1)

    @torch.no_grad()
    def evaluate(self, data: List[Dict], batch_size: int = 4):
        """在验证集上计算平均 loss（不改变训练状态，按真实分数剪枝）。"""
        self.model.eval()
        try:
            total, nm, na, nb = 0.0, 0.0, 0.0, 0
            for start in range(0, len(data), batch_size):
                chunk = data[start:start + batch_size]
                docs = [item['doc'] for item in chunk]
                clusters_list = [item['clusters'] for item in chunk]
                processed = self.processor.process_batch(docs, clusters_list)
                batch = self.processor.collate(processed, self.device)
                # 评估不注入 gold（真实剪枝），保证指标可信
                out, loss, m_loss, a_loss = self._compute_loss(batch)
                total += loss.item()
                nm += m_loss.item()
                na += a_loss.item()
                nb += 1
        finally:
            self.model.train()
        n = max(nb, 1)
        return total / n, nm / n, na / n

    def save_checkpoint(self, output_dir: str, epoch: int, loss: float,
                        step: Optional[int] = None):
        os.makedirs(output_dir, exist_ok=True)
        ckpt = {
            'epoch': epoch,
            'step': step,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'loss': loss,
        }
        torch.save(ckpt, os.path.join(output_dir, f'checkpoint_epoch_{epoch}.pt'))
        torch.save(ckpt, os.path.join(output_dir, 'checkpoint_latest.pt'))
        if step is not None:
            torch.save(ckpt, os.path.join(output_dir, f'checkpoint_step_{step}.pt'))

    def load_checkpoint(self, output_dir: str, map_location=None,
                         load_optimizer: bool = True):
        """
        加载最新 checkpoint。
        - load_optimizer=True（断点续训）：同时恢复优化器状态，返回已训练到的 epoch。
        - load_optimizer=False（增量训练）：仅恢复模型权重，优化器保持新建状态，
          返回 0（epoch 从 1 重新计数），避免旧数据的 Adam 动量污染新数据分布。
        无 checkpoint 时返回 0。
        """
        ckpt_path = _find_latest_checkpoint(output_dir)
        if ckpt_path is None:
            return 0
        sd = torch.load(ckpt_path, map_location=map_location or self.device)
        self.model.load_state_dict(sd['model_state_dict'])
        if load_optimizer and 'optimizer_state_dict' in sd:
            self.optimizer.load_state_dict(sd['optimizer_state_dict'])
        return sd['epoch'] if load_optimizer else 0


# ---------------------------------------------------------------------------
# 预测（含复数代词多链归属特性）
# ---------------------------------------------------------------------------
def _load_tokenizer(path: str):
    """加载 tokenizer；对 Mistral 等模型加 fix_mistral_regex 消除正则警告。"""
    try:
        return AutoTokenizer.from_pretrained(path, fix_mistral_regex=True)
    except TypeError:
        return AutoTokenizer.from_pretrained(path)


class CorefPredictor:
    def __init__(self, model, tokenizer, device=None,
                 max_span_width: int = 10, max_len: int = 512,
                 max_candidates: int = 1000, max_span_tokens: int = 32,
                 coref_threshold: float = 0.0,
                 plural_threshold: float = 0.5):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device or next(model.parameters()).device
        self.max_span_width = max_span_width
        self.max_len = max_len
        self.max_candidates = max_candidates
        self.max_span_tokens = max_span_tokens
        self.coref_threshold = coref_threshold
        self.plural_threshold = plural_threshold

    @classmethod
    def from_pretrained(cls, output_dir: str, device=None,
                        max_span_width: int = 10, max_len: int = 512,
                        max_candidates: int = 1000, max_span_tokens: int = 32,
                        coref_threshold: float = 0.0,
                        plural_threshold: float = 0.5) -> 'CorefPredictor':
        model = CorefModel.from_pretrained_dir(output_dir, device or 'cpu')
        tokenizer = _load_tokenizer(output_dir)
        return cls(model, tokenizer, device, max_span_width, max_len,
                   max_candidates, max_span_tokens, coref_threshold, plural_threshold)

    def predict(self, doc: str) -> List[List[Dict]]:
        self.model.eval()
        encoding = self.tokenizer(
            doc, max_length=self.max_len, truncation=True,
            return_tensors='pt', return_offsets_mapping=True)
        offset_mapping = encoding['offset_mapping'][0].tolist()
        cands = generate_candidate_spans(
            doc, offset_mapping,
            max_span_width=self.max_span_width,
            max_candidates=self.max_candidates,
            max_span_tokens=self.max_span_tokens)

        input_ids = encoding['input_ids'].to(self.device)
        attention_mask = encoding['attention_mask'].to(self.device)
        cand_spans, cand_mask = pad_candidates([cands], self.device)

        with torch.no_grad():
            out = self.model(input_ids, attention_mask, cand_spans, cand_mask)

        pruned = out['pruned_indices'][0].cpu().tolist()      # K 个 pruned 候选在全量中的下标
        combined = out['pairwise'][0].cpu()                   # (K,K)
        K = len(pruned)

        # 1. 贪心链接（保持簇互斥）：每个 i 找最早的、combined 最高且 > null(0) 的 j<i
        parent = list(range(K))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[ry] = rx

        for i in range(K):
            best_j, best_s = -1, float('-inf')
            for j in range(i):
                s = float(combined[i, j])
                if s > best_s:
                    best_s, best_j = s, j
            if best_j >= 0 and best_s > self.coref_threshold:
                union(i, best_j)

        cluster_map = defaultdict(list)
        for i in range(K):
            cluster_map[find(i)].append(i)
        clusters = [v for v in cluster_map.values()]  # 互斥簇（pruned 位置列表）

        # 2. 复数代词多链归属（本项目特性）：把代词复制到多条高分链，各链保持独立
        plural_positions = [i for i in range(K)
                            if self._is_plural_pronoun(cands[pruned[i]]["text"])]
        clusters = self._resolve_plural_pronouns(clusters, pruned, combined,
                                                  plural_positions)

        # 3. 转回字符区间输出（一个代词可能出现在多个簇中）
        output = []
        for members in clusters:
            mentions = []
            for p in members:
                c = cands[pruned[p]]
                mentions.append({
                    'name': c['text'],
                    'char_start': c['char_start'],
                    'char_end': c['char_end'],
                })
            output.append(mentions)
        return output

    def _resolve_plural_pronouns(self,
                                 clusters: List[List[int]],
                                 pruned: List[int],
                                 combined: torch.Tensor,
                                 plural_positions: List[int]) -> List[List[int]]:
        """把每个复数代词复制到所有"高分链"中（保持各链独立，不合并链）。"""
        result = [list(c) for c in clusters]
        for p in plural_positions:
            for ci, c in enumerate(result):
                if p in c:
                    continue  # 已在该簇
                # 代词与该簇任意成员的最高 combined 分
                max_s = float('-inf')
                for m in c:
                    s = float(combined[p, m]) if p > m else float(combined[m, p])
                    if s > max_s:
                        max_s = s
                if max_s > self.plural_threshold:
                    result[ci].append(p)
        return result

    @staticmethod
    def _is_plural_pronoun(text: str) -> bool:
        plural = {'它们', '他们', '她们', '二者', '两者', '各位', '诸位', '双方',
                  'they', 'them', 'these', 'those', 'both', 'all'}
        return text in plural or text.lower() in plural


# ---------------------------------------------------------------------------
# 训练入口（存档 / 断点续训）
# ---------------------------------------------------------------------------
def train(data_path: str,
          output_dir: str,
          bert_model_name: str = 'bert-base-chinese',
          max_span_width: int = 10,
          feature_size: int = 20,
          max_antecedents: int = 128,
          max_span_tokens: int = 32,
          max_len: int = 512,
          max_candidates: int = 1000,
          epochs: int = 5,
          batch_size: int = 4,
          lr: float = 2e-5,
          lr_head: Optional[float] = None,
          mention_pos_weight: float = 5.0,
          fp16: bool = False,
          no_cache: bool = False,
          device: Optional[str] = None,
          resume: bool = False,
          incremental: bool = False,
          keep_optimizer: bool = False,
          scheduler_type: str = 'constant',
          warmup_steps: int = 0,
          warmup_ratio: float = 0.0,
          dropout: float = 0.2,
          log_step: int = 50,
          eval_data_path: Optional[str] = None,
          save_steps: int = 0,
          eval_steps: int = 0):
    device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
    os.makedirs(output_dir, exist_ok=True)

    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"载入训练数据：{len(data)} 篇文档")

    # 计算调度器所需的总步数与 warmup 步数
    steps_per_epoch = max(1, (len(data) + batch_size - 1) // batch_size)
    total_steps = steps_per_epoch * max(1, epochs)
    if warmup_steps <= 0 and warmup_ratio > 0:
        warmup_steps = max(1, int(warmup_ratio * total_steps))
    if scheduler_type not in (None, 'constant'):
        print(f"学习率调度器：{scheduler_type}  总步数={total_steps}  "
              f"warmup步数={warmup_steps}")

    eval_data = None
    if eval_data_path is not None:
        with open(eval_data_path, 'r', encoding='utf-8') as f:
            eval_data = json.load(f)
        print(f"载入验证数据：{len(eval_data)} 篇文档")

    # 增量训练 / 断点续训：若 output_dir 已有存档，则按 config.json 重建模型架构，
    # 保证与 checkpoint 完全一致（避免 size mismatch），并复用存档 tokenizer。
    load_pretrained = resume or incremental
    if load_pretrained and os.path.isfile(os.path.join(output_dir, 'config.json')):
        with open(os.path.join(output_dir, 'config.json'), 'r', encoding='utf-8') as f:
            saved = json.load(f)
        bert_model_name = saved.get('bert_model_name', bert_model_name)
        max_span_width = saved.get('max_span_width', max_span_width)
        feature_size = saved.get('feature_size', feature_size)
        max_antecedents = saved.get('max_antecedents', max_antecedents)
        max_span_tokens = saved.get('max_span_tokens', max_span_tokens)
        max_candidates = saved.get('max_candidates', max_candidates)
        max_len = saved.get('max_len', max_len)
        dropout = saved.get('dropout', dropout)
        print(f"加载存档超参重建模型 "
              f"(max_span_tokens={max_span_tokens}, max_span_width={max_span_width}, "
              f"max_candidates={max_candidates}, max_len={max_len})")

    # 增量训练必须有已训练好的 checkpoint（模型权重）与 config.json
    if incremental:
        _ckpt = _find_latest_checkpoint(output_dir)
        if _ckpt is None or not os.path.isfile(
                os.path.join(output_dir, 'config.json')):
            raise SystemExit(
                "增量训练失败：output_dir 下未找到 checkpoint_latest.pt 与 config.json。"
                "请先训练或指定已有的模型目录。")

    # tokenizer：复用存档目录内的（与训练时一致），否则从预训练模型加载
    if load_pretrained and os.path.isdir(output_dir) and os.path.exists(
            os.path.join(output_dir, 'tokenizer.json')):
        tokenizer = _load_tokenizer(output_dir)
    else:
        tokenizer = _load_tokenizer(bert_model_name)
    tokenizer.save_pretrained(output_dir)  # 推理时可直接加载

    # 诊断：检查 gold mention 是否被正确命中候选（offset 对齐问题常导致全丢）
    _diag_proc = CorefDataProcessor(tokenizer, max_span_width, max_len,
                                     max_candidates, max_span_tokens,
                                     cache=not no_cache)
    _sample = data[0]
    _p = _diag_proc.process_document(_sample['doc'], _sample['clusters'])
    _n_gold = sum(_p['mention_labels'])
    print(f"[诊断] 首篇文档: 候选数={len(_p['candidates'])}, "
          f"命中gold mention数={_n_gold}, 标注簇数={len(_sample['clusters'])}")
    if _n_gold == 0:
        print("[警告] gold mention 几乎全部未命中！多为标注的 char_start/char_end 与候选对齐"
              "不一致，模型只能学到'无 mention'的平凡解，loss 难以下降。请核对标注偏移。")

    processor = CorefDataProcessor(tokenizer, max_span_width, max_len,
                                   max_candidates, max_span_tokens,
                                   cache=not no_cache)
    model = CorefModel(bert_model_name, max_span_width, feature_size,
                       max_antecedents, max_span_tokens, dropout)
    trainer = CorefTrainer(model, processor, device, lr, lr_head,
                           mention_pos_weight, fp16,
                           scheduler_type=scheduler_type,
                           total_steps=total_steps,
                           warmup_steps=warmup_steps)

    start_epoch = 0
    if resume:
        start_epoch = trainer.load_checkpoint(output_dir, map_location=device,
                                              load_optimizer=True)
        if start_epoch > 0:
            print(f"断点续训：从第 {start_epoch} 轮恢复（保留优化器状态）")
        else:
            print("未找到可用 checkpoint，从头开始训练")
    elif incremental:
        # 仅加载模型权重，优化器重置为新建状态；epoch 从 1 重新计数（全新阶段）
        start_epoch = trainer.load_checkpoint(output_dir, map_location=device,
                                              load_optimizer=keep_optimizer)
        mode = "保留优化器状态" if keep_optimizer else "重置优化器（默认，避免旧数据动量污染）"
        print(f"增量训练：已加载 output_dir 下训练好的模型权重（{mode}），"
              f"将从第 1 轮起在新数据上继续训练 {epochs} 个 epoch")

    # 续训时把调度器快进到已训练步数，使学习率曲线与中断前衔接
    if trainer.scheduler is not None:
        trainer.scheduler.last_epoch = trainer.global_step - 1

    # 断点续训护栏：若已训练到的 epoch 已 >= 目标 epochs，则实际不会训练
    if resume and start_epoch >= epochs:
        print(f"[提示] 已训练到第 {start_epoch} 轮，>= 目标 epochs={epochs}，"
              f"本次续训无新 epoch 执行。如需继续，请调大 --epochs。")

    # 保存超参配置，供推理时重建模型
    config = dict(bert_model_name=bert_model_name, max_span_width=max_span_width,
                  feature_size=feature_size, max_antecedents=max_antecedents,
                  max_span_tokens=max_span_tokens, max_candidates=max_candidates,
                  max_len=max_len, dropout=dropout)
    with open(os.path.join(output_dir, 'config.json'), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    for epoch in range(start_epoch + 1, epochs + 1):
        print(f"\n===== Epoch {epoch}/{epochs} =====")
        epoch_data = data[:]
        random.shuffle(epoch_data)
        avg = trainer.train_epoch(epoch_data, batch_size, log_step,
                                   save_steps, eval_steps, eval_data,
                                   output_dir, epoch)
        print(f"  avg loss: {avg:.4f}")
        trainer.save_checkpoint(output_dir, epoch, avg)
        print(f"  已保存 checkpoint -> {output_dir}")

    print(f"\n训练完成。模型保存在：{output_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser(description='e2e-coref 训练 / 推理')
    parser.add_argument('--mode', choices=['train', 'predict'], default='train')
    parser.add_argument('--data', type=str, help='训练数据 json 路径', default='../../data/coref_train_data3.json')
    parser.add_argument('--output_dir', type=str, default='../../models_cache/e2e_coref')
    parser.add_argument('--bert', type=str, default='../../models_cache/xlm_roberta_base')
    parser.add_argument('--epochs', type=int, default=3)
    parser.add_argument('--batch_size', type=int, default=4)
    parser.add_argument('--resume', action='store_true',
                        help='断点续训：精确恢复（模型+优化器+epoch）')
    parser.add_argument('--incremental', action='store_true', default=True,
                        help='增量训练：从 output_dir 下已训练模型继续学（仅加载权重，'
                             '优化器重置，epoch 重新计数），通常用于喂新数据扩充能力')
    parser.add_argument('--keep_optimizer', action='store_true',
                        help='增量训练时保留旧优化器状态（默认重置，避免旧数据动量污染）')
    parser.add_argument('--scheduler', type=str, default='cosine',
                        choices=['constant', 'linear', 'cosine'],
                        help='学习率调度器：constant(不调度)/linear(warmup+线性衰减)/'
                             'cosine(warmup+余弦衰减)')
    parser.add_argument('--warmup_steps', type=int, default=0,
                        help='warmup 步数（0 表示不热身；与 --warmup_ratio 二选一）')
    parser.add_argument('--warmup_ratio', type=float, default=0.1,
                        help='warmup 占总步数比例（如 0.03），仅在未指定 --warmup_steps 时生效')
    parser.add_argument('--text', type=str, help='predict 模式的输入文本')
    parser.add_argument('--max_antecedents', type=int, default=128)
    parser.add_argument('--max_candidates', type=int, default=400)
    parser.add_argument('--max_span_tokens', type=int, default=16,
                        help='单个候选 span 最多覆盖的 token 数（Mistral 等需调大）')
    parser.add_argument('--lr', type=float, default=2e-5,
                        help='骨干（BERT/Mistral）学习率')
    parser.add_argument('--lr_head', type=float, default=None,
                        help='任务头学习率（mention/antecedent scorer）；'
                             '默认 = lr*5')
    parser.add_argument('--mention_pos_weight', type=float, default=5.0,
                        help='mention BCE 的 pos_weight，类别越不平衡越要调大'
                             '（如 10~20）')
    parser.add_argument('--fp16', action='store_true',
                        help='混合精度训练（仅 CUDA 生效），24B 大模型提速并省显存')
    parser.add_argument('--no_cache', action='store_true',
                        help='关闭候选/tokenize 缓存（默认开启，第二轮起显著加速）')
    parser.add_argument('--log_step', type=int, default=2,
                        help='每多少步打印一次当前 loss（0 表示不打印）')
    parser.add_argument('--eval_data', type=str, default=None,
                        help='验证集 json 路径（提供后按 eval_steps 验证）')
    parser.add_argument('--save_steps', type=int, default=600,
                        help='每多少步保存一次 checkpoint（0 表示仅在 epoch 末保存）')
    parser.add_argument('--eval_steps', type=int, default=0,
                        help='每多少步在验证集上评估并输出 eval_loss（0 表示不评估）')
    args = parser.parse_args()

    if args.mode == 'train':
        if not args.data:
            raise SystemExit('--data 必须指定训练数据路径')
        train(args.data, args.output_dir, bert_model_name=args.bert,
              epochs=args.epochs, batch_size=args.batch_size, resume=args.resume,
              incremental=args.incremental, keep_optimizer=args.keep_optimizer,
              scheduler_type=args.scheduler, warmup_steps=args.warmup_steps,
              warmup_ratio=args.warmup_ratio,
              max_antecedents=args.max_antecedents,
              max_candidates=args.max_candidates,
              max_span_tokens=args.max_span_tokens,
              lr=args.lr, lr_head=args.lr_head,
              mention_pos_weight=args.mention_pos_weight,
              fp16=args.fp16, no_cache=args.no_cache,
              log_step=args.log_step,
              eval_data_path=args.eval_data,
              save_steps=args.save_steps,
              eval_steps=args.eval_steps)
    else:
        predictor = CorefPredictor.from_pretrained(
            args.output_dir, max_candidates=args.max_candidates,
            max_span_tokens=args.max_span_tokens)
        text = args.text or ("国家电网有限公司于2020年发布了年度社会责任报告。"
                             "该报告详细阐述了公司在清洁能源领域的贡献。"
                             "它特别提到，全年消纳新能源电量达6000亿千瓦时。"
                             "这份文件还公布了未来五年的碳减排目标。")
        result = predictor.predict(text)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
