# 歧义拒绝器跨领域鲁棒性分析

## 1. 范围

本轮只运行 `Challenge Dev v2` 的离线实验；未改正式 Pipeline、共指规则、API 或 gold，也未运行任何 blind holdout。新增 `robustness_domain_pilot` 为 16 条文本 / 16 个 case，覆盖能源、金融、互联网、交通、医疗与媒体，每个领域至少包含 1 条正例和 1 条 NIL。

## 2. 新增子集结果

|方案|总体|正例|NIL|False Rejection|False Positive|
|-|-:|-:|-:|-:|-:|
|Baseline|10 / 16|8 / 8|2 / 8|0|6|
|`nearest_group_with_ambiguity_rejection`|16 / 16|8 / 8|8 / 8|0|0|

拒绝器在新增开发子集修复 6 个 baseline false positive，未引入 false rejection。该结果说明“最近组默认 + 强歧义拒绝”在六个已覆盖领域的当前表达下工作稳定；它不是独立泛化证明。

## 3. 按领域统计（拒绝器）

|领域|样本数|正例准确率|NIL 准确率|总体|False Rejection|False Positive|
|-|-:|-:|-:|-:|-:|-:|
|Energy|3|2 / 2|1 / 1|3 / 3|0|0|
|Finance|3|2 / 2|1 / 1|3 / 3|0|0|
|Internet|3|1 / 1|2 / 2|3 / 3|0|0|
|Transportation|2|1 / 1|1 / 1|2 / 2|0|0|
|Healthcare|3|1 / 1|2 / 2|3 / 3|0|0|
|Media|2|1 / 1|1 / 1|2 / 2|0|0|

至少 4 个领域有相对 baseline 的正向 NIL 收益：能源、金融、互联网、交通、医疗、媒体均有；新增集无领域特例或 sample ID / 实体名硬编码。

## 4. 误报与漏报

本轮新增子集的拒绝器错误记录为空：

|类别|数量|说明|
|-|-:|-|
|`false_rejection`|0|正例未被错误拒绝。|
|`missed_ambiguity`|0|新增 NIL 未被错误强选。|
|`subject_switch_false_alarm`|0|含主体切换词的正例未被误拒绝。|
|`event_reset_false_alarm`|0|含“与此同时”等重置信号的正例未被误拒绝。|
|`domain_specific_failure`|0|新增六领域未观察到领域独有失败。|

完整 v2 仍存在 7 个 false positive 与 4 个 false NIL，主要来自旧子集的跨句边界、缺少显式切换证据的同句歧义和错误实体集合；不能将新增子集的 100% 外推为全系统能力。

## 5. 继续条件判断

相对 55 条 baseline，拒绝器由 32 / 55 提升至 42 / 55（+10），正例正确数保持 24 / 30，NIL 正确数由 8 / 25 提升至 18 / 25。满足本轮开发集继续门槛：提升不少于 5、正例损失 0、NIL 不下降、新增子集不少于 80%、六领域均有正向收益。

结论：**PROMISING（仅限离线开发实验）**。可进入“可选实验分支接入”的评审，但在独立、未参与规则设计的 holdout 验证前，不应接入正式 Pipeline。
