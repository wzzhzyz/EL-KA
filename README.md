项目：实体链接与知识对齐（骨架）

说明：本目录提供项目骨架、全局配置基类、日志工具和 SQLite 链路追踪表草稿。

注意：中文共指消岐已改为本地规则基线实现，规划中的 `Coreferee` 方案仅保留为可替换接口，不作为当前默认实现。

快速开始（在项目根目录运行）：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m entity_linker.db.init_db
```

主要文件：
- [entity_linker/config.py](entity_linker/config.py)
- [entity_linker/logging_util.py](entity_linker/logging_util.py)
- [entity_linker/db/schema.sql](entity_linker/db/schema.sql)
- [entity_linker/db/init_db.py](entity_linker/db/init_db.py)

下一步建议：补充评测集、示例数据与 API 规范。

## 服务化入口

当前版本已经提供一个可独立部署的 FastAPI 服务，入口在 [entity_linker/service.py](entity_linker/service.py)。

更多部署与 agent 扩展说明请参见 [docs/deployment_and_agent_usage.md](docs/deployment_and_agent_usage.md)。

启动方式：

```powershell
D:/Programfiles/anaconda/envs/EL-KA/python.exe -m uvicorn entity_linker.service:app --host 0.0.0.0 --port 8000
```

核心能力：
- 统一标准接口：POST /v1/link
- 输入为 text + mentions + kb + options
- 输出为 trace_id / results / stats / input_mode
- 共指消解通过 options.enable_coreference 按需开启
- 可通过环境变量 EL_KA_AGENT 选择注册的智能体工厂，后续可热插拔接入其他实现

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
  "options": {
    "enable_coreference": false
  }
}
```