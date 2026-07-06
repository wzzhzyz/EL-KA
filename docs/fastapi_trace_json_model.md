# FastAPI 全局 trace_id 中间件与统一 JSON 模型

## 目标

说明 FastAPI 服务中如何统一管理 `trace_id`，并定义统一请求 / 响应 JSON 模型。

## trace_id 中间件设计

### 1. 目的

- 为每次请求生成唯一跟踪 ID。
- 支持客户端传入 `trace_id`。
- 将 `trace_id` 注入请求上下文，供后续业务逻辑、日志和 trace 查询使用。

### 2. 实现方案

- 使用 FastAPI 中间件 `BaseHTTPMiddleware` 或 `app.middleware('http')`。
- 读取请求头：`X-Trace-Id`。
- 若请求中未提供，则生成 UUID。
- 将 `trace_id` 保存到 `request.state.trace_id`。
- 该中间件还可统一添加响应头：`X-Trace-Id`。

### 3. 返回值一致性

- 所有接口响应中都应携带 `trace_id`。
- 出现错误时，`trace_id` 仍需保留，便于后续定位。

## 统一请求模型

建议使用 Pydantic 定义基础请求模型：

- `BaseRequest`：包含 `trace_id` 和通用参数。
- `LinkRequest`：继承 `BaseRequest`，包含 `text`, `use_ea`, `bge_model_path`。
- `BatchLinkRequest`：包含 `items: list[LinkItem]`。

示例：

```python
class BaseRequest(BaseModel):
    trace_id: Optional[str] = None

class LinkRequest(BaseRequest):
    text: str
    use_ea: Optional[bool] = False
    bge_model_path: Optional[str] = None
```

## 统一响应模型

建议定义统一响应外层：

- `trace_id`: string
- `status`: string，`success` / `failed`
- `error`: Optional[str]
- `data`: 可选业务数据
- `meta`: 可选元数据

示例：

```python
class BaseResponse(BaseModel):
    trace_id: str
    status: str
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
```

### 业务响应模型示例

`/link` 业务响应：

```python
class EntityItem(BaseModel):
    mention_text: str
    start: int
    end: int
    entity_id: Optional[str]
    confidence: Optional[float]

class LinkResponse(BaseResponse):
    data: Dict[str, List[EntityItem]]
```

`/link_with_mentions` 业务响应：

```python
class MentionItem(EntityItem):
    kb_name: Optional[str]
    mention_id: Optional[str]

class LinkWithMentionsResponse(BaseResponse):
    data: Dict[str, List[MentionItem]]
```

## 兼容性与调试

- 所有 API 应在响应中保留 `trace_id`。
- 中间件应对异常响应也返回统一模型。
- 若发生异常，`status='failed'`，`error` 字段存放关键信息。
- 建议在 `meta` 中返回 `backend`、`fallback_reason` 等运行信息。

## 备注

- 该规范有助于后端服务与前端聚合器统一交互契约。
- 若后续引入 RPC 或消息链路，可复用该 trace_id 规则。
