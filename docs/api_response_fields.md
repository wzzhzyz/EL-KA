# 实体链接API输出字段说明（初稿）

## 1. 适用接口

- `POST /link`：输入原始文本，由服务先执行NER，再完成实体链接；
- `POST /link_with_mentions`：输入文本与已识别mention，符合任务书规定的主要输入方式；
- `GET /health`：服务健康状态；
- `GET /knowledge`：知识库摘要；
- `GET /trace/{trace_id}`：查询链接留痕。

## 2. 链接请求

当前两个链接接口统一使用：

```json
{
  "text": "国家电网发布年度报告。",
  "options": {
    "mentions": [
      {
        "mention": "国家电网",
        "type": "ORG",
        "char_start": 0,
        "char_end": 4,
        "confidence": 1.0
      }
    ],
    "nil_threshold": 0.8,
    "enable_coreference": false,
    "enable_llm_fallback": false,
    "linkable_types": ["ORG", "PERSON", "GPE", "LOC"]
  }
}
```

`/link_with_mentions`从`options.mentions`读取已识别mention；`/link`忽略该字段并执行NER。

## 3. 链接响应顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| `trace_id` | string | 是 | 本次调用的唯一追踪编号，用于日志和数据库回放 |
| `text` | string | 是 | 原始输入文本 |
| `results` | array | 是 | 每个mention的链接或NIL结果 |
| `stats` | object | 是 | 本次调用的数量统计 |

## 4. results字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|:---:|---|
| `mention` | string | 是 | 输入或NER识别出的实体指称 |
| `type` | string | 是 | mention类型，如ORG、PERSON、GPE、LOC、PRON |
| `char_start` | integer | 是 | mention起始字符位置，包含 |
| `char_end` | integer | 是 | mention结束字符位置，不包含 |
| `entity_id` | string | 是 | 标准实体唯一ID；NIL时为空字符串 |
| `standard_entity` | string | 是 | 当前实现中的标准实体名称；NIL时为空字符串 |
| `confidence` | number | 是 | 最终链接置信度，建议范围0-1 |
| `is_nil` | boolean | 是 | 是否未链接到知识库实体 |
| `evidence` | string | 是 | 别名、相似度、阈值或共指规则等判定依据 |
| `is_coreference` | boolean | 否 | 是否由共指模块回链得到 |
| `resolved_from` | string | 否 | 共指结果的先行词 |

任务书目标字段使用`entity_name`表示标准实体名称，当前实现使用`standard_entity`。正式接口定稿时应统一字段名或保留兼容别名。

## 5. stats字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `total_mentions` | integer | 返回结果中的mention总数 |
| `linked` | integer | 成功链接到标准实体的数量 |
| `nil` | integer | NIL数量 |
| `coreference_resolved` | integer | 通过共指回链的数量 |

应满足：

```text
linked + nil = total_mentions
```

共指结果被追加到results时，`total_mentions`可能包含新增的指代mention。

## 6. 其他接口字段

### GET /health

```json
{
  "status": "healthy",
  "entities_count": 63
}
```

### GET /knowledge

```json
{
  "total_entities": 63,
  "entities": []
}
```

当前接口最多返回前50个实体。

### GET /trace/{trace_id}

```json
{
  "trace_id": "trace_xxx",
  "records": []
}
```

## 7. 错误响应

| HTTP状态 | 场景 | 当前响应 |
|---:|---|---|
| 422 | 缺少`text`或字段类型错误 | Pydantic校验结果，字段为`detail` |
| 503 | 服务仍在初始化 | `{"detail": "服务正在初始化"}` |
| 500 | 链接执行异常 | `{"detail": "具体错误"}` |
| 404 | trace_id不存在 | `{"detail": "未找到trace_id"}` |

## 8. 参数支持状态

| 参数 | 当前状态 | 说明 |
|---|---|---|
| `mentions` | 已支持 | `/link_with_mentions`读取 |
| `nil_threshold` | 已支持 | 请求级覆盖最终NIL阈值 |
| `enable_coreference` | 已支持 | 请求级控制共指分支 |
| `linkable_types` | `/link`已支持 | `link_with_mentions`当前未执行类型过滤 |
| `enable_llm_fallback` | 待联调 | 字段已在接口说明中预留，Disambiguator仍主要读取启动配置 |

## 9. 已知接口问题

1. `mentions`嵌套在通用`options`中，Pydantic无法对单个mention字段做严格校验；
2. `results`当前声明为`List[Dict]`，未定义强类型响应Schema；
3. 标准实体名称字段与任务书建议的`entity_name`不一致；
4. 消歧模块计算了`method`，但最终链接结果未稳定返回该字段；
5. 请求方不能直接传入`trace_id`，只能由服务生成；
6. LLM请求级开关尚需联合调试确认。

上述问题只作为接口联调和后续完善依据，本日不修改API实现。
