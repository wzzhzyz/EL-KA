# 集合共指 P0 规则冻结记录

## 冻结信息

- 冻结日期：2026-07-13
- 当前 Git HEAD：`a28d44d`（工作区包含本轮尚未提交的 P0 共指、数据与评测材料改动）
- 冻结对象：`entity_linker/coreference.py` 中的 `RuleBasedCoreferenceResolver`
- 冻结版本：P0——同句显式协调组；支持 `和`、`与`、`及`、`以及`、`、`、`同`、`跟`、`连同`、`会同`；集合词数量约束已启用。

## 冻结时回归基线

|指标|结果|
|-|-:|
|历史单实体|257 / 257（100.00%）|
|Acceptance Main|100 / 100（100.00%）|
|Challenge Dev|18 / 25（72.00%）|
|集合正例 Exact Match|79 / 83（95.18%）|
|集合 NIL|34 / 37（91.89%）|

## 已知边界

- `CORE_COL_EVAL_123`：`semantic_ambiguity_no_safe_rule`。多个同句协调组均可解释“双方”，保持最近协调组优先；不修改 gold，不以样本 ID、固定词面或单条文本写特例。
- `CORE_COL_EVAL_071`、`CORE_COL_EVAL_106`、`CORE_COL_EVAL_107`：需要篇章级主体连续性或事件语义。简单跨句缓存会与当前正确的跨句 NIL 对照冲突，故不在 P0 后继续修改。
- `CORE_COL_EVAL_075`、`CORE_COL_EVAL_124`：人称 / 类型约束边界；仅两条，不继续堆叠局部规则。
- `CORE_COL_EVAL_074`：产品集合范围边界；未建立粗粒度产品 / 平台类型策略前不扩展。

## 冻结纪律

Blind Holdout 在本冻结版本下只运行一次；运行后不基于相同 holdout 调整规则、gold 或数据。若未来重新优化，应先将本 holdout 降级为下一轮开发挑战集，再创建新的 holdout。
