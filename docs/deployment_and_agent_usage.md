# 部署与 Agent 扩展指南

## 1. 服务部署

该项目已提供一个可独立部署的 FastAPI 服务，入口在 `entity_linker/service.py`。

推荐启动方式：

```powershell
python -m uvicorn entity_linker.service:app --host 0.0.0.0 --port 8000
```

也可以使用项目根目录中的 `start_service.py`：

```powershell
python start_service.py
```

### 1.1 运行前准备

1. 创建并激活 Python 环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. 安装依赖：

```powershell
pip install -r requirements.txt
```

3. 初始化 SQLite trace 数据库：

```powershell
python -m entity_linker.db.init_db
```

### 1.2 启动参数

- `--host`：监听地址，默认 `0.0.0.0`
- `--port`：监听端口，默认 `8000`

## 2. HTTP API 使用

当前服务暴露的核心接口为：

- `POST /v1/link`

### 2.1 请求格式

请求体为 JSON，主要字段：

- `text`: string，原始文本
- `mentions`: array，可选。已识别的 mentions
  - `mention`: mention 文本
  - `type`: mention 类型，例如 `ORG`/`PER`/`GPE`
  - `char_start`: 起始字符索引
  - `char_end`: 结束字符索引
  - `confidence`: 置信度
- `kb`: string，可选。当前版本作为本地知识库路径或标识使用，实际会映射到 pipeline 的 `kb_path`
- `options`: object，可选配置
  - `enable_coreference`: boolean，是否启用共指消解
  - `coreference_nil_threshold`: number，可选，共指 NIL 决策阈值

示例请求：

```json
{
  "text": "国家电网发布了公告。",
  "mentions": [
    {
      "mention": "国家电网",
      "type": "ORG",
      "char_start": 0,
      "char_end": 4,
      "confidence": 1.0
    }
  ],
  "kb": "data/kb/energy_entities.json",
  "options": {
    "enable_coreference": false
  }
}
```

### 2.2 响应格式

返回结果包含：

- `trace_id`
- `text`
- `input_mode`
- `results`
- `stats`
- `backend`
- `message`

每个 `results` 项目至少应包括：

- `mention`
- `type`
- `char_start`
- `char_end`
- `entity_id`
- `standard_entity`
- `confidence`
- `is_nil`
- `evidence`
- `link_basis`

## 3. KB 指定与插件

当前版本的 `kb` 字段会被映射为 pipeline 内部的 `kb_path`。

- 如果传入合法文件路径，系统会按请求加载该本地知识库。
- 如果传入相对路径，则会相对于项目根目录解析。

例如：

```json
{
  "kb": "data/kb/energy_entities.json"
}
```

## 4. 共指消解

`options.enable_coreference` 用于启/停本地规则共指消解。

- `false`：不执行共指消解
- `true`：在链接完成后执行 `RuleBasedCoreferenceResolver`

## 5. Agent 扩展点

服务支持通过环境变量 `EL_KA_AGENT` 选择不同的 agent 实现。

当前默认实现为 `EntityLinkingPipeline`，如果未注册指定 agent，则会使用本地默认 pipeline：

```python
EntityLinkingPipeline({"entity_alignment": {"enabled": False}})
```

### 5.1 注册自定义 agent

在项目中任意可导入的位置注册 agent 工厂：

```python
from entity_linker.registry import registry
from entity_linker.pipeline import EntityLinkingPipeline


def custom_pipeline_factory() -> EntityLinkingPipeline:
    return EntityLinkingPipeline({"entity_alignment": {"enabled": False}})

registry.register("custom", custom_pipeline_factory)
```

然后启动服务前设置环境变量：

```powershell
$env:EL_KA_AGENT = "custom"
python -m uvicorn entity_linker.service:app --host 0.0.0.0 --port 8000
```

### 5.2 运行时选择

`entity_linker/service.py` 会按以下逻辑选择 pipeline：

1. 读取 `EL_KA_AGENT`
2. 从 `registry` 中查找工厂函数
3. 如果找到则调用工厂构造 pipeline
4. 否则回退到默认 `EntityLinkingPipeline`

## 6. 验证与测试

已有测试用例：

- `tests/test_service_api.py`

运行方式：

```powershell
python -m unittest discover -s tests -p "test_service_api.py"
```

推荐在完成部署前进行一次验证，确保接口与本地 pipeline 正常工作。

## 7. 未来扩展建议

- 增加 `EL_KA_AGENT` 的可注册 agent 列表与文档
- 提供 `POST /v1/link_with_mentions` 扩展接口
- 增加统一 trace_id 中间件以支持跨服务链路追踪
- 提供 SQLLite trace 数据库的可视化查询工具
