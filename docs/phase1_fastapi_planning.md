# 阶段二 FastAPI 接口开发规划

## 1. 目标

为下一阶段实体链接系统提供可在线访问的服务接口，满足：
- 单条/批量文本提交流水线调用
- trace 查询与链路回放
- 后端执行模式切换（本地 fallback / EntityAlignmentV0）
- 结果与调试信息分离

## 2. 拟实现接口

### 2.1 `POST /api/v1/link`

用途：提交文本并执行实体链接任务。

请求体：
- `text`: string
- `trace_id`（可选）：string，若未指定则服务器生成 UUID
- `use_ea`（可选）：boolean，是否启用 EntityAlignmentV0 后端
- `bge_model_path`（可选）：string，BGE 模型目录

返回示例：
- `trace_id`
- `backend`：`local` 或 `entity_alignment`
- `entities`：列表
- `mentions`：检测到的 mention 信息
- `status`：`success` / `failed`
- `error`（可选）

### 2.2 `POST /api/v1/link/batch`

用途：批量提交多条文本。

请求体：
- `items`: array of { `text`: string, `trace_id`?: string }
- `use_ea`（可选）：boolean
- `bge_model_path`（可选）：string

返回：
- `results`: 每条文本对应 `trace_id`、`status`、`link_count`
- `summary`：批量结果统计

### 2.3 `GET /api/v1/trace/{trace_id}`

用途：查询单次流水线执行详情。

返回示例：
- `trace_id`
- `run_metadata`：执行时间、backend、输入文本等
- `steps`：每个 pipeline step 的状态与时间戳
- `mentions` / `candidates` / `link_results`

### 2.4 `GET /api/v1/trace/{trace_id}/raw`

用途：获取完整原始 trace 数据，适用于调试。

返回示例：
- `raw_trace`：JSON 原始对象
- `db_rows`：可选的数据库原始行

## 3. 设计要点

### 3.1 业务分层

- API 层：FastAPI 路由与请求/响应模型。
- 服务层：`entity_linker` pipeline 调用、参数转换、trace 读取。
- 数据层：SQLite DB 读写接口、trace 序列化。

建议目录结构：
- `entity_linker/api/`
  - `main.py`
  - `schemas.py`
  - `service.py`
  - `db.py`

### 3.2 参数与后端切换

- `use_ea=True` 时，优先尝试 EntityAlignmentV0。
- 若 EntityAlignmentV0 初始化失败或 BGE 模型缺失，返回 `backend=local`，并在响应中记录 `fallback_reason`。
- `bge_model_path` 只做路径控制，不在 API 层实现下载功能。

### 3.3 Trace 与调试

- `POST /api/v1/link` 和 `batch` 应返回 `trace_id`。
- `GET /api/v1/trace/{trace_id}` 返回结构化步骤结果。
- 调试日志应只包含必要信息；异常详情可通过 `raw` 接口查看。

### 3.4 错误与状态码

- 成功返回 `200`。
- 输入校验失败返回 `400`。
- trace 未找到返回 `404`。
- 内部异常返回 `500`，响应内给出简要 `error`。

## 4. 开发步骤

1. 创建 `entity_linker/api/main.py`，引入 FastAPI 基础框架。
2. 定义 Pydantic schema：`LinkRequest`、`BatchLinkRequest`、`TraceResponse`。
3. 在 `entity_linker/api/service.py` 中封装现有 pipeline 调用：
   - `run_text_link(text, trace_id, use_ea, bge_model_path)`
   - `run_batch_link(items, use_ea, bge_model_path)`
   - `get_trace(trace_id)`
4. 在 `entity_linker/api/db.py` 中封装 trace 读取方法。
5. 增加测试用例：
   - `test_api_link_single`
   - `test_api_link_batch`
   - `test_api_trace_not_found`

## 5. 里程碑与验收

### 5.1 第一阶段交付

- `POST /api/v1/link` 可在线执行单条链接。
- `GET /api/v1/trace/{trace_id}` 返回 trace 元数据与步骤列表。
- `use_ea` 参数能触发后端切换逻辑。

### 5.2 第二阶段补充

- `POST /api/v1/link/batch` 批量处理并返回汇总。
- `GET /api/v1/trace/{trace_id}/raw` 完整 trace。
- 可选：`GET /api/v1/run-history` 分页查询历史 trace。

## 6. 运行示例

```powershell
cd D:\Doc\shixun\2\EL-KA
uvicorn entity_linker.api.main:app --reload --host 0.0.0.0 --port 8000
```

单条请求：

```powershell
curl -X POST "http://127.0.0.1:8000/api/v1/link" -H "Content-Type: application/json" -d "{\"text\": \"北京市公安局办公室地址在哪里？\", \"use_ea\": false}"
```

查询 trace：

```powershell
curl "http://127.0.0.1:8000/api/v1/trace/<trace_id>"
```

## 7. 风险与注意事项

- 当前 pipeline 依赖 `EntityAlignmentV0` 和 BGE 模型路径，若部署环境不具备模型，接口应可靠回退。
- `trace_id` 需唯一且可重复查询，建议使用 UUID。
- 对于批量请求，建议限制最大条数以避免单次请求阻塞。
