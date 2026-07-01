# 别名匹配预期判定逻辑

> 版本: 1.0 | 用途: 候选生成召回率校验依据

---

## 1. 三层候选召回预期

| 层级 | 方法 | 预期命中条件 | 预期未命中 |
|------|------|------|------|
| L1 | alias_exact | mention 与 alias.name 完全相等 | 编辑距离≥1, NIL |
| L2 | alias_fuzzy | 编辑距离≤1 且 mention长度≥2 | 编辑距离≥2 |
| L3 | dense_vector | BGE余弦相似度≥0.6 | 语义无关 |

## 2. 匹配优先级

```
1. abbreviation 精确命中    → 最高优先 (priority=1.0)
2. alias.name 精确命中       → aliases[].priority 排序
3. alias_fuzzy 编辑距离=1    → priority × 0.8
4. dense_vector 语义匹配     → cosine_similarity
```

## 3. 预期判定表

| 场景 | mention | 预期L1 | 预期L2 | 预期L3 |
|------|------|:--:|:--:|:--:|
| 标准简称 | 国网 | ✅ | ✅ | ✅ |
| 英文缩写 | CATL | ✅ | ✅ | ✅ |
| OCR形近字 | 囯网 | ❌ | ✅ | ✅ |
| 异体字 | 宁徳时代 | ❌ | ✅ | ✅ |
| 非标别名 | 塔拉滩光伏基地 | ❌ | ✅ | ✅ |
| 不在KB | 工信部 | ❌ | ❌ | ❌(NIL) |
| 两字简称 | 清华 | ✅ | ✅ | ✅ |

## 4. 召回率计算公式

```
Recall@K = 正确召回样本数 / 总非NIL样本数

L1 Recall = alias_exact命中数 / 非NIL样本数
L2 Recall = (L1命中 + fuzzy命中) / 非NIL样本数
L3 Recall = (L1+L2 + dense命中) / 非NIL样本数
```

## 5. 预期指标

| 指标 | 目标 | 说明 |
|------|:--:|------|
| L1 精确召回率 | ≥85% | 大部分mention可精确命中 |
| L2 模糊召回率 | ≥95% | 补充OCR/异体字容错 |
| L3 语义召回率 | ≥98% | 兜底非标别名 |
| MRR | ≥0.80 | 平均倒数排名 |
