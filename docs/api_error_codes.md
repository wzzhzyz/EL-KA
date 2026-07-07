# API 异常返回与统一错误码体系

## 目标

为 FastAPI 接口建立一致的错误码与响应规范，便于前端统一处理与后端监控。

## 总体约定

- 所有响应外层使用统一结构：
  - `trace_id`: string
  - `status`: `success` / `failed`
  - `error_code`: integer（应用级错误码，0 表示成功）
  - `error_message`: string（可人读消息）
  - `data`: 可选业务数据
  - `meta`: 可选运行信息（如 `backend`、`fallback_reason`）

示例：

```json
{
  "trace_id": "...",
  "status": "failed",
  "error_code": 2002,
  "error_message": "coref module initialization failed",
  "data": null,
  "meta": {"backend": "local", "fallback_reason": "coref_init_failed"}
}
```

## 错误码分段（建议）

- 0: 成功
- 1000-1999: 请求与输入校验类（客户端错误）
- 2000-2999: 后端处理/业务错误（服务器侧可恢复问题）
- 3000-3999: 数据存储 / DB 错误
- 4000-4999: 第三方依赖错误（模型加载、外部服务）
- 5000-5999: 未分类/严重错误

### 常用错误码说明

- 0: Success
- 1001: Invalid input (missing required field)
- 1002: Unsupported media type / invalid JSON
- 1003: Text too long / exceeds limit
- 1004: Unsupported parameter value (e.g., unknown `coref_model`)

- 2001: Pipeline execution failed
- 2002: Coref module initialization failed
- 2003: EntityAlignment backend error
- 2004: Pipeline step timeout

- 3001: DB write failed
- 3002: DB read failed

- 4001: External model not found
- 4002: External service timeout

- 5001: Unknown internal error

## HTTP 状态码映射建议

- 200: `status=success`（`error_code=0`）
- 400: 客户端输入错误（`1000-1999`）
- 404: 资源未找到（可定义专用错误码，例如 `1005: trace not found`）
- 422: 请求语义校验失败（Pydantic 校验）
- 500: 服务器内部错误（`2000-5999`）

## FastAPI 错误处理中间件示例（伪代码）

- 捕获 `HTTPException` 与 `Exception`。
- 将异常转换为统一 `BaseResponse`，并返回对应 `error_code` 与 `http status`。
- 在响应头和 body 中保留 `X-Trace-Id` / `trace_id`。

示例响应模型：

```python
class BaseResponse(BaseModel):
    trace_id: str
    status: str
    error_code: int = 0
    error_message: Optional[str] = None
    data: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None
```

## 日志与监控

- 每次非 0 错误都记录 `error_code`、`trace_id`、`endpoint`、`user_ip`、`backend` 至日志系统。
- 统计常见错误码频率，为优先修复项排序。

## 兼容性与演进

- 初期阶段可先实现一套常见错误码；随着服务成熟，逐步扩展并在 `docs/api_error_codes.md` 中维护最新列表。
- 所有变更应保证向后兼容（旧错误码仍然被识别）。