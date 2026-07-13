# 共指消解最终冻结记录

- 默认配置：`enable_collective_ambiguity_rejection=true`；显式 `false` 保留历史最近协调组行为。
- 冻结阈值：`max_evidence_strength=2`。
- 正式统一验收：375 / 382（98.17%，PASS）。
- Blind Holdout v2：OFF 23 / 32，ON 29 / 32；正例 20 / 20 保持，NIL 3 / 12 → 9 / 12。
- 已知限制：`sentence_index` 输入契约、跨句篇章建模、深层多协调组语义歧义、规则特征边界、未接入模型、Holdout v2 单人复核限制。剩余 3 条 missed ambiguity 未修改或删除。
