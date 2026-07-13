# 集合共指篇章状态离线实验（首轮）

## 1. 实验范围

- 仅使用 Challenge Dev v2 的 55 条文本 / case；不含任何 blind holdout。
- 未运行或读取任何 blind holdout；未修改正式规则、API、gold、阈值，也未使用 BGE/FAISS。
- 这是 pilot sample，结果仅用于方向判断，不能视为稳定统计结论。

## 2. 候选暴露验证

- 候选组总数：70
- 含候选的 case：42
- 多候选 case：28
- 三实体候选：10
- 候选提取异常：0
- Baseline 与 `nearest_group_only`：一致。

当前候选提取严格复用正式规则的同句约束，因此跨句 case 没有候选是预期边界，不是数据错误。

## 3. 方案对比

|方案|总体|正例|NIL|False NIL|False Positive|Wrong Entity Set|
|-|-:|-:|-:|-:|-:|-:|
|`baseline_current_rule`|60.00%|80.00%|36.00%|4|16|2|
|`nearest_group_only`|60.00%|80.00%|36.00%|4|16|2|
|`recency_and_cardinality`|61.82%|30.00%|100.00%|21|0|0|
|`discourse_features`|65.45%|73.33%|56.00%|8|11|0|
|`nearest_group_with_ambiguity_rejection`|76.36%|80.00%|72.00%|4|7|2|

## 4. 分 Pilot 子集结果

### `ambiguity_rejection_pilot`

|方案|总体|正例|NIL|False NIL|False Positive|
|-|-:|-:|-:|-:|-:|
|`baseline_current_rule`|50.00%|100.00%|0.00%|0|4|
|`nearest_group_only`|50.00%|100.00%|0.00%|0|4|
|`recency_and_cardinality`|50.00%|0.00%|100.00%|4|0|
|`discourse_features`|62.50%|100.00%|25.00%|0|3|
|`nearest_group_with_ambiguity_rejection`|100.00%|100.00%|100.00%|0|0|

### `cross_sentence_pilot`

|方案|总体|正例|NIL|False NIL|False Positive|
|-|-:|-:|-:|-:|-:|
|`baseline_current_rule`|33.33%|0.00%|66.67%|4|2|
|`nearest_group_only`|33.33%|0.00%|66.67%|4|2|
|`recency_and_cardinality`|50.00%|0.00%|100.00%|6|0|
|`discourse_features`|50.00%|0.00%|100.00%|6|0|
|`nearest_group_with_ambiguity_rejection`|33.33%|0.00%|66.67%|4|2|

### `robustness_domain_pilot`

|方案|总体|正例|NIL|False NIL|False Positive|
|-|-:|-:|-:|-:|-:|
|`baseline_current_rule`|68.75%|100.00%|37.50%|0|5|
|`nearest_group_only`|68.75%|100.00%|37.50%|0|5|
|`recency_and_cardinality`|56.25%|12.50%|100.00%|7|0|
|`discourse_features`|62.50%|75.00%|50.00%|2|4|
|`nearest_group_with_ambiguity_rejection`|100.00%|100.00%|100.00%|0|0|

### `same_sentence_candidate_pilot`

|方案|总体|正例|NIL|False NIL|False Positive|
|-|-:|-:|-:|-:|-:|
|`baseline_current_rule`|73.68%|100.00%|28.57%|0|5|
|`nearest_group_only`|73.68%|100.00%|28.57%|0|5|
|`recency_and_cardinality`|78.95%|66.67%|100.00%|4|0|
|`discourse_features`|78.95%|100.00%|42.86%|0|4|
|`nearest_group_with_ambiguity_rejection`|73.68%|100.00%|28.57%|0|5|

## 5. 跨领域结果（歧义拒绝器）

|领域|正例准确率|NIL 准确率|总体|False Rejection|False Positive|
|-|-:|-:|-:|-:|-:|
|`Energy`|100.00%|100.00%|100.00%|0|0|
|`Finance`|100.00%|100.00%|100.00%|0|0|
|`Healthcare`|100.00%|100.00%|100.00%|0|0|
|`Internet`|100.00%|100.00%|100.00%|0|0|
|`Media`|100.00%|100.00%|100.00%|0|0|
|`Transportation`|100.00%|100.00%|100.00%|0|0|

## 6. 阈值扫描

- `recency_and_cardinality`：`select_threshold=0.80`，`margin_threshold=0.30`。
- `discourse_features`：`select_threshold=0.90`，`margin_threshold=0.00`。
- `nearest_group_with_ambiguity_rejection`：`candidate_score_gap=1.00`，`minimum_evidence_count=3`。

## 7. 可行性判断

**PROMISING**：相对 baseline 多正确至少 3 条，正例损失不超过 1 条且 NIL 未下降；仅建议继续扩充开发集验证。

## 8. 主要限制

- 候选暴露刻意不跨句扩展，无法修复跨句 false NIL。
- 词面 bigram overlap 与主体切换词仅为无模型近似，不能替代句法或语义分析。
- 新增领域 pilot 是开发集，不能替代未参与设计的独立盲测。
