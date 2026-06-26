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