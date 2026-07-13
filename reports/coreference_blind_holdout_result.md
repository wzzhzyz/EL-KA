# 共指消解第五项验收报告

## 1. 验收标准

共指消解准确率 ≥80%。正式总体不计入 `coreference_collective_test.json` 单元夹具。

## 2. 评测环境

- 代码版本：`a28d44d`
- 共指模块入口：`entity_linker.coreference.RuleBasedCoreferenceResolver`
- 调用方式：直接实例化真实解析器，对真实输出与 gold 比较；未使用 mock 或 gold 预测。
- 历史数据：`data/eval/coreference_long_text_test.json`
- 正式集合数据：`data/eval/coreference_collective_eval.json`
- Blind Holdout：`data/eval/coreference_blind_holdout.json`

## 3. 数据规模

- 历史单实体 case：257
- 正式集合 case：120（正例 83；集合 NIL 37）
- `acceptance_main`：100；`challenge_dev`：25；`blind_holdout`：25

## 4. 总体结果

|指标|结果|阈值|结论|
|-|-:|-:|-|
|Overall Coreference Accuracy|98.17% (375/382)|80.00%|PASS|

## 5. 分类结果

|指标|结果|
|-|-|
|Legacy Single Accuracy|100.00% (257/257)|
|Single Positive Accuracy|100.00% (198/198)|
|Single NIL Accuracy|100.00% (64/64)|
|Collective Exact Match Accuracy|95.18% (79/83)|
|Collective Positive Accuracy|95.18% (79/83)|
|Collective NIL Accuracy|91.89% (34/37)|
|Acceptance Main Accuracy|100.00% (100/100)|
|Challenge Dev Accuracy|72.00% (18/25)|
|Blind Holdout Accuracy|72.00% (18/25)|
|Blind Holdout Positive Exact Match|68.75% (11/16)|
|Blind Holdout NIL Accuracy|77.78% (7/9)|

## 6. 场景分组

### subset

|分组|正确 / 总数|准确率|
|-|-:|-:|
|`acceptance_main`|100 / 100|100.00%|
|`blind_holdout`|18 / 25|72.00%|
|`challenge_dev`|18 / 25|72.00%|
|`legacy`|257 / 257|100.00%|

### difficulty

|分组|正确 / 总数|准确率|
|-|-:|-:|
|`easy`|1 / 1|100.00%|
|`hard`|43 / 57|75.44%|
|`legacy`|317 / 317|100.00%|
|`medium`|32 / 32|100.00%|

### conjunction

|分组|正确 / 总数|准确率|
|-|-:|-:|
|`legacy`|335 / 342|97.95%|
|`mixed`|0 / 1|0.00%|
|`none`|1 / 1|100.00%|
|`与`|13 / 15|86.67%|
|`以及`|3 / 3|100.00%|
|`会同`|1 / 1|100.00%|
|`及`|11 / 11|100.00%|
|`同`|1 / 1|100.00%|
|`和`|16 / 20|80.00%|
|`跟`|1 / 1|100.00%|
|`连同`|1 / 1|100.00%|
|`顿号+及`|9 / 9|100.00%|
|`顿号+及+以及`|1 / 1|100.00%|

### sentence_scope

|分组|正确 / 总数|准确率|
|-|-:|-:|
|`cross_sentence`|4 / 11|36.36%|
|`legacy`|257 / 257|100.00%|
|`no_gold_antecedent`|31 / 33|93.94%|
|`same_sentence`|101 / 106|95.28%|

### antecedent_count

|分组|正确 / 总数|准确率|
|-|-:|-:|
|`0`|303 / 308|98.38%|
|`2`|69 / 78|88.46%|
|`3`|19 / 19|100.00%|
|`4`|2 / 2|100.00%|

### positive_or_nil

|分组|正确 / 总数|准确率|
|-|-:|-:|
|`NIL`|105 / 110|95.45%|
|`POSITIVE`|288 / 297|96.97%|

## 7. Badcase

|Sample|指代|错误类型|gold|预测|规则|
|-|-|-|-|-|-|
|`CORE_COL_EVAL_071`|双方|`false_nil`|`['ENT_ENERGY_0001', 'ENT_ENERGY_0002']`|`None`|`collective_unresolved`|
|`CORE_COL_EVAL_074`|它们|`false_nil`|`['ENT_GEN_0061', 'ENT_GEN_0104']`|`None`|`collective_unresolved`|
|`CORE_COL_EVAL_075`|她们|`false_positive`|`None`|`['ENT_ENERGY_0001', 'ENT_ENERGY_0002']`|`collective_coordinated_antecedents`|
|`CORE_COL_EVAL_106`|双方|`false_nil`|`['ENT_ENERGY_0001', 'ENT_ENERGY_0002']`|`None`|`collective_unresolved`|
|`CORE_COL_EVAL_107`|双方|`false_nil`|`['ENT_ENERGY_0003', 'ENT_ENERGY_0008']`|`None`|`collective_unresolved`|
|`CORE_COL_EVAL_123`|双方|`false_positive`|`None`|`['ENT_GEN_0051', 'ENT_GEN_0052']`|`collective_coordinated_antecedents`|
|`CORE_COL_EVAL_124`|她们|`false_positive`|`None`|`['ENT_ENERGY_0001', 'ENT_ENERGY_0002']`|`collective_coordinated_antecedents`|
|`CORE_BLIND_HOLDOUT_007`|双方|`false_nil`|`['ENT_GEN_0113', 'ENT_GEN_0114']`|`None`|`collective_unresolved`|
|`CORE_BLIND_HOLDOUT_008`|二者|`false_nil`|`['ENT_GEN_0055', 'ENT_GEN_0081']`|`None`|`collective_unresolved`|
|`CORE_BLIND_HOLDOUT_009`|双方|`false_nil`|`['ENT_ENERGY_0003', 'ENT_ENERGY_0008']`|`None`|`collective_unresolved`|
|`CORE_BLIND_HOLDOUT_010`|双方|`false_nil`|`['ENT_GEN_0139', 'ENT_GEN_0115']`|`None`|`collective_unresolved`|
|`CORE_BLIND_HOLDOUT_015`|它们|`false_nil`|`['ENT_GEN_0061', 'ENT_GEN_0104']`|`None`|`collective_unresolved`|
|`CORE_BLIND_HOLDOUT_017`|她们|`false_positive`|`None`|`['ENT_GEN_0139', 'ENT_GEN_0115']`|`collective_coordinated_antecedents`|
|`CORE_BLIND_HOLDOUT_019`|双方|`false_positive`|`None`|`['ENT_GEN_0051', 'ENT_GEN_0053']`|`collective_coordinated_antecedents`|

## 8. 当前限制

- 当前规则以同句显式并列为主，跨句隐式集合、未覆盖连接词和非 ORG/PERSON 集合会暴露失败；
- 运行知识库缺少可用 PERSON 实体，PERSON 集合正例未纳入端到端 KB 评测；
- Challenge Dev 已参与规则开发，不能作为最终泛化指标；Blind Holdout 在规则冻结后一次性运行，不能据此继续调规则。

## 9. 最终验收结论

正式共指准确率为 **98.17%**，阈值为 **80.00%**，结论：**PASS**。数据质量通过与该算法验收结论分别由质量审计和本脚本的真实解析输出支撑。
