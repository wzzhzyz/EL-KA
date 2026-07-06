# FastAPI 跨域与接口自动文档配置说明

## 目标

说明如何为 FastAPI 服务配置跨域访问（CORS）和自动文档展示。

## CORS 配置

### 1. 目的

- 允许 Web 前端在浏览器中调用 FastAPI 接口。
- 控制允许的来源、方法和请求头。

### 2. 基本配置

在 `FastAPI` 应用中添加 `CORSMiddleware`：

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title='Entity Linker API',
    version='0.1.0',
    description='Entity linking service for EL-KA project',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['*'],
)
```

### 3. 推荐策略

- 开发环境可使用 `allow_origins=['*']`。
- 生产环境建议明确列出允许域名。
- `allow_headers=['*']` 可保证请求携带 `Content-Type`, `X-Trace-Id` 等自定义头。
- `allow_methods` 建议至少包含 `GET`, `POST`, `OPTIONS`。

## API 自动文档展示

FastAPI 自带两个自动文档界面：
- Swagger UI：`/docs`
- ReDoc：`/redoc`
- OpenAPI JSON：`/openapi.json`

### 1. 默认启用

FastAPI 默认会自动启用上述文档路径，无需额外配置。

### 2. 自定义文档路径

可在创建 app 时配置：

```python
app = FastAPI(
    title='Entity Linker API',
    version='0.1.0',
    description='Entity linking service for EL-KA project',
    docs_url='/docs',
    redoc_url='/redoc',
    openapi_url='/openapi.json',
)
```

### 3. 文档内容建议

- 为所有接口添加 `summary` 和 `description`。
- 为请求体和响应模型定义清晰的 Pydantic schema。
- 在接口参数上添加示例值，提升 Swagger 展示效果。

## 运行方式

```powershell
uvicorn entity_linker.api.main:app --reload --host 0.0.0.0 --port 8000
```

访问方式：
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`
- `http://127.0.0.1:8000/openapi.json`

## 备注

- 若不希望暴露文档，可将 `docs_url=None` 和 `redoc_url=None`。
- CORS 与自动文档通常可并行配置，且对前端集成体验非常重要。
