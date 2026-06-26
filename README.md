项目：实体链接与知识对齐（骨架）

说明：本目录提供项目骨架、全局配置基类、日志工具和 SQLite 链路追踪表草稿。

注意：已知依赖/限制：`Coreferee` 的共指消解对中文支持不足；代码中在需要处保留占位（不实现中文共指）。

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