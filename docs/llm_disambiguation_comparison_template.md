# LLM 消歧前后效果对比记录模板

> 日期：2026-07-09  
> 成员视角：欧小红（第三成员，数据处理与实体链接模块实现）  
> 对应任务：搭建 LLM 消歧前后效果对比记录模板

## 1. 模板目标

该模板用于记录疑难实体链接样本在 LLM 兜底前后的效果变化，重点回答三个问题：

1. baseline 为什么低置信或容易误判；
2. LLM 兜底是否改变了结果；
3. 结果变化是否真正带来正确率提升。

模板文件：

`data/eval/llm_disambiguation_comparison_template.json`

## 2. 使用场景

适用于以下样本：

- 短别名，如 `国网`、`平安`、`招行`；
- 母子公司或机构上下级歧义；
- 产品与公司歧义，如 `微信` 与 `腾讯`；
- 跨领域但知识库未覆盖的 NIL；
- baseline top1 分数低或 top1/top2 差距很小的样本。

## 3. 推荐记录字段

| 字段 | 说明 |
|---|---|
| case_id | 疑难样本编号 |
| text | 原始文本 |
| mention | 已识别实体指称 |
| candidate_entity_ids | 候选实体ID列表 |
| gold_entity_id | 人工标注实体ID，NIL则为空 |
| expected_nil | 是否期望NIL |
| baseline.entity_id | LLM前预测实体 |
| baseline.confidence | LLM前置信度 |
| baseline.method | LLM前方法 |
| baseline.evidence | LLM前证据 |
| baseline.is_correct | LLM前是否正确 |
| llm_fallback.trigger_reason | 触发LLM原因 |
| llm_fallback.entity_id | LLM后预测实体 |
| llm_fallback.confidence | LLM后置信度 |
| llm_fallback.reasoning_summary | LLM证据摘要 |
| llm_fallback.is_correct | LLM后是否正确 |
| delta.improvement_type | 提升类型或退化类型 |
| review.review_status | 人工复核状态 |

## 4. improvement_type 枚举

| 类型 | 含义 |
|---|---|
| corrected_wrong_entity | LLM 将错误实体修正为正确实体 |
| corrected_nil | LLM 将错误非NIL修正为NIL |
| unchanged_correct | 前后都正确 |
| unchanged_wrong | 前后都错误 |
| regression | LLM 将正确结果改错 |

## 5. 验收方式

1. 从 `data/eval/llm_fallback_difficult_cases.json` 选取样本；
2. 记录 baseline 输出；
3. 开启 LLM fallback 后记录输出；
4. 由人工复核 `is_correct` 与 `improvement_type`；
5. 统计 LLM 前后准确率、NIL F1 和退化样本数。

## 6. 注意事项

- `reasoning_summary` 只记录简要证据，不保存冗长推理过程；
- 若 LLM 输出实体不在候选列表中，需记录为 `review_status=pending`；
- 对涉及 NIL 的样本，必须明确说明“知识库未覆盖”还是“上下文不足”。
