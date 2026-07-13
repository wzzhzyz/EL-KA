# Challenge Dev 残差分析：人称类型约束与跨句缓存决策

## 1. 范围

本报告分析 P0 后 `challenge_dev` 的 7 条失败：18 / 25 已正确，剩余 7 / 25 未正确。没有修改共指代码、测试数据、gold 或阈值；多协调组仍保持“最近协调组优先”。`CORE_COL_EVAL_123` 固定归类为 `semantic_ambiguity_no_safe_rule`，不修改其 gold，也不为该文本写特例。

## 2. 逐条残差

|Sample|目标|Gold / 预测 ID|NIL（gold / 预测）|规则|句距|前件类型|主根因|安全通用规则|
|-|-|-|-|-:|-|-|-|-|
|`071`|双方|国家电网、南方电网 / `[]`|false / true|`collective_unresolved`|2|ORG、ORG|`cross_sentence_state_loss`|否|
|`074`|它们|微信、腾讯会议 / `[]`|false / true|`collective_unresolved`|0|CONSUMER_PRODUCT、CONSUMER_PRODUCT|`anaphor_type_mismatch`|否|
|`075`|她们|`[]` / 国家电网、南方电网|true / false|`collective_coordinated_antecedents`|0|ORG、ORG|`person_type_constraint`|是，局部|
|`106`|双方|国家电网、南方电网 / `[]`|false / true|`collective_unresolved`|1|ORG、ORG|`cross_sentence_state_loss`|否|
|`107`|双方|华能集团、三峡集团 / `[]`|false / true|`collective_unresolved`|2|ORG、ORG|`cross_sentence_state_loss`|否|
|`123`|双方|`[]` / 华为、腾讯|true / false|`collective_coordinated_antecedents`|0|ORG × 4|`semantic_ambiguity_no_safe_rule`|否|
|`124`|她们|`[]` / 国家电网、南方电网|true / false|`collective_coordinated_antecedents`|0|ORG、ORG|`person_type_constraint`|是，局部|

完整文本、evidence、次级错误分类、风险和处理建议见 [JSON 残差报告](coreference_challenge_residual_analysis.json)。

## 3. 根因汇总

|根因|数量|占剩余失败比例|是否可用低风险规则修复|推荐优先级|
|-|-:|-:|-|-|
|`cross_sentence_state_loss`（同时标记 `cross_sentence_window_failure`）|3|42.86%|否，当前存在对照冲突|P1，暂缓|
|`person_type_constraint`|2|28.57%|部分，是局部约束|P2|
|`anaphor_type_mismatch`（产品集合范围）|1|14.29%|否|P3|
|`semantic_ambiguity_no_safe_rule`（同时标记 `wrong_coordinated_group`）|1|14.29%|否|已知边界|
|`implicit_discourse_reasoning`|0（`107` 为次级因素）|0.00%|否|未观察到主因|
|`complex_ellipsis`|0|0.00%|否|未观察到主因|

错误结果形态为：`false_nil` 4 条（071、074、106、107），`false_positive_collective` 3 条（075、123、124）；没有 `under_prediction`、`over_prediction` 或 `wrong_entity_set` 残差。

## 4. 两项候选优化的安全性

### 人称 / 类型约束

- 人称类型问题为 2 条（075、124）；若将“她们”限制为仅回指 PERSON 组，预计修复 2 条 false positive。
- 这是残差中风险最低的代码变更，但未达到“至少 3 条”优先门槛。
- 可能影响未来 PERSON 集合能力；当前运行 KB 没有可用 PERSON 正例。对历史 257 条、正式集合主集预计影响小，但仍必须完整回归，并重点观察集合 NIL。

### 最多跨两句协调组缓存

- 跨句状态 / 窗口问题为 3 条（071、106、107），数量达到优先门槛，理论收益为 3 条。
- 但 `106` 与当前**正确**的 `122` 都是“前一句明确双实体协调组 + 下一句双方”，句距同为 1；gold 分别为正例和 NIL。单靠窗口、协调词、类型和实体位置无法安全区分。
- `072`、`116` 是主体切换后正确 NIL 对照，`125` 是三句距离正确 NIL 对照。缓存即使限制两句，也需要篇章主体判断，已超出当前局部规则可靠范围。
- 因此直接实施缓存会有明确的 false positive / NIL 下降风险，不建议在本轮实现。

## 5. 决策

1. 人称或类型问题：3 条（其中严格的人称类型约束为 2 条，产品类型范围为 1 条）。
2. 跨句状态或窗口问题：3 条。
3. 多协调组语义歧义：1 条（`123`）。
4. 隐式篇章推理或复杂省略：无主因；`107` 对篇章连续性有次级依赖。
5. 覆盖最多的是跨句状态丢失（3 / 7）。
6. 风险最低的是人称类型约束，但仅修复 2 条且未达优先门槛。
7. 跨句缓存理论修复 3 条，但无安全局部规则；人称类型约束理论修复 2 条。
8. 跨句缓存可能影响当前正确的集合 NIL（至少 `122`，并可能波及 `072`、`116`）；人称约束对历史 257 和主集预计影响小，但仍须全量回归。

结论：当前不值得进入下一轮规则修改。建议冻结 P0，保留 7 条残差为边界证据，转入独立 `blind_holdout` 建设；若后续确需继续优化，应先引入可验证的话语主体 / 事件语义信号，而不是继续堆叠局部规则。
