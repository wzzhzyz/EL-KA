# FastAPI 服务接口规范

## 目标

说明 `FastAPI` 服务应支持的核心业务接口，重点覆盖两个入口：
- `/link`
- `/link_with_mentions`

## 服务定位

该服务面向实体链接调用，接收文本输入并返回结构化实体链接结果。服务应支持本地 fallback 与 `EntityAlignmentV0` 后端切换。

## 核心接口

### 1. `POST /api/v1/link`

用途：接收输入文本并返回实体链接结果。

请求体：
- `text`: string，待链接的原始文本。
- `use_ea`: boolean，可选，是否启用 EntityAlignmentV0 后端。
- `bge_model_path`: string，可选，BGE 模型目录。
- `trace_id`: string，可选，全局跟踪 ID。

响应示例：
- `trace_id`
- `backend`: string，实际使用的后端名称。
- `entities`: array，标准实体链接结果。
- `status`: string，`success` 或 `failed`。
- `error`: string，可选。

响应结构建议：
- `entities` 每项包含 `mention_text`, `start`, `end`, `entity_id`, `confidence`。

### 2. `POST /api/v1/link_with_mentions`

用途：返回更完整的 mention 信息，便于客户端直接展示检查结果。

请求体：同 `/link`。

响应示例：
- `trace_id`
- `backend`
- `mentions`: array，每项包含 `mention_text`, `start`, `end`, `entity_id`, `kb_name`, `confidence`。
- `status`
- `error`

区别说明：
- `/link` 适合仅需要最终实体结果的场景。
- `/link_with_mentions` 适合需要 mention spans、原始识别结果以及更详细可视化信息的场景。

## 接口兼容性建议

- 两个接口都应支持相同的请求字段，便于客户端切换。
- 若 `use_ea=True`，应尝试使用 `EntityAlignmentV0`；若失败则回退到 `local` 并在响应中说明 `fallback_reason`。
- 两个接口的响应格式应保持一致的统一外层模型。

## 典型使用场景

- `/link`：搜索推荐、实体链接批量计算、后端批处理调用。
- `/link_with_mentions`：标注平台、人工审核、前端高亮展示。

## 备注

- 该文档仅定义业务接口规范，不包含具体实现代码。
- 后续开发可基于 `entity_linker.pipeline` 及数据库 trace 机制实现。
