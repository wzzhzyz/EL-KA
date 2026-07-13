# Alias Normalization 专项测试集现状分析

## 1. 分布统计

当前 `data/eval/alias_normalization_test.json` 共 120 条，覆盖 81 个标准实体（运行知识库 158 个实体的 51.3%）和全部 17 个实体类型。

|alias_type|数量|
|-|-:|
|short_name|35|
|abbreviation|20|
|nickname|16|
|english_name|15|
|former_name|14|
|industry_alias|10|
|regional_alias|10|

难度分布为 easy 49（40.8%）、medium 51（42.5%）、hard 20（16.7%）。所有样本均为正例，`is_negative=true` 的样本为 0；20 条样本的 `is_ambiguous=true`，但尚无真实多候选字段。

实体类型虽全部覆盖，但抽样并不均衡：TECHNICAL_TERM 18 条、REGION 17 条，TRANSPORTATION_ORG 3 条、CONSUMER_PRODUCT 4 条、MEDIA_ORG 4 条。专项验收应保留现有广度，但后续困难补充应优先照顾低样本类型。

## 2. Context 与候选信息审计

当前 120 条中：

- `candidate_entities`：0 条具备；
- `expected_candidate_rank`：0 条具备；
- `ambiguity_type`：0 条具备；
- `is_negative`：0 条具备；
- 真实多候选样本：0 条。

文本共使用 21 种模板，单模板最多 12 条，未出现大量完全同句的模板堆叠；但所有上下文均为通用“材料提及/项目文件/公开报道”句式，无法区分两个候选实体。所有 `evidence` 都只是“该名称直接收录于知识库 alias”型来源说明，适合证明可追溯性，却不能证明候选排序或上下文消歧能力。

## 3. 当前 100% 的含义与边界

当前评测器调用项目本地 `_LocalKnowledgeBase` 与 `_FallbackCandidateGenerator`。测试 mention 均直接来自同一运行知识库的 aliases 或 abbreviation，因此 120/120 的 Top-1 结果证明的是：**当前运行 KB 的已登记 alias 可以被本地 alias lookup/candidate 路径回收并映射到 canonical entity**。

该结果不能单独证明以下能力：

1. 同一 alias 的多候选上下文选择；
2. 看似 alias 但 KB 不存在时的拒绝标准化；
3. 产品/公司、母子公司、区域/机构等相近候选的排序；
4. 拼写错误的纠正能力（KB 没有可验证 typo alias，不应虚构）。

## 4. 结论

第一版已可靠覆盖正向 alias→canonical entity 映射，也具备 ID、规范名称和 alias 来源可追溯性；但验收可信度仍主要来自“真实 KB 别名覆盖”，而不是复杂决策压力。下一版应在不删除、不重标现有 120 条的前提下，新增一组独立的困难正例与 hard NIL 负例，并引入候选、歧义和拒绝指标。
