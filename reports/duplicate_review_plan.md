# 测试数据重复治理分析与人工复核计划

## 1. 范围、结论与约束

本报告基于 `reports/dataset_quality_report.json` 的当前审计结果编制，仅进行分类和治理建议：**未删除、合并、改写或移动任何测试数据**。

|指标|当前值|治理含义|
|-|-:|-|
|精确重复组|132|包含跨任务复用和同任务重复，不能直接全部删除|
|精确重复实例|310|每组保留 1 条后的多余实例为 178，仅为统计口径|
|同任务精确重复组|30|本轮人工复核的主要对象|
|跨任务精确复用组|102|默认保留；不同专项的相同文本不等于数据泄漏|
|同文本同 mention 的 gold 冲突|0|无待修复的确定性 gold 冲突|
|跨任务字段差异组|0|当前未见相同文本的显式 gold 不一致|
|近重复候选|76|仅作人工审查线索，不作为自动删除依据|

检测口径为：文本去空白和标点后精确比较；近重复使用 `SequenceMatcher`，阈值为 `0.90`，并带长度差过滤。短中文文本和仅替换实体名称的模板可能被误报，因此近重复不等同于重复错误。

## 2. 分类规则

|分类|判定|处理原则|
|-|-|-|
|`exact_redundant`|同一测试文件、相同文本、相同 gold，且未见专项用途差异|先人工核对样本字段；确认后再由数据负责人决定保留一个或改写一个|
|`template_variant`|句式或上下文高度相似，但实体、目标或任务语义不同|保留；后续扩充时避免继续使用同模板|
|`legitimate_cross_task_reuse`|不同验收任务为验证不同能力而复用同一事实或文本|保留，并在验收说明中标注用途边界|
|`semantic_duplicate`|语义等价但文本并非完全相同|需人工判定是否降低同一专项的有效样本量|
|`gold_conflict`|同规范化文本、同 mention、不同显式 gold|优先修复；当前为 0|
|`needs_manual_review`|专项定位可能不同，审计无法判断是否应双份保留|保留现状，等待负责人确认用途|

## 3. 30 组同任务精确重复的逐组计划

### 3.1 同文件重复：建议列为 `exact_redundant`（8 组）

这些组在同一文件内具有相同规范化文本和相同 gold。当前仅列为候选，**不在本轮删除**。

|组|样本|文本|分类|建议|
|-|-|-|-|-|
|1|`candidate_retrieval_test.json`: `CR_161` / `CR_205`|天坛医院部署远程会诊平台。|`exact_redundant`|人工比较候选列表和场景字段；若完全相同，后续仅保留一个或改写一个为不同召回压力。|
|2|`candidate_retrieval_test.json`: `CR_169` / `CR_208`|奇瑞汽车发布出口车型计划。|`exact_redundant`|同上，重点确认候选集是否不同。|
|3|`mention_linking_test.json`: `MENTION_LINK_373` / `MENTION_LINK_499`|腾讯、阿里巴巴和百度共同参加 AI 安全论坛。|`exact_redundant`|核对多 mention 的 gold 列表后，决定保留或改写。|
|4|`mention_linking_test.json`: `MENTION_LINK_398` / `MENTION_LINK_462`|中国日报和经济日报分别报道绿色金融政策。|`exact_redundant`|核对多 mention 的 gold 列表后，决定保留或改写。|
|5|`mention_linking_test.json`: `MENTION_LINK_402` / `MENTION_LINK_442`|State Grid Zhejiang 在英文报告中对应国网浙江电力。|`exact_redundant`|核对别名/英文名测试意图；若无不同目标，保留一个。|
|6|`mention_linking_test.json`: `MENTION_LINK_428` / `MENTION_LINK_501`|OpenAI 能源实验室提交模型说明，百度和华为只是候选干扰。|`exact_redundant`|核对 NIL 或干扰候选字段；若一致，后续保留一个。|
|7|`mention_linking_test.json`: `MENTION_LINK_429` / `MENTION_LINK_505`|广州轨道交通产业联盟评估客流，广州地铁提供线路数据。|`exact_redundant`|核对多实体 gold；若一致，后续保留一个。|
|8|`mention_linking_test.json`: `MENTION_LINK_436` / `MENTION_LINK_496`|杭州低碳城市研究院发布报告，杭州市提供公开数据。|`exact_redundant`|核对多实体 gold；若一致，后续保留一个。|

### 3.2 LLM 专项之间的精确复用：`needs_manual_review`（22 组）

以下样本分别位于 `llm_fallback_ambiguity_test.json` 与 `llm_fallback_difficult_cases.json`。当前审计按 `llm_fallback` 任务族计为“同任务”，但两文件的验收定位可能不同；在未确认前不能擅自删除，也不应简单将它们认定为泄漏。

|组|歧义集|困难集|分类|人工确认问题|
|-|-|-|-|-|
|1|`LLM_AMB_090`|`LLM_HARD_024`|`needs_manual_review`|是否需要同时作为国际机构 NIL 歧义与困难兜底样本？|
|2|`LLM_AMB_093`|`LLM_HARD_028`|`needs_manual_review`|是否需要同时作为未收录文博机构 NIL 样本？|
|3|`LLM_AMB_097`|`LLM_HARD_031`|`needs_manual_review`|是否同时验证多机构与集合上下文？|
|4|`LLM_AMB_098`|`LLM_HARD_032`|`needs_manual_review`|是否同时验证汽车实体和集合代词？|
|5|`LLM_AMB_100`|`LLM_HARD_033`|`needs_manual_review`|是否同时验证高校集合与候选歧义？|
|6|`LLM_AMB_106`|`LLM_HARD_039`|`needs_manual_review`|是否同时验证设施/集团混淆？|
|7|`LLM_AMB_107`|`LLM_HARD_034`|`needs_manual_review`|是否同时验证前者指代和地图实体歧义？|
|8|`LLM_AMB_108`|`LLM_HARD_035`|`needs_manual_review`|是否同时验证后者指代和地图实体歧义？|
|9|`LLM_AMB_112`|`LLM_HARD_041`|`needs_manual_review`|是否同时验证运营商多实体上下文？|
|10|`LLM_AMB_113`|`LLM_HARD_042`|`needs_manual_review`|是否同时验证运营商角色区分？|
|11|`LLM_AMB_114`|`LLM_HARD_036`|`needs_manual_review`|是否同时验证地区与未收录企业？|
|12|`LLM_AMB_117`|`LLM_HARD_037`|`needs_manual_review`|是否同时验证国际组织 NIL？|
|13|`LLM_AMB_118`|`LLM_HARD_038`|`needs_manual_review`|是否同时验证技术公司干扰候选？|
|14|`LLM_AMB_123`|`LLM_HARD_052`|`needs_manual_review`|是否同时验证金融实体与引用来源？|
|15|`LLM_AMB_127`|`LLM_HARD_054`|`needs_manual_review`|是否同时验证地区实体区分？|
|16|`LLM_AMB_129`|`LLM_HARD_043`|`needs_manual_review`|是否同时验证高校简称和角色区分？|
|17|`LLM_AMB_130`|`LLM_HARD_044`|`needs_manual_review`|是否同时验证高校简称和角色区分？|
|18|`LLM_AMB_133`|`LLM_HARD_050`|`needs_manual_review`|是否同时验证平台/系统类型排除？|
|19|`LLM_AMB_134`|`LLM_HARD_046`|`needs_manual_review`|是否同时验证公司与产品入口关系？|
|20|`LLM_AMB_137`|`LLM_HARD_047`|`needs_manual_review`|是否同时验证支付产品与银行类型排除？|
|21|`LLM_AMB_138`|`LLM_HARD_048`|`needs_manual_review`|是否同时验证银行简称与集合语境？|
|22|`LLM_AMB_140`|`LLM_HARD_049`|`needs_manual_review`|是否同时验证无明确先行词的研究机构表述？|

建议由 LLM 专项负责人逐项标注为：`保留双份（用途不同）`、`移动为跨任务共享样本` 或 `后续改写其中一条`。在此决策前，这 22 组不计入可安全删除项。

## 4. 近重复审查优先级

76 对近重复中，21 对发生在同一文件，55 对跨文件。建议只做分批人工审查，不根据相似度自动修改。

|优先级|对象|数量|初步分类|建议|
|-|-|-:|-|-|
|高|`alias_normalization_test.json` 内近重复|14|`template_variant` 或 `semantic_duplicate`|检查是否仅替换别名/实体且上下文不增加验收信息；优先补足不同 alias 类型或困难上下文。|
|高|`coreference_long_text_test.json` 内近重复|3|`semantic_duplicate`|检查是否重复验证相同指代词、同一规则和同一前件距离。|
|高|`mention_linking_test.json` 内近重复|2|`semantic_duplicate`|与第 3.1 节的精确重复一起处理，避免主测试集有效规模被高估。|
|高|`candidate_retrieval_test.json` 内近重复|1|`template_variant`|确认候选列表、干扰项和 gold 是否形成不同召回压力。|
|高|正式集合共指集内部近重复|1|`needs_manual_review`|`coreference_collective_eval.json#6` 与 `#45` 相似度 0.900；保留前应确认一个验证最近协调组、另一个验证跨句 NIL，二者不应被当作同一能力。|
|中|正式集合共指集与规则夹具|1|`legitimate_cross_task_reuse`|`coreference_collective_eval.json#8` 与夹具 `#5` 仅为近重复；正式集和单元夹具用途不同，保留但避免未来再次复制。|
|中|候选 / 消歧 / 综合链接 /主测试集跨文件近重复|41|`legitimate_cross_task_reuse` 或 `template_variant`|按功能契约判断：候选召回、消歧、综合链接可复用同一事实，但不应在同一最终指标内重复计数。|
|中|LLM 专项与主测试集跨文件近重复|10|`needs_manual_review`|核对是否是有意的兜底压力样本；若是，应在专项文档记录来源。|
|低|别名集与主链接/共指集、NER 与主链接等跨任务近重复|3|`legitimate_cross_task_reuse`|任务目标不同，默认保留。|

> 注：中优先级“候选 / 消歧 / 综合链接 / 主测试集”41 对由候选-消歧 12、候选-综合 12、候选-主链接 11、消歧-综合 4、综合-主链接 2 构成；LLM 与主测试集 10 对由困难集-主链接 5、候选-困难集 3、综合-歧义集 1、歧义集-困难集 1 构成。

## 5. 不应自动处理的项目

1. 102 组跨任务精确复用：各专项的输入、gold 契约和验收目标不同，不能仅凭文本相同判断为泄漏。
2. 76 对近重复：相似度算法只提供候选，不能替代人工语义判断。
3. 历史 `coreference_long_text_test.json` 中的夹具 ID：属于历史兼容数据问题，不属于重复治理范围。
4. 正式集合共指集的 24 条 NIL：它们是规则边界覆盖，不应因相似句式被删除。

## 6. 建议执行顺序（后续阶段）

1. 由数据负责人先确认第 3.1 节 8 组同文件精确重复的字段是否完全一致；确认后才决定保留、改写或去重。
2. 由 LLM 专项负责人确认第 3.2 节 22 组是否因两个专项目标不同而需要双份保留，并记录决定。
3. 再抽查 21 对同文件近重复，优先别名标准化、主实体链接和历史长文本共指。
4. 若后续建立统一最终测试总表，应以“任务契约 + 样本 ID”切分统计，避免跨专项复用造成同一指标重复计数。
5. 每项实际数据改动前重新运行 `python scripts/check_dataset_quality.py`，要求 `conflicting_duplicate_groups=0`，并将改动前后统计写入回归报告。
