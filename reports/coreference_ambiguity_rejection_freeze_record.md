# 集合共指歧义拒绝实验分支冻结记录

- 配置位置：请求 `options.enable_collective_ambiguity_rejection`。
- 默认值：`false`。
- 共享逻辑：`entity_linker/collective_ambiguity.py`，由正式解析器和 runtime shadow 共同调用。
- 冻结阈值：`max_evidence_strength = 2`；须存在至少两个合法同句协调组、最近组数量合法、无显式主体持续，并存在主体切换或事件重置信号。
- OFF：与 runtime 基线 55 / 55 逐例一致。
- ON：与 runtime shadow 55 / 55 逐例一致，43 / 55；正例 27 / 30，NIL 16 / 25，False Positive 9，False NIL 1。
- 已知限制：`sentence_index` 缺失时按同句兼容处理，见 `reports/coreference_sentence_index_contract_review.md`。
- 本轮未创建或运行 blind holdout。
