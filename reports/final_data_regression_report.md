# Final Data Regression Report

## 1. 修改背景

alias_normalization 的 160 条专项集引入 hard NIL 压力后，发现 5 条不存在于运行 KB 的输入会因 substring fuzzy containment 被候选生成器误召回。原规则把任意双向子串包含视为候选证据，导致短地区名、短简称和长名称前缀污染候选列表。

## 2. 修改内容

本次仅调整 `entity_linker/pipeline.py` 的 local fallback fuzzy 候选路径：

- 精确 alias 匹配保持不变；
- fuzzy containment 要求较短一方长度不少于 3、长度比例不少于 0.50；
- 分数由长度比例和编辑相似度计算，不再固定为 0.85；
- fuzzy metadata 保留命中 alias、原因、长度、比例、编辑距离和 score；
- 不调整 NIL 阈值，不修改测试集、gold 或 KB。

## 3. 测试集覆盖

|测试集|规模|本次回归口径|
|-|-:|-|
|`mention_linking_test.json`|505 文本、1,052 mentions；其中正向 gold 867|正向 gold 是否进入 local fallback 候选列表|
|`candidate_retrieval_test.json`|212 条；正向 gold 164|gold 候选召回|
|`disambiguation_test.json`|154 条；非 NIL gold 113|gold 候选召回|
|`alias_normalization_test.json`|160 条：140 正例、20 hard NIL、20 候选压力正例|正例 Top-1、负例候选拒绝、候选压力 Top-1|
|Batch|214 请求、452 mentions：366 正向、86 NIL|正向 gold 候选召回、NIL 无候选拒绝|

Before 指标通过只读复现旧版“任意 containment”候选规则得到；After 指标使用当前 `_FallbackCandidateGenerator` 得到。两者均不写数据库、不改动输入数据。

## 4. 指标变化

|数据集/指标|Before|After|变化|
|-|-:|-:|-:|
|主链接正向候选召回|849/867（97.92%）|847/867（97.69%）|-2 / -0.23pp|
|候选召回集正向候选召回|157/164（95.73%）|157/164（95.73%）|0|
|消歧集非 NIL 候选召回|106/113（93.81%）|106/113（93.81%）|0|
|Alias Positive Recall|140/140（100.00%）|140/140（100.00%）|0|
|Alias Negative Precision|15/20（75.00%）|19/20（95.00%）|+20.00pp|
|Alias Ambiguous Accuracy|20/20（100.00%）|20/20（100.00%）|0|
|Alias Overall Accuracy|155/160（96.88%）|159/160（99.38%）|+2.50pp|
|Batch 正向候选召回|348/366（95.08%）|348/366（95.08%）|0|
|Batch NIL 候选拒绝|62/86（72.09%）|85/86（98.84%）|+26.75pp|

`scripts/check_alias_normalization_data.py` 复核结果：160 条，0 error，0 warning。`entity_linker/pipeline.py` 已通过 `py_compile`。

## 5. Badcase 变化

|hard NIL|Before|After|
|-|-|-|
|中国能源研究会|国家能源投资集团有限责任公司候选|无候选|
|中国农业银行|中国农业银行股份有限公司候选|仍为 fuzzy 候选，score=0.7833|
|北京协和医院|北京市候选|无候选|
|上交|上海证券交易所候选|无候选|
|深圳大学|深圳市候选|无候选|

保留 `中国农业银行`：它在严格 KB alias 词表下未显式登记该形式，但现实中是“农业银行”的自然扩展简称，并且主链接数据中存在对应正例。该项是标注/alias 覆盖边界，不应靠收紧候选规则强行消除。

## 6. 当前限制

- 主链接正向候选召回减少 2 条，均来自旧版低比例 substring-only 命中；需要后续人工决定是否应作为 KB alias 登记。
- 当前统计衡量的是 local fallback 候选召回/拒绝，而不是 BGE 或 LLM 后端的最终端到端链接准确率。
- `tests/test_candidate_generation.py`、`tests/test_disambiguate.py` 在当前环境依赖未安装的 `faiss`，无法直接运行；本报告用同一 KB 和同一 local fallback 路径完成无写入回归。
- 实体类型与上下文约束尚未接入；这是下一阶段方案 B，不属于本次低风险候选优化。
