# 集合共指 Challenge Dev 失败根因分析

## 1. 范围与事实基线

本报告只分析 `data/eval/coreference_collective_eval.json` 中原 `blind_challenge` 子集的真实输出。该子集已参与分析，后续应改称 `challenge_dev`，不能再作为最终盲测。分析直接使用 `reports/coreference_acceptance_result.json` 中 `RuleBasedCoreferenceResolver` 的预测、gold、规则名和 evidence；未修改规则、gold 或样本。

|指标|结果|
|-|-:|
|Challenge 样本|25|
|Challenge 正确|8 / 25（32.00%）|
|失败|17|
|当前正式总体|365 / 382（95.55%）|

## 2. 逐条失败分析

|样本|目标|主错误类型|Gold / 预测|规则路径|根因与建议|
|-|-|-|-|-|-|
|`071`|双方|`cross_sentence_window_failure`|国家电网、南方电网 / NIL|`collective_unresolved`|协调组在两句前；P1 有限协调组缓存。|
|`073`|双方|`unsupported_coordination_marker`|国家电网、南方电网 / NIL|`collective_unresolved`|未识别“同”；P0 在受限 mention 间隔加入连接词。|
|`074`|它们|`collective_type_scope_failure`|微信、腾讯会议 / NIL|`collective_unresolved`|产品集合被 ORG/PERSON 安全范围过滤；P2 再评估产品粗类型。|
|`075`|她们|`type_compatibility_error`|NIL / 国家电网、南方电网|`collective_coordinated_antecedents`|女性人称词未约束 PERSON 前件；P1 加集合词类型约束。|
|`106`|双方|`cross_sentence_window_failure`|国家电网、南方电网 / NIL|`collective_unresolved`|明确协调组在前一句；P1 缓存。|
|`107`|双方|`cross_sentence_window_failure`|华能集团、三峡集团 / NIL|`collective_unresolved`|两句距离且有插入 mention；P1 有限缓存并降低插入主体影响。|
|`108`|双方|`unsupported_coordination_marker`|中国移动、中国电信 / NIL|`collective_unresolved`|未识别“跟”；P0 扩展受限连接词。|
|`109`|两家机构|`unsupported_coordination_marker`|国家电网、南方电网 / NIL|`collective_unresolved`|未识别“连同”；P0 扩展受限连接词。|
|`110`|双方|`unsupported_coordination_marker`|国家能源局、国家发展改革委 / NIL|`collective_unresolved`|未识别“会同”；P0 扩展受限连接词。|
|`111`|各方|`anaphor_cardinality_error`|三实体 / 最近单实体|`recency_type_sentence`|未当集合词，回退最近实体；P0 至少两个约束。|
|`112`|三方|`anaphor_cardinality_error`|三实体 / 最近单实体|`recency_type_sentence`|未当集合词；P0 恰好三个约束。|
|`113`|两者|`anaphor_cardinality_error`|双实体 / 最近单实体|`recency_type_sentence`|未当集合词；P0 恰好两个约束。|
|`114`|该二者|`anaphor_cardinality_error`|双实体 / 最近单实体|`recency_type_sentence`|未当集合词；P0 恰好两个约束。|
|`115`|上述单位|`anaphor_cardinality_error`|双实体 / 最近单实体|`recency_type_sentence`|未当集合词；P0 至少两个约束。|
|`121`|三方|`anaphor_cardinality_error`|NIL / 最近单实体|`recency_type_sentence`|两个实体不满足“三方”；P0 数量不符即集合 NIL。|
|`123`|双方|`wrong_coordinated_group`|NIL / 华为、腾讯|`collective_coordinated_antecedents`|两个合法组语义竞争，规则固定取最近；P2 竞争时 NIL。|
|`124`|她们|`type_compatibility_error`|NIL / 国家电网、南方电网|`collective_coordinated_antecedents`|同 `075`；P1 人称集合词类型约束。|

完整字段（文本、gold / 预测 ID、evidence、次级分类、风险）见 [JSON 机器可读分析](coreference_blind_failure_analysis.json)。

## 3. 根因统计

|错误类型|数量|占 17 条比例|可否规则修复|优先级|
|-|-:|-:|-|-|
|`collective_anaphor_cardinality_coverage_gap`|6|35.29%|是|P0|
|`unsupported_coordination_marker`|4|23.53%|是|P0|
|`cross_sentence_window_failure`|3|17.65%|部分|P1|
|`type_compatibility_error`|2|11.76%|是|P1|
|`collective_type_scope_failure`|1|5.88%|部分|P2|
|`wrong_coordinated_group`|1|5.88%|部分|P2|

前三个根因覆盖 13 / 17（76.47%）失败。`complete_group_extraction_failure` 不是当前主因：现有同句提取器已经会把连续 `和/与/及/以及/、` 的三、四实体组作为完整组返回；本轮问题是未覆盖的连接词或指代表达、跨句窗口和歧义选择。

## 4. 推荐分阶段优化

### P0：集合词数量约束与连接词扩展

- 涉及文件：`entity_linker/coreference.py`；后续再更新评测输出。
- 规则：为 `各方`、`三方`、`两者`、`该二者`、`上述单位` 进入集合分支；`双方/二者/两者/该二者` 要求恰好 2 个唯一 ID，`三方` 要求恰好 3 个，其余上述集合词要求至少 2 个；数量不符返回集合 NIL。
- 规则：仅在两个相邻已链接 mention 的文本间隔内支持 `同`、`跟`、`连同`、`会同`，不取消同句、同质、去重和显式连接限制。
- 预期：直接覆盖 10 个失败（`073`、`108`–`115`、`121`），challenge_dev 理论上由 8/25 提升至约 18/25；实际以回归为准。
- 风险：低到中等。`同` 等词有非协调用法；需要现有边界限制。数量约束反而会降低 `121` 的过召回。

### P1：类型约束与有限跨句缓存

- 涉及文件：`entity_linker/coreference.py`，并需新增失败驱动回归数据后验证。
- 类型约束可修复 `075`、`124`：人称女性集合词不得连接 ORG 组。对未来 PERSON 组保留兼容空间。
- 有限缓存可覆盖 `071`、`106`、`107`：只缓存明确、已链接、同质协调组；同句优先，最多回看两句；出现新主体或竞争组时降权并倾向 NIL。
- 风险：跨句缓存最可能新增 false positive 和降低集合 NIL，不能与 P0 混合实施。

### P2：多协调组和产品集合

- `123` 需要多个合法协调组的语义竞争判断。主验收已有“最近组正确”的样本，不能简单规定“多个组一律 NIL”。
- `074` 需要先定义可复用 PRODUCT/SYSTEM 粗类型矩阵；否则可能把产品、平台与公司误合并。
- 两项均不建议为单条 challenge 样本打补丁。

## 5. 回归风险与边界

- P0 词面 / 数量规则会改变原先走 `recency_type_sentence` 的输出，因此必须保持历史单实体 257/257，并检查正式集合主集和集合 NIL。
- 跨句缓存可能将当前正确的主体切换 NIL 错误链接；只有 P0 收益确认后才应单独实施。
- 多协调组选择可能伤害现有“最近协调组”成功样本；缺少可靠话语证据时应优先返回 NIL。
- 跨句隐式集合、复杂主体切换、多组语义竞争、产品—公司混合仍是当前规则系统不可可靠解决的语义边界。

## 6. 结论与下一步

总体指标已过线，但不能用 95.55% 掩盖 challenge_dev 32.00% 的泛化不足。建议下一步仅执行任务定义的 Step 2：将已暴露的 25 条原盲测逻辑标记为 `challenge_dev`，并新建不计入正式指标的代表性失败回归集；随后再单独实施 P0，不应自动进入 P1 / P2。
