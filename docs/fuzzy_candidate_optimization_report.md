# Fuzzy Candidate 低风险优化报告

## 1. 优化原因

alias_normalization 专项集的 hard NIL 负例中，`中国能源研究会`、`中国农业银行`、`北京协和医院`、`上交`、`深圳大学` 会被本地 fuzzy containment 规则错误带入候选集。原规则对任意双向子串包含均返回候选，并固定赋予 0.85 分，无法说明实际匹配强度。

本次仅优化 local fallback 的 fuzzy 候选路径；精确 alias、测试集、gold、NIL 阈值及总体 pipeline 结构均未修改。

## 2. 修改内容

修改 [entity_linker/pipeline.py](../entity_linker/pipeline.py)：

- 保留 `get_entities_by_alias()` 的精确 alias 行为；
- 新增 `get_entities_by_alias_fuzzy_with_metadata()`，同时保留原 `get_entities_by_alias_fuzzy()` 的兼容返回类型；
- substring fuzzy 要求较短一方长度至少为 3，且较短/较长长度比例至少为 0.50；
- 使用长度比例与 Levenshtein 编辑相似度计算分数：`0.35 + 0.35 * ratio + 0.30 * edit_similarity`；
- 根据实际 fuzzy 分数排序，不再使用固定 0.85；
- 候选 metadata 记录 `alias`、`reason`、长度、长度比例、编辑距离、编辑相似度和 score，供 trace 与后续审计使用。

选择 0.50 而非更高比例的原因是回归结果：0.70 以上会强制拒绝“中农行”边界样本，并显著减少既有模糊正例。0.50 已能屏蔽短 alias 污染，同时不通过规则替代该简称的标注决策。

## 3. 专项指标前后对比

|指标|Before|After|
|-|-:|-:|
|Positive Recall|100.00%|100.00%|
|Negative Precision|75.00%（15/20）|95.00%（19/20）|
|Ambiguous Accuracy|100.00%（20/20）|100.00%（20/20）|
|Overall Accuracy|96.88%（155/160）|99.38%（159/160）|

专项数据质量检查：160 条，0 error，0 warning。

## 4. 5 条 hard NIL 的变化

|样本|优化前候选|优化后候选|结论|
|-|-|-|-|
|中国能源研究会|国家能源投资集团有限责任公司（短 alias `国能`）|无候选|已解决|
|中国农业银行|中国农业银行股份有限公司|仍为 fuzzy 候选，score=0.7833，命中 alias `农业银行`|保留为 alias 覆盖边界；默认 local NIL 阈值 0.90 下应拒绝|
|北京协和医院|北京市（`北京`子串）|无候选|已解决|
|上交|上海证券交易所（`上交所`前缀）|无候选|已解决|
|深圳大学|深圳市（`深圳`子串）|无候选|已解决|

因此，明确的短 alias 候选污染已解决 4/5；没有通过修改 gold 或删除困难样本来取得指标提升。

## 5. 原有数据回归

下表使用不写数据库的 local fallback 候选路径，对既有 JSON 金标中的正向实体检查“gold 是否出现在候选列表”。Before 通过只读复现旧 containment 规则得到，After 为当前实现。

|数据集|Before|After|变化|
|-|-:|-:|-:|
|mention_linking_test 正向候选召回|849/867（97.92%）|847/867（97.69%）|-2（-0.23pp）|
|candidate_retrieval_test 正向候选召回|157/164（95.73%）|157/164（95.73%）|0|
|disambiguation_test 非 NIL 候选召回|106/113（93.81%）|106/113（93.81%）|0|

主链接集减少的两条候选均来自 `MENTION_LINK_168` 的旧 substring-only 命中；它们应在下一轮人工确认“是否为应登记 alias”后决定是补充 KB alias 还是接受为保守 NIL。候选召回集和消歧正例集无变化。

项目中原有 `tests/test_candidate_generation.py`、`tests/test_disambiguate.py` 依赖当前环境未安装的 `faiss`，无法作为本地可执行回归入口；本次改动位于 `entity_linker` 的 local fallback，故采用上述直接加载同一 KB 与同一 `_FallbackCandidateGenerator` 的非写入式回归统计，覆盖了指定的三份验收 JSON 数据。

## 6. 风险与下一步

- 精确 alias 不受影响；但依赖短/低比例 substring 的真实正例可能不再被 fuzzy 召回，已观察到主链接集 2 条下降。
- `中国农业银行`同时在不同数据集呈现“严格词表 NIL”和“合理简称正例”的边界矛盾，不能仅靠候选规则裁决；应在后续标注治理中明确该 alias 是否写入 KB。
- 当前改动未引入实体类型或上下文判断。若需要继续提升剩余边界 NIL 的最终拒绝质量，再评估方案 B 的类型过滤与上下文辅助；不建议仅为把候选级指标推至 100% 直接引入 LLM 重排。
