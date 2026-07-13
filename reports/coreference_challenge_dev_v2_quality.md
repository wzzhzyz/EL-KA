# Challenge Dev v2 数据质量检查

## 1. 检查范围

- 数据文件：`data/eval/coreference_challenge_dev_v2.json`
- 当前规模：39 条文本、39 个集合共指 case。
- 子集：原跨句 pilot 12 条；同句候选竞争 pilot 19 条；歧义拒绝配对 pilot 8 条。
- 数据定位：开发阶段的离线实验集，不是 blind holdout。

## 2. 标注与知识库检查

|检查项|结果|
|-|-:|
|JSON 结构与必填元数据|通过|
|`[start, end)` mention 偏移|39 / 39 正确|
|正例 gold `entity_ids` 存在于运行知识库|22 / 22|
|NIL 的 `entity_ids=[]` 与空 `antecedent_indices`|17 / 17|
|正例 / NIL 标签一致性|39 / 39|
|检查错误数|0|

所有正例均使用 `data/kb/energy_entities.json` 中存在的运行知识库 ID，未使用 `TEST_*`、`PER_TEST_*` 或其他夹具 ID。

## 3. 独立性检查

比较范围为 `data/eval/` 下除本文件外、包含 `samples` 的 JSON 数据集。文本去空白后执行精确匹配和 `difflib.SequenceMatcher` 近重复检查。

|检查项|规则|结果|
|-|-|-:|
|精确重复|归一化文本完全相同|0|
|近重复|文本相似度 `>= 0.80`|0|
|v2 内部近重复|任意两条 v2 文本相似度 `>= 0.80`|0|
|gold 冲突|相同文本对应不同 `expected_coreferences`|0|

新增样例未复制 Acceptance Main、Challenge Dev v1、Blind Holdout v1 或 failure regression 的文本。

## 4. 子集与覆盖情况

|子集|文本 / case|正例|NIL|主要覆盖|
|-|-:|-:|-:|-|
|`cross_sentence_pilot`|12 / 12|6|6|跨一句、跨两句、主体/事件切换、跨句多组竞争、产品与人称边界。|
|`same_sentence_candidate_pilot`|19 / 19|12|7|单协调组、三实体组、两协调组最近组、多协调组歧义、类型/数量不匹配。|
|`ambiguity_rejection_pilot`|8 / 8|4|4|最近组显式持续与新主体/事件切换的严格配对。|
|合计|39 / 39|22|17|跨句边界、同句候选竞争与歧义拒绝。|

新增同句子集覆盖：4 条单协调组正例、4 条三实体正例、4 条多协调组最近组正例、4 条多协调组歧义 NIL、2 条类型不匹配 NIL 与 1 条数量不匹配 NIL。每条样例均含 `scenario`、`difficulty`、`requires_discourse_reasoning`、`expected_resolution_basis` 和 `annotation_evidence`。

## 5. 结论与边界

当前 39 条 v2 数据均通过结构、偏移、知识库引用、重复和 gold 冲突检查。同句子集可用于候选协调组暴露、可解释评分和歧义拒绝验证；跨句子集继续用于记录现有同句规则的边界。

本轮未修改既有 gold、Acceptance Main、Challenge Dev v1、Blind Holdout v1 或正式 API；没有运行任何 blind holdout。

## 6. 第二轮跨领域扩充（本轮状态）

本轮新增 `robustness_domain_pilot` 16 条文本 / 16 个 case，使 v2 当前规模为 **55 条文本、55 个 case**：正例 30 条、NIL 25 条。新增数据覆盖 Energy、Finance、Internet、Transportation、Healthcare、Media；每个领域均至少有 1 条正例和 1 条 NIL，并包含主体持续、主体切换、切换词误导正例、新实体未切换、三实体及四实体集合场景。

全量偏移复核结果为 **55 / 55 正确**，新增正例均引用运行知识库中的实体 ID，新增数据的精确重复为 0、gold 冲突为 0。内部近重复扫描仍发现 6 对结构相似的开发对照文本（主体持续 / 主体切换成对设计），因此“内部近重复 = 0”的旧结论不再适用；这些对照不与 Acceptance Main、Challenge Dev v1 或 Blind Holdout 重复，但后续若将 v2 用作正式泛化集，应改写其中的共用模板并重新审计。

## 7. 去模板化复核结果

已对上述 6 对中的新增侧文本完成语义保持型改写，并重新执行 `SequenceMatcher >= 0.80` 内部近重复检查：**0 对**。改写未改变 gold `entity_ids`、NIL 标签、`antecedent_indices` 或实体 ID；全量偏移错误仍为 **0**。逐对改写说明见 `reports/coreference_near_duplicate_rewrite_review.md`。本节结果覆盖第 6 节中“内部近重复仍为 6 对”的历史记录。
