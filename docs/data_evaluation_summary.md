# 验收数据与评测总览

## 验收指标映射

|验收指标|主要测试集|当前规模|可报告指标/当前结果|说明|
|-|-|-:|-|-|
|链接准确率 ≥85%|`mention_linking_test.json`、`eval_dataset.json`、Batch|505 文本/1,052 mentions；综合集 264；Batch 214 请求|本次 local fallback 正向候选召回 847/867（97.69%）|候选召回不是最终链接准确率；最终准确率需用冻结服务输出与 gold 对比|
|消歧准确率 ≥85%|`disambiguation_test.json`、LLM 歧义/困难集|154 + 151 + 110|本次非 NIL gold 候选召回 106/113（93.81%）|候选进入列表不等于上下文消歧最终正确；LLM 集用于困难候选与人工对比|
|NIL 检测 F1 ≥0.80|主链接、消歧、LLM、Batch、alias hard NIL|主链接含 185 NIL mentions；Batch 86 NIL；alias hard NIL 20|Batch NIL 候选拒绝 85/86（98.84%）；alias Negative Precision 19/20（95.00%）|候选拒绝/Precision 不等同完整服务 NIL F1，仍应在服务输出上计算 Precision、Recall、F1|
|别名标准化召回 ≥85%|`alias_normalization_test.json`|160：140 正例、20 hard NIL、20 候选压力正例|Positive Recall 140/140（100%）；Negative Precision 95%；Ambiguous Accuracy 100%；Overall 99.38%|独立专项集，所有正例由运行 KB aliases/abbreviation 溯源|
|共指消解 ≥80%|`coreference_long_text_test.json`|154 文本、257 回链 cases|具备规则共指评测脚本与显式 entity ID gold|包括跨句、长距离、集合指代与 NIL；复杂多前件仍需继续扩展|
|可追溯|pipeline trace、API 契约、候选 metadata|服务链路级|fuzzy 候选现记录命中 alias、原因、长度比例、编辑距离与 score|可用于审计候选产生依据；仍建议保留固定请求—trace 回放 fixture|

## 本阶段数据资产

|类别|文件|用途|
|-|-|-|
|主链接|`data/eval/mention_linking_test.json`|已识别 mention 输入下的标准实体链接与 NIL|
|候选|`data/eval/candidate_retrieval_test.json`|候选生成覆盖与召回|
|消歧|`data/eval/disambiguation_test.json`|候选排序、阈值与 NIL 场景|
|LLM 困难样本|`data/eval/llm_fallback_ambiguity_test.json`、`llm_fallback_difficult_cases.json`|高歧义、低置信度与候选证据|
|别名专项|`data/eval/alias_normalization_test.json`|alias→canonical entity、hard NIL、候选压力|
|共指|`data/eval/coreference_long_text_test.json`|代词/指称回链|
|Batch|`data/batch_texts.txt`、`data/batch_ground_truth.json`|多 mention 回归与批量接口联调|
|知识库|`data/kb/energy_entities.json`|158 实体、490 aliases、17 实体类型|

## Alias Normalization 验收结论

专项数据质量检查为 160 条、0 error、0 warning。fuzzy 优化后，精确 alias 行为不变；4 条短 alias 污染 hard NIL 已不再产生候选。`中国农业银行`保留为边界 case：严格运行 KB alias 词表没有该精确形式，但现实中它是“农业银行”的常见扩展简称，且主链接数据存在相应正例。

因此，别名标准化的正向召回验收指标已满足；Negative Precision 95% 说明候选拒绝能力显著改善，但不应以删除该边界 case 追求 100%。

## 使用与解释边界

- 当前候选级回归是 local fallback 的验证，不能替代 BGE/LLM 后端的最终链接准确率或 NIL F1；
- 任何对外展示应区分“候选召回/拒绝”与“最终链接/消歧指标”；
- 当前优先完成方案 A 的低风险规则治理；实体类型、上下文和模型重排属于后续可选增强，不应与本轮数据验收混淆。
