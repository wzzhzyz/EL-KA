# Alias Normalization Hard NIL 误召回分析

> 范围：只分析 `ALIAS_HARD_021/022/023/025/030`。本报告不修改测试数据、gold 或候选生成代码。

## 1. 结论摘要

五条失败均不是 alias 精确命中，而是本地 `_FallbackCandidateGenerator` 的 fuzzy containment 规则触发：只要 `mention in candidate_alias` 或 `candidate_alias in mention`，便生成候选，并统一赋予 0.85 分。该规则没有最小长度、长度比例、词边界、实体类型或上下文约束。

需要区分两个层级：当前专项评测器把“候选路径返回任意实体”视为负例失败，因此 5 条构成 **candidate-stage 误召回**。在完整 local fallback pipeline 的默认配置中，fuzzy 候选分数为 0.85，默认 `nil_threshold` 为 0.90，后续 NIL 阶段理论上会拒绝它；实际接口配置若将阈值调低到 0.85 或以下，则可能形成最终错误链接。因此本问题首先是候选污染和阈值配置风险，不能直接等同于完整服务在默认阈值下的最终链接错误。

## 2. 逐例失败链路

|样本|输入 mention 与上下文|fuzzy 命中形式|候选阶段错误实体|人工拒绝依据|
|-|-|-|-|-|
|`ALIAS_HARD_021`|`中国能源研究会`；文本描述其发布能源转型研究成果、召开年度学术会议|短 alias `国能` 被包含在 mention 内|`ENT_ENERGY_0005`，国家能源投资集团有限责任公司|研究会与能源投资集团的组织性质、名称和业务均不同；KB 未登记该研究会|
|`ALIAS_HARD_022`|`中国农业银行`；文本描述面向农业项目的绿色信贷产品|mention 是 KB 全称 `中国农业银行股份有限公司` 的前缀，也包含 alias `农业银行`|`ENT_GEN_0082`，中国农业银行股份有限公司|按冻结数据契约，`中国农业银行`未作为 KB 显式 canonical/alias 登记，且样本 gold 为 NIL；但它是非常自然的简称，本例应同时标注为“严格 alias 词表下的 NIL、现实语义上存在覆盖缺口”的边界案例|
|`ALIAS_HARD_023`|`北京协和医院`；文本描述罕见病远程会诊平台|地区名 alias `北京`（及短形式）被包含在 mention 内|`ENT_ENERGY_0028`，北京市|医院是医疗机构，不能因为名称含地区就链接为地区；KB 未包含该医院实体|
|`ALIAS_HARD_025`|`上交`；文本描述上海交大碳实验室与其联合举办论坛|`上交`是证券交易所 alias `上交所` 的前缀|`ENT_GEN_0087`，上海证券交易所|上下文是高校/实验室协作，非证券交易；`上交`在该 KB 未登记为上海交通大学 alias，也不能据此前缀链接证券交易所|
|`ALIAS_HARD_030`|`深圳大学`；文本描述其建设海洋能源实验平台|地区 alias `深圳`（及短形式）被包含在 mention 内|`ENT_ENERGY_0027`，深圳市|大学与地区不是同类实体；KB 未包含深圳大学，不能把含地名的高校名称退化为地区实体|

## 3. Candidate 生成过程

1. `get_entities_by_alias(mention)` 先做精确索引查找；五条均无精确 alias。
2. 随后 `get_entities_by_alias_fuzzy(mention)` 遍历全部 alias 索引，只要任一方向满足字符串包含就返回实体。
3. `_FallbackCandidateGenerator.generate()` 对 fuzzy 返回的实体统一赋分 0.85，并不记录实际重叠长度或相似度。
4. 当前 alias 专项评测器直接取候选列表首项作为预测，因此把上述返回视为负例失败。

该路径的风险点是：`国能`、`北京`、`深圳`、`上交所` 这类短 alias 只要作为较长 mention 的局部子串，就能跨实体类型进入候选集；候选顺序取决于 alias 索引遍历顺序，而不是上下文相关性。

## 4. 为什么“不存在 alias”仍会产生候选

“不存在精确 alias”只说明 `get_entities_by_alias()` 返回空，不会阻止随后执行 fuzzy 分支。fuzzy 分支的包含式规则把“局部字面重叠”视为候选证据，因此：

- 长 mention 包含短 KB alias，例如 `北京协和医院` 包含 `北京`；
- KB 全称或 alias 包含输入 mention，例如 `上交所` 包含 `上交`、`中国农业银行股份有限公司` 包含 `中国农业银行`；
- 不存在数值 similarity，也不存在最低分阈值；0.85 是固定标签分数，不代表字符串或语义相似度。

候选生成阶段不接收 `entity_type` 或 `context` 参数，故无法排除“医疗机构→地区”“高校→地区”“高校语境→证券交易所”这样的明显不一致。

## 5. NIL 判定边界

candidate generator 本身不做 NIL 判断。完整 pipeline 在候选生成后调用 fallback disambiguator，再以 `score < nil_threshold` 判断 NIL；默认阈值为 0.90，而 fuzzy 分数为 0.85。故应在后续联调中单独测量：默认阈值、接口覆盖阈值及 EntityAlignment 后端下这五条的最终 `is_nil`，避免把候选级指标误读为服务级 F1。
