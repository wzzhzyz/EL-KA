# 实体链接 API 输出字段说明

> 版本：集合共指扩展说明（Step 8）
> 更新：2026-07-13

## 1. 适用接口与请求结构

当前服务代码定义的链接接口为 `POST /v1/link`。请求中的已识别实体指称位于顶层 `mentions`，开启集合共指使用 `options.enable_coreference`：

```json
{
  "text": "人民日报社和新华通讯社发布联合声明，他们将继续合作。",
  "mentions": [
    {"mention": "人民日报社", "type": "ORG", "char_start": 0, "char_end": 5, "confidence": 1.0},
    {"mention": "新华通讯社", "type": "ORG", "char_start": 6, "char_end": 11, "confidence": 1.0},
    {"mention": "他们", "type": "PRON", "char_start": 18, "char_end": 20, "confidence": 1.0}
  ],
  "options": {"enable_coreference": true}
}
```

服务还定义 `GET /health`。本说明只描述当前 `LinkResponse` 的实际字段；`results` 与 `stats` 在代码中均为通用字典，尚未声明为强类型 Pydantic 子模型。

## 2. 顶层响应字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `trace_id` | `string` | 是 | 本次调用的追踪编号，用于日志和数据库回放。 |
| `text` | `string` | 是 | 原始输入文本。 |
| `input_mode` | `string` | 是 | 当前输入模式，例如 `provided_mentions`。 |
| `results` | `array<object>` | 是 | 每个输入 mention 的实体链接或 NIL 结果。 |
| `stats` | `object` | 是 | 本次调用的汇总统计。 |
| `backend` | `string` | 是 | 当前后端类型，例如 `local` 或 `bge`。 |
| `message` | `string | null` | 否 | 可选附加信息。 |

## 3. `results[i]` 的基础字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `mention` | `string` | 是 | 输入或 NER 识别出的实体指称。 |
| `type` | `string` | 是 | mention 类型，例如 `ORG`、`PERSON`、`GPE`、`LOC`、`PRON`。 |
| `char_start` | `integer` | 是 | mention 起始字符位置（包含）。 |
| `char_end` | `integer` | 是 | mention 结束字符位置（不包含）。 |
| `entity_id` | `string | null` | 是 | 单实体链接的标准实体 ID；集合共指成功时为 `null`。普通 NIL 在当前主链路通常为兼容空字符串。 |
| `standard_entity` | `string` | 是 | 单实体链接的标准实体名称；普通 NIL 为空字符串。集合共指成功时，当前代码同步的是内部 `entity_name`，该值为空字符串；多个目标不通过该字段承载。 |
| `confidence` | `number` | 是 | 最终链接或共指置信度。 |
| `is_nil` | `boolean` | 是 | 是否未链接到知识库实体。它是判断 NIL 的唯一状态字段。 |
| `evidence` | `string` | 是 | 别名、相似度、阈值或共指规则等判定依据。 |
| `is_coreference` | `boolean` | 否 | 原始 NIL 结果被成功共指回链后为 `true`。 |
| `resolved_from` | `string | null` | 否 | 单实体共指的先行词；集合共指没有单一先行词，因此为 `null`。 |

任务书使用 `entity_name` 表示标准实体名称；当前顶层实现使用 `standard_entity`。集合共指的内部对象保留 `entity_name`，但 HTTP 顶层不会新增未实现的 `standard_entities` 字段。

## 4. 集合共指字段与内部对象的关系

内部共指模块返回 `CoreferenceResolution`，其序列化字段包含 `entity_id`、`entity_ids`、`entity_name`、`antecedent`、`antecedent_index`、`antecedent_mentions`、`antecedent_indices`、`confidence`、`evidence`、`rule`、`is_nil` 与 `is_collective`。

当 `enable_coreference=true` 时，管线会将该序列化对象放入每个 `results[i].coreference`。只有同时满足“原始 `results[i].is_nil=true` 且共指解析 `is_nil=false`”时，才会将共指结论同步到 `results[i]` 顶层：`entity_id`、`standard_entity`、`confidence`、`is_nil`、`is_coreference`、`resolved_from`、`evidence`、`entity_ids`、`antecedent_mentions`、`antecedent_indices` 与 `is_collective`。

调用方读取建议如下：

1. 判断该 mention 最终是否成功，读取顶层 `is_nil`；不得仅根据 `entity_id` 是否为空判断。
2. 若顶层 `is_collective=true`，从顶层 `entity_ids` 和 `antecedent_mentions` 读取多个目标与前件。
3. 若需要规则、原始前件索引或未同步的内部解析信息，读取 `results[i].coreference`。

| 场景 | `entity_id` | `entity_ids` | `is_collective` | `is_nil` |
| --- | --- | --- | :---: | :---: |
| 单实体共指成功 | 单个目标 ID | `[单个目标 ID]` | `false` | `false` |
| 集合共指成功 | `null` | 多个去重目标 ID | `true` | `false` |
| 集合共指未解析 | `null`（内部对象） | `[]` | `true` | `true` |
| 普通 NIL | 兼容空值（主链路通常为空字符串） | `[]`（内部对象） | `false` | `true` |

集合成功的顶层兼容示例：

```json
{
  "mention": "他们",
  "entity_id": null,
  "standard_entity": "",
  "entity_ids": ["ENT_NEWS_0001", "ENT_NEWS_0002"],
  "antecedent_mentions": ["人民日报社", "新华通讯社"],
  "antecedent_indices": [0, 1],
  "is_collective": true,
  "is_coreference": true,
  "is_nil": false
}
```

## 5. `stats` 统计口径

| 字段 | 类型 | 当前代码口径 |
| --- | --- | --- |
| `total_mentions` | `integer` | `len(results)`。 |
| `linked` | `integer` | 对每个结果按 `is_nil=false` 计数；集合共指成功必须计入该项。 |
| `nil` | `integer` | 对每个结果按 `is_nil=true` 计数。 |
| `coreference_resolved` | `integer` | 顶层 `is_coreference=true` 的结果数量。 |

当前实现正是以 `is_nil` 而非 `entity_id` 是否为空统计，因此集合共指成功（`entity_id=null`、`is_nil=false`）会计入 `linked`，不会计入 `nil`。在每个结果均具有布尔 `is_nil` 的前提下，`linked + nil = total_mentions` 仍成立。HTTP API 尚未在当前环境进行实时联调，字段序列化兼容性仍应在具备 FastAPI 的环境复核。

## 6. 已知接口边界

- `results` 仍为 `List[Dict]`，集合字段没有强类型响应 Schema；调用方应兼容可选的 `coreference` 与顶层集合字段。
- `standard_entity` 是单字符串兼容字段，不能表达多个标准实体；集合目标应以 `entity_ids` 与 `antecedent_mentions` 为准。
- 当前本地环境缺少 FastAPI，未执行实时 HTTP 请求验证；本说明中的字段传播依据 `service.py`、`pipeline.py` 与 `coreference.py` 的静态代码核对。
