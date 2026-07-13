# 集合共指消解设计与验证说明

> 版本：Step 8

## 1. 目标与适用位置

集合共指处理“人民日报社和新华通讯社……他们”这类一个指代同时回指多个已链接实体的情形。它位于实体链接之后：前件 mention 必须已有有效 `entity_id`，本模块不负责新增实体发现、候选生成或知识库补全。

## 2. 内部共指对象

内部模块 `RuleBasedCoreferenceResolver` 为每个 mention 返回一个 `CoreferenceResolution`。其序列化对象使用 `entity_id` 保持单实体兼容，并以 `entity_ids` 表达多目标结果：

| 场景 | `entity_id` | `entity_ids` | `is_collective` | `is_nil` |
| --- | --- | --- | :---: | :---: |
| 单实体共指成功 | 单个目标 ID | `[单个目标 ID]` | `false` | `false` |
| 集合共指成功 | `null` | 多个去重目标 ID | `true` | `false` |
| 集合共指未解析 | `null` | `[]` | `true` | `true` |
| 普通 NIL | `null` | `[]` | `false` | `true` |

对象还会给出 `entity_name`、`antecedent`、`antecedent_index`、`antecedent_mentions`、`antecedent_indices`、`confidence`、`evidence` 与 `rule`。因此，**不能仅根据 `entity_id` 是否为空判断 NIL，必须读取 `is_nil`。**

```json
{
  "mention": "他们",
  "entity_id": null,
  "entity_ids": ["TEST_PEOPLE_DAILY", "TEST_XINHUA"],
  "entity_name": "",
  "antecedent": null,
  "antecedent_mentions": ["人民日报社", "新华通讯社"],
  "antecedent_indices": [0, 1],
  "confidence": 0.9,
  "rule": "collective_coordinated_antecedents",
  "is_collective": true,
  "is_nil": false
}
```

## 3. HTTP 输出映射

当请求启用 `enable_coreference=true` 时，管线总会把内部对象写入 `results[i].coreference`。若原始 `results[i]` 为 NIL，且该对象成功解析（`is_nil=false`），管线会将共指结论同步到顶层结果：`entity_id`、`standard_entity`、`confidence`、`is_nil`、`is_coreference`、`resolved_from`、`evidence`、`entity_ids`、`antecedent_mentions`、`antecedent_indices` 与 `is_collective`。

集合成功时，内部 `entity_name` 为空字符串，故同步后的顶层 `standard_entity` 也为空字符串；多个目标应从 `entity_ids` 和 `antecedent_mentions` 读取。顶层字段适合读取最终链接状态，嵌套 `coreference` 适合读取规则、前件索引和完整内部判定。详见 `docs/api_response_fields.md`。

## 4. 当前本地规则

集合代词范围包括“他们”“她们”“它们”“双方”“二者”“两家央企”“两家机构”“这些机构”等已定义表面词。候选前件必须位于同一句、位于指代之前，并以“和、与、及、以及、、”之一显式连接；同时还必须满足：

- 至少两个不同的实体 ID；
- 全部为同一归一化类型；
- 类型仅允许全 `ORG` 组或全 `PERSON` 组；
- 组内每个 mention 均已有可用实体链接结果。

满足条件时，规则为 `collective_coordinated_antecedents`，置信度为 `0.90`。任一条件不满足时，集合代词返回 `collective_unresolved`，即集合共指未解析 NIL；不会猜测最邻近的两个实体。

## 5. 边界与非目标

- 不处理跨句隐式集合，即使出现“他们”，也必须有同句显式协调结构；
- 不处理 `ORG` 与地点、人物等混合类型集合；
- 不从未链接 mention 推断实体 ID；
- 不处理嵌套集合、复杂并列、省略结构或常识推断；
- 单数代词继续使用既有单实体最近前件规则，不升级为集合结果。

这些限制是保守设计，用于避免将不确定指代错误扩展为多个实体链接。

## 6. 测试与验证范围

专项夹具 `data/eval/coreference_collective_test.json` 共 8 条文本；每条文本包含 1 个待验证指代，因此共 8 个评测 case。它覆盖机构集合、人物集合、三实体集合、混合类型、跨句无连接、单数代词、未链接前件与重复实体 ID。

夹具中的 `TEST_` / `PER_TEST_` ID 仅验证规则结构，不代表运行知识库实体。在线服务只有在前置实体链接返回真实知识库 ID 后，才会向调用方返回真实 ID。历史 `coreference_long_text_test.json` 不增加 `entity_ids` gold，仍按既有单实体/NIL 口径回归，避免因新增专项能力改写历史标注。

本轮直接脚本验证、专项评测、历史长文本回归与数据校验均已通过；实时 HTTP API 与 pytest 框架测试受当前环境缺少 `fastapi`、`pytest` 限制未执行。具体命令和结果见 `reports/collective_coreference_regression_report.md`。
