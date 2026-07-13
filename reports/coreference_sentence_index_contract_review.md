# 共指 `sentence_index` 输入契约限制

当前正式 mention 输入允许缺失 `sentence_index`；解析器兼容性地按默认值 `0` 处理。离线篇章实验则仅在内存中依据字符偏移和标点补充分句，因此两种口径会改变候选协调组的可见范围。

本轮将其记录为 `input_contract_limitation`，未全局修改 mention、候选组同句边界或 Pipeline 分句行为。

后续独立评审可选方案：

1. 上游明确提供 `sentence_index`；
2. Pipeline 统一按字符偏移补充分句；
3. 保持当前兼容行为。
