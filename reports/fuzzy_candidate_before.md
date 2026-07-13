# Fuzzy Candidate 优化前逻辑审计

## 当前逻辑

`entity_linker/pipeline.py` 中的 `_LocalKnowledgeBase.get_entities_by_alias_fuzzy()` 遍历本地 alias 索引；对每个 alias 仅执行双向包含判断：

```python
if mention in candidate_alias or candidate_alias in mention:
    # 返回该 alias 对应实体
```

`_FallbackCandidateGenerator.generate()` 先保留精确 alias 候选（0.95），再把所有 fuzzy 候选以固定 0.85 和 `alias_fuzzy` 方法写入候选列表。fuzzy 返回顺序来自 alias 索引遍历，未按照实际相似度排序。

## NIL 流程

candidate generator 不进行 NIL 判断。完整 pipeline 在消歧后以 `score < nil_threshold` 判定 NIL；fallback 默认阈值为 0.90。因此固定 0.85 fuzzy 候选在默认完整 fallback 流程中理论上会被拒绝，但 alias 专项评测器当前衡量的是候选路径是否返回实体，故将其记为负例误召回。

## 风险点

- 无最小 alias 长度：`北京`、`深圳`、`上交`、`国能`等短字符串可触发子串候选；
- 无长度比例：长 mention 与短局部 alias 也被视为同等 fuzzy 证据；
- 无编辑距离或可解释相似度：0.85 是固定值，不代表真实相似度；
- 无 entity type/context 输入：医院、高校可因包含地名进入 REGION 候选，校园语境可进入证券候选；
- 无 fuzzy 排序：候选顺序取决于索引插入顺序；
- metadata 只记录 `match_type=alias_fuzzy`，无法回答命中了哪条 alias、为何得分。

## 修改位置

本次低风险优化仅应修改：

1. `_LocalKnowledgeBase.get_entities_by_alias_fuzzy()`：增加 containment 过滤、分数和匹配证据；
2. `_FallbackCandidateGenerator.generate()`：保留精确路径不变，消费 fuzzy 的分数/metadata 并按分数排序。

不修改测试集、gold、NIL 阈值、实体类型契约或主 pipeline 结构。
