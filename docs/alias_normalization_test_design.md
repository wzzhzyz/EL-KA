# Alias Normalization 专项测试集设计

## 1. 建设原因

“别名标准化召回率”是实体链接验收的独立指标。此前别名能力分散在运行知识库的 `aliases`、主链接集和候选召回集内，无法直接以“别名输入 → 标准实体 ID/标准名称”的单一口径计分。`data/eval/alias_normalization_test.json` 因此作为独立的专项验收集，同时保留主链接集兼容字段，便于接入已识别 mention 的实体链接流程。

## 2. 数据来源与边界

- 标准实体来源：`data/kb/energy_entities.json` 的 158 个运行实体。
- 输入别名来源：同一实体的 `aliases` 或 `abbreviation` 字段；不新增实体、不向 KB 写入别名。
- 样本均为正向标准化样本（`is_nil=false`），NIL 能力继续由既有 NIL 专项数据集验收。
- 所有 `expected_entity.entity_id` 和 `canonical_name` 均由运行 KB 反查确认。

## 3. Schema 说明

每条样本使用以下专项字段：

|字段|说明|
|-|-|
|`id`|连续样本 ID，例如 `ALIAS_001`|
|`text`、`mention`|包含待标准化别名的上下文及已识别指称|
|`mention_type`|固定为 `ALIAS`|
|`alias_type`|`abbreviation`、`short_name`、`former_name`、`english_name`、`nickname`、`industry_alias`、`regional_alias`、`typo_alias`|
|`entity_type`|运行 KB 中的原始实体类型|
|`expected_entity`|`entity_id` 与 `canonical_name`|
|`is_nil`、`has_nil`|当前均为 `false`|
|`difficulty`、`is_ambiguous`、`evidence`|验收分层、潜在歧义提示和可审计依据|

为兼容 `mention_linking_test.json`，每条还镜像 `mentions`（含字符位置）及 `expected_entities`。因此专项数据可由单 mention 评测器读取，也可转换至现有主链接集的已识别指称输入契约。

## 4. 数据分布

当前版本共 160 条：原始正向映射样本 120 条，另追加 20 条来源于既有 LLM 歧义集的候选压力正例，以及 20 条来源于既有 NIL 金标的 hard NIL 负例。

|alias_type|数量|
|-|-:|
|short_name|35|
|abbreviation|20|
|former_name|14|
|english_name|15|
|industry_alias|10|
|regional_alias|10|
|nickname|16|
|typo_alias|0|

新增 40 条全部标记为 `hard`。其中 20 条正例带有 `candidate_entities`、`expected_candidate_rank=1` 与 `ambiguity_type`；20 条负例带有 `is_negative=true`、`is_nil=true`、空值 `expected_entity` 和真实候选压力。原始 120 条的文本、mention 与 gold 标注均未修改。

`former_name` 为 14 条而非 15 条，是因为运行 KB 可用、且不等于标准名的“曾用名”只有 14 条；不为凑数增加未被 KB 证实的历史名称。`typo_alias` 是受支持的 schema 值，但运行 KB 没有已验证的错写 alias，故本版本不虚构该类数据。

样本按实体类型轮转抽取，覆盖电网、发电、技术术语、区域、科技、金融、教育、医疗、交通、媒体、产品与软件等多类实体；其中包含验收所需的 COMPANY/ORGANIZATION 类以及 MEDICAL、TRANSPORTATION、MEDIA、TECHNOLOGY、FINANCE 对应的原始 KB 类型。

## 5. 测试范围

本专项测试的是“已识别 alias mention → canonical entity”的标准化能力，以及在候选压力下的正例选择、在 alias-like NIL 输入下的拒绝行为。

不测试以下能力：

- NER 或通用实体发现；
- 不在文本中出现的实体检索；
- 长文本共指链解析；
- BGE/LLM 对候选列表的上下文重排效果。

## 6. 与其他验收项的区别

|指标|主要测试内容|
|-|-|
|实体链接|已识别 mention 在完整候选与链接链路中映射到实体|
|实体消歧|多候选实体基于上下文、模型分数或 LLM 证据选择正确目标|
|别名标准化|alias/简称/曾用名输入映射至 canonical entity，并验证负例拒绝|

因此，本测试集的 `candidate_entities` 是可审计的候选压力元数据；它不替代独立消歧集对上下文排序模型的测量。

## 7. 困难样本设计

原始 20 条 `hard` 样本选择短简称、常用称呼或行业术语，表示潜在歧义。追加的 20 条候选压力正例直接复用已有 LLM 歧义集的真实 alias、文本、候选实体和决定性证据，覆盖 `parent_child`、`same_type_similarity`、`regional_confusion` 与 `product_company_confusion`。追加的 20 条 hard NIL 负例复用既有 `expected_nil=true` 金标，并经运行 KB 的规范名称与 alias 索引双重复核后确认不存在。

当前运行 KB 没有多 owner alias，因此没有伪造 `same_alias` 的实体冲突；候选压力样本验证的是“真实 alias 加有来源相近候选”的验收场景。

## 8. 评测指标与运行方式

保留 Top-1 正向映射指标，并增加：

- **Positive Recall**：正例中 `predicted_entity_id == expected_entity.entity_id` 的比例；
- **Negative Precision**：`is_negative=true` 样本被候选路径正确拒绝（无返回实体）的比例；
- **Ambiguous Accuracy**：带显式候选列表的正例歧义样本中 Top-1 选择正确的比例；
- **Overall Accuracy**：正例映射正确与负例正确拒绝合并后的比例。

评测脚本调用项目的本地 `_LocalKnowledgeBase` 与 `_FallbackCandidateGenerator`，报告按 `alias_type`、`difficulty`、`entity_type` 分组输出：

```bash
python scripts/check_alias_normalization_data.py
python scripts/evaluate_alias_normalization.py
```

数据质量报告输出至 `reports/alias_data_quality_report.md`，评测结果输出至 `docs/alias_normalization_evaluation.md`。
