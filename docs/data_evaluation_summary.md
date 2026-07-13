# 验收数据与评测总览

## 验收指标映射

|验收指标|主要测试集|当前规模|可报告指标/当前结果|说明|
|-|-|-:|-|-|
|链接准确率 ≥85%|`mention_linking_test.json`、`eval_dataset.json`、Batch|505 文本/1,052 mentions；综合集 264；Batch 214 请求|本次 local fallback 正向候选召回 847/867（97.69%）|候选召回不是最终链接准确率；最终准确率需用冻结服务输出与 gold 对比|
|消歧准确率 ≥85%|`disambiguation_test.json`、LLM 歧义/困难集|154 + 151 + 110|本次非 NIL gold 候选召回 106/113（93.81%）|候选进入列表不等于上下文消歧最终正确；LLM 集用于困难候选与人工对比|
|NIL 检测 F1 ≥0.80|主链接、消歧、LLM、Batch、alias hard NIL|主链接含 185 NIL mentions；Batch 86 NIL；alias hard NIL 20|Batch NIL 候选拒绝 85/86（98.84%）；alias Negative Precision 19/20（95.00%）|候选拒绝/Precision 不等同完整服务 NIL F1，仍应在服务输出上计算 Precision、Recall、F1|
|别名标准化召回 ≥85%|`alias_normalization_test.json`|160：140 正例、20 hard NIL、20 候选压力正例|Positive Recall 140/140（100%）；Negative Precision 95%；Ambiguous Accuracy 100%；Overall 99.38%|独立专项集，所有正例由运行 KB aliases/abbreviation 溯源|
|共指消解 ≥80%|`coreference_long_text_test.json`、`coreference_collective_eval.json`、`coreference_blind_holdout.json`|历史单实体：154 文本、257 case；正式集合：125 case（主集 100、Challenge Dev 25）；Holdout：25 case|统一口径 375/382（98.17%）；主集 100/100；Challenge Dev 18/25；Holdout 18/25（72.00%）；集合正例 79/83（95.18%），集合 NIL 34/37（91.89%）|满足 ≥80% 阈值；Challenge Dev 已参与规则开发，Holdout 才是冻结后的独立泛化结果，显示复杂跨句/类型场景仍有提升空间|
|可追溯|pipeline trace、API 契约、候选 metadata|服务链路级|fuzzy 候选现记录命中 alias、原因、长度比例、编辑距离与 score|可用于审计候选产生依据；仍建议保留固定请求—trace 回放 fixture|

## 本阶段数据资产

|类别|文件|用途|
|-|-|-|
|主链接|`data/eval/mention_linking_test.json`|已识别 mention 输入下的标准实体链接与 NIL|
|候选|`data/eval/candidate_retrieval_test.json`|候选生成覆盖与召回|
|消歧|`data/eval/disambiguation_test.json`|候选排序、阈值与 NIL 场景|
|LLM 困难样本|`data/eval/llm_fallback_ambiguity_test.json`、`llm_fallback_difficult_cases.json`|高歧义、低置信度与候选证据|
|别名专项|`data/eval/alias_normalization_test.json`|alias→canonical entity、hard NIL、候选压力|
|历史共指|`data/eval/coreference_long_text_test.json`|历史 Schema 的单实体/兼容回链回归|
|集合共指正式验收|`data/eval/coreference_collective_eval.json`|125 条正式运行 KB ID 样本：83 条集合正例、37 条集合 NIL、5 条普通 NIL；含 100 条主验收和 25 条 Challenge Dev|
|集合共指 Blind Holdout|`data/eval/coreference_blind_holdout.json`|25 条独立冻结后泛化样本：16 条集合正例、9 条集合 NIL；不计入既有统一总体|
|集合共指夹具|`data/eval/coreference_collective_test.json`|8 条规则单元回归，不作为正式总体共指指标|
|Batch|`data/batch_texts.txt`、`data/batch_ground_truth.json`|多 mention 回归与批量接口联调|
|知识库|`data/kb/energy_entities.json`|158 实体、490 aliases、17 实体类型|

## Alias Normalization 验收结论

专项数据质量检查为 160 条、0 error、0 warning。fuzzy 优化后，精确 alias 行为不变；4 条短 alias 污染 hard NIL 已不再产生候选。`中国农业银行`保留为边界 case：严格运行 KB alias 词表没有该精确形式，但现实中它是“农业银行”的常见扩展简称，且主链接数据存在相应正例。

因此，别名标准化的正向召回验收指标已满足；Negative Precision 95% 说明候选拒绝能力显著改善，但不应以删除该边界 case 追求 100%。

## 使用与解释边界

- 当前候选级回归是 local fallback 的验证，不能替代 BGE/LLM 后端的最终链接准确率或 NIL F1；
- 任何对外展示应区分“候选召回/拒绝”与“最终链接/消歧指标”；
- 当前优先完成方案 A 的低风险规则治理；实体类型、上下文和模型重排属于后续可选增强，不应与本轮数据验收混淆。
- 集合共指成功以 `entity_ids`、`is_collective=true`、`is_nil=false` 判断；`entity_id=null` 本身不表示 NIL。第五项统一验收结果见 `reports/coreference_acceptance_result.md`，冻结后 holdout 结果见 `reports/coreference_blind_holdout_result.md`，逐条标注复核见 `reports/coreference_collective_annotation_review.md` 与 `reports/coreference_blind_holdout_annotation_review.md`。Challenge Dev 已参与规则开发，不代表最终泛化能力。
- 本机未安装 `faiss`，因此依赖 BGE/FAISS 的历史主链接、候选与消歧端到端脚本未纳入本轮可复现结果；数据 Schema、gold、偏移和引用一致性已由全量质量审计覆盖。
