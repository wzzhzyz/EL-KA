# Blind Holdout v2 运行前质量审计

- 文本 / case：32 / 32；正例 20，NIL 12（62.5% / 37.5%）。
- 领域：Energy 4、Finance 5、Internet 5、Transportation 4、Healthcare 5、Media 4、Manufacturing 3、PublicService 2。
- JSON / Schema / 偏移 / 非 KB 正例 ID / 精确重复 / 内部近重复 / 外部近重复 / gold 冲突：均为 0。
- 外部比较范围：`data/eval` 中既有含 `samples` 的数据集，包括开发集、既有 blind、acceptance 与 failure regression。
- 人工复核：32 / 32，单人复核限制；多协调组、跨句、复杂 NIL 均列为重点复核。

结论：**READY_FOR_ONE_TIME_OFF_ON_EVALUATION**。本报告完成前未运行 OFF/ON 或任何 holdout 共指评测。
