# 离线拒绝器与运行时解析器对齐报告

## 结论

- 不一致样本：5 / 55。
- 未发现 gold leakage：离线脚本仅使用 gold 进行事后正确性计算，不参与候选、特征或决策。
- 主要差异：离线脚本按字符偏移补充 `sentence_index`，运行时原始输入缺失该字段时默认均为 0。

## 指标

|路径|正确|正例|NIL|False NIL|False Positive|
|-|-:|-:|-:|-:|-:|
|Offline Baseline|33 / 55|24 / 30|9 / 25|4|16|
|Offline Rejection|42 / 55|24 / 30|18 / 25|4|7|
|Runtime / Shadow OFF|34 / 55|27 / 30|7 / 25|1|18|
|Runtime Shadow Rejection|43 / 55|27 / 30|16 / 25|1|9|

## 输入差异矩阵

|项目|离线脚本|正式解析器|一致|
|-|-|-|-|
|mention 来源|原始 JSON + in-memory 分句字段|原始 JSON|否|
|mention 顺序/偏移/entity_id/type|原始 JSON|原始 JSON|是|
|sentence_index|按标点补充|缺失时默认 0|否|
|候选过滤|正式私有候选提取|正式私有候选提取|是|
|候选组顺序|正式提取顺序|正式提取顺序|是|

## 差异样本

- `CORE_DEV_V2_001`：`sentence_index_mismatch`；离线脚本基于字符偏移补充分句；运行时原始 JSON 未提供 sentence_index，解析器按默认值处理。
- `CORE_DEV_V2_005`：`sentence_index_mismatch`；离线脚本基于字符偏移补充分句；运行时原始 JSON 未提供 sentence_index，解析器按默认值处理。
- `CORE_DEV_V2_006`：`sentence_index_mismatch`；离线脚本基于字符偏移补充分句；运行时原始 JSON 未提供 sentence_index，解析器按默认值处理。
- `CORE_DEV_V2_009`：`sentence_index_mismatch`；离线脚本基于字符偏移补充分句；运行时原始 JSON 未提供 sentence_index，解析器按默认值处理。
- `CORE_DEV_V2_012`：`sentence_index_mismatch`；离线脚本基于字符偏移补充分句；运行时原始 JSON 未提供 sentence_index，解析器按默认值处理。
