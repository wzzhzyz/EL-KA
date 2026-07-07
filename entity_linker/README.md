# entity_linker 输入格式说明

这个目录下的命令行入口是 `python -m entity_linker`。

> 当前 `entity_linker` 实现的是本地串联流程：NER → 候选生成 → fallback规则消歧 → NIL判定 → 存储。
> 如果仓库内安装并准备好了 `EntityAlignmentV0` 的 BGE 模型目录，系统会尝试接入 `EntityAlignmentV0` 的候选生成和消歧组件；否则会自动回退到本地 fallback 实现。
> fallback 消歧仅作为 BGE/LLM 未就绪时的可验收规则兜底，真实语义消歧仍通过 `DisambiguatorPort` 保持可插拔接入。

## 1. 单文本输入

适合一次只处理一条文本。

```powershell
python -m entity_linker --text "国家电网有限公司发布了公告。"
```

## 2. 多文本直接输入

适合一次在命令行里传入多条文本。

```powershell
python -m entity_linker --texts "文本1" "文本2" "文本3"
```

## 3. 批量文件输入

### txt 文件

可以，多条也支持。规则是：
- 每一行是一条文本
- 空行会被忽略
- 一行里就是一条完整文本，不要求额外 JSON 格式

示例：

```text
国家电网有限公司发布了公告。
国网新源控股有限公司正在扩建。
中国南方电网有限责任公司开展了新项目。
```

命令：

```powershell
python -m entity_linker --batch-file .\data\batch_texts.txt
```

### json 文件

支持两种格式：
- JSON 数组，每个元素可以是字符串或包含 `text` 字段的对象
- JSON 对象，若包含 `texts` 数组，则数组元素按上面规则读取

示例 1：

```json
[
  "国家电网有限公司发布了公告。",
  "国网新源控股有限公司正在扩建。"
]
```

示例 2：

```json
[
  {"text": "国家电网有限公司发布了公告。"},
  {"text": "国网新源控股有限公司正在扩建。"}
]
```

示例 3：

```json
{
  "texts": [
    "国家电网有限公司发布了公告。",
    "国网新源控股有限公司正在扩建。"
  ]
}
```

### jsonl 文件

每一行是一条 JSON 记录，常见格式是每行包含一个 `text` 字段。

示例：

```jsonl
{"text": "国家电网有限公司发布了公告。"}
{"text": "国网新源控股有限公司正在扩建。"}
```

命令：

```powershell
python -m entity_linker --batch-file .\data\batch_texts.jsonl
```

## 4. 输出

程序默认直接打印 JSON 结果到终端；如果想保存到文件，可以加 `--output`：

```powershell
python -m entity_linker --batch-file .\data\batch_texts.txt --output .\data\result.json
```

如果你希望保留当前 pipeline 的共指占位步骤，可以加 `--enable-coreference`：

```powershell
python -m entity_linker --text "国家电网有限公司发布了公告。" --enable-coreference
```

## 5. 结果说明

输出结果里通常会包含：
- `trace_id`：链路追踪编号
- `results`：实体抽取和候选结果
- `stats`：统计信息
- `backend`：当前使用的后端，当前主文件夹默认是 `local`

如果需要查看全链路数据库记录，可以在代码里调用 `EntityLinkingPipeline.get_trace(trace_id)` 或 `EntityLinkingPipeline.list_runs()`。

## 6. 全流程测试指令

### 6.1 先测试当前默认流程（如果 BGE 模型尚未下载）

```powershell
python -m entity_linker --text "国家电网有限公司发布了公告。"
```

这会运行当前 pipeline，并在没有可用 BGE 模型时自动回退到本地 fallback 实现。

### 6.2 如果准备好 BGE 模型目录后，建议使用 Python 直接指定模型路径进行端到端测试

```python
from entity_linker.pipeline import EntityLinkingPipeline

pipeline = EntityLinkingPipeline(config={
    "bge_model_path": r"D:\path\to\bge-small-zh"
})
result = pipeline.run("国家电网有限公司发布了公告。")
print(result)
```

如果模型路径正确且模型已下载，`pipeline.backend` 会切换为 `entity_alignment`。

### 6.3 查询数据库中一条运行记录

```powershell
python -c "import sqlite3, json; db_path='data/trace.db'; trace_id='YOUR_TRACE_ID'; conn=sqlite3.connect(db_path); conn.row_factory=sqlite3.Row; cursor=conn.cursor(); run=cursor.execute('SELECT * FROM pipeline_run WHERE run_id=?', (trace_id,)).fetchone(); print(dict(run)); cursor.close(); conn.close()"
```

## 7. 数据库里有什么

默认数据库文件是 `data/trace.db`。如果你想在命令行里直接查看某个 `trace_id` 的运行记录，可以用下面的 Python 命令。

### 查询单个 trace_id

```powershell
python -c "import sqlite3, json; db_path='data/trace.db'; trace_id='20260701T015326Z_7825d042-141b-4c36-9c34-9ed8f54aa79e'; conn=sqlite3.connect(db_path); conn.row_factory=sqlite3.Row; cursor=conn.cursor(); run=cursor.execute('SELECT * FROM pipeline_run WHERE run_id=?', (trace_id,)).fetchone(); steps=cursor.execute('SELECT * FROM pipeline_step WHERE run_id=? ORDER BY id', (trace_id,)).fetchall(); mentions=cursor.execute('SELECT * FROM mention WHERE task_id=? ORDER BY id', (trace_id,)).fetchall(); candidates=cursor.execute('SELECT c.*, m.mention_text FROM candidate c JOIN mention m ON c.mention_id=m.id WHERE m.task_id=? ORDER BY c.id', (trace_id,)).fetchall(); results=cursor.execute('SELECT lr.*, m.mention_text FROM link_result lr JOIN mention m ON lr.mention_id=m.id WHERE m.task_id=? ORDER BY lr.id', (trace_id,)).fetchall(); print('run=', dict(run) if run else None); print('steps=', [dict(row) for row in steps]); print('mentions=', [dict(row) for row in mentions]); print('candidates=', [dict(row) for row in candidates]); print('results=', [dict(row) for row in results]); conn.close()"
```

这里的变量名已经统一好了：
- `db_path`：数据库路径
- `trace_id`：要查询的链路编号
- `conn`：SQLite 连接
- `cursor`：查询游标
- `run`、`steps`、`mentions`、`candidates`、`results`：各表查询结果

### 只看某个表

如果你只想看一个表，也可以直接查：

```powershell
python -c "import sqlite3; db_path='data/trace.db'; conn=sqlite3.connect(db_path); cursor=conn.cursor(); rows=cursor.execute('SELECT * FROM pipeline_run ORDER BY id DESC LIMIT 5').fetchall(); print(rows); conn.close()"
```

```powershell
python -c "import sqlite3; db_path='data/trace.db'; trace_id='20260701T015326Z_7825d042-141b-4c36-9c34-9ed8f54aa79e'; conn=sqlite3.connect(db_path); cursor=conn.cursor(); rows=cursor.execute('SELECT * FROM mention WHERE task_id=? ORDER BY id', (trace_id,)).fetchall(); print(rows); conn.close()"
```

如果你更习惯看表结构，也可以直接打开 `data/trace.db` 做可视化查看。

## 7. Python API 调用示例

你也可以直接在 Python 里调用 `entity_linker`：

```python
from entity_linker.pipeline import EntityLinkingPipeline

pipeline = EntityLinkingPipeline()
result = pipeline.run("国家电网有限公司发布了公告。")
print(result)

batch_results = pipeline.run_batch([
    "国家电网有限公司发布了公告。",
    "国网新源控股有限公司正在扩建。",
])
print(batch_results)

trace = pipeline.get_trace(result["trace_id"])
print(trace)

runs = pipeline.list_runs(limit=10)
print(runs)
```

> 注意：当前 `EntityLinkingPipeline` 默认使用本地 `fallback` 组件，可完成规则级候选选择与 NIL 判定，但不等同于真实 BGE 语义消歧。
> 如果要接入 `EntityAlignmentV0` 中的真实消歧与候选生成模块，需要确保 BGE 模型路径和依赖可用，pipeline 会优先尝试加载该后端。

## 8. 数据库里有什么

这一部分是把“程序里每一步做了什么”和“数据库里每张表存了什么”对应起来说明，避免只看到表名却不知道具体内容。

### 7.1 pipeline_run：一次完整运行的总表

这张表对应一次 `python -m entity_linker ...` 的整体执行，也就是一条链路的“总入口”。

字段说明：
- `run_id`：本次运行的唯一编号，也就是 `trace_id`
- `task_name`：任务名，当前主流程一般是 `entity_linking`
- `status`：运行状态，常见值是 `running`、`success`、`failed`
- `start_ts`：开始时间
- `end_ts`：结束时间，当前实现里主要保留字段，便于后续扩展
- `actor`：触发来源，当前可以留空或由外层服务填充
- `metadata`：JSON 字符串，保存后端类型、参数、统计信息等

对应代码：
- 启动时写入：`EntityLinkingPipeline.run()`
- 结束时更新：`EntityLinkingPipeline.run()`

### 7.2 pipeline_step：每一步做了什么

这张表记录每个阶段的日志，按顺序能看到这条链路里经历了哪些步骤。

字段说明：
- `run_id`：对应哪一次运行
- `stage_name`：步骤名，例如 `pipeline_start`、`ner`、`candidate_generation`、`coreference`、`pipeline_finish`
- `status`：步骤状态，常见值是 `running`、`success`、`skipped`、`failed`
- `message`：这一步的自然语言说明
- `payload`：JSON 字符串，保存这一步的附加信息，比如文本长度、mention 数量、候选数量
- `created_at`：记录时间

对应代码：
- `EntityLinkingPipeline._record_stage()`

### 7.3 mention：NER 抽取出的实体指称

这张表记录 NER 识别到的 mention，也就是原文里被抽出来的实体片段。

字段说明：
- `task_id`：对应运行编号，也就是 `trace_id`
- `doc_id`：文档编号，默认可以和 `trace_id` 相同
- `mention_text`：mention 原文，比如“国家电网有限公司”
- `start_idx`：起始字符位置
- `end_idx`：结束字符位置
- `mention_norm`：归一化后的 mention，比如去空格、转小写
- `context`：mention 前后文片段，方便回看

对应代码：
- `EntityLinkingPipeline._run_linking()` 里调用 `insert_mention()`

### 7.4 candidate：mention 对应的候选实体

这张表记录候选生成结果。一个 mention 可以对应多条候选，所以这是一对多关系。

字段说明：
- `mention_id`：对应哪一条 mention
- `candidate_entity_id`：候选实体 ID
- `candidate_name`：候选实体标准名
- `score`：候选分数
- `metadata`：JSON 字符串，保存别名命中方式、来源等信息

对应代码：
- `EntityLinkingPipeline._run_linking()` 里循环调用 `insert_candidate()`

### 7.5 link_result：最终结果

这张表记录最终写入的结果。当前主流程不做消歧，所以这里主要保存“该 mention 已完成候选生成，但不做最终链接”的结果。

字段说明：
- `mention_id`：对应哪条 mention
- `linked_entity_id`：最终链接到的实体 ID，当前流程可能为空
- `linked_entity_name`：最终链接到的标准名，当前流程可能为空
- `is_nil`：是否判定为 NIL
- `score`：最终结果分数
- `decision_reason`：为什么这么判定
- `evidence`：依据文本
- `model_version`：模型版本，当前主流程可留空
- `actor`：由哪个模块写入，当前主流程通常是 `candidate_generation_only`

对应代码：
- `EntityLinkingPipeline._run_linking()` 里调用 `insert_link_result()`

### 7.6 audit_log：留痕审计表

这张表记录“原值 -> 新值 -> 原因”，是为了后续追责、回放和审计。

字段说明：
- `mention_id`：关联 mention
- `link_result_id`：关联结果
- `field`：被改动或记录的字段名
- `old_value`：原值
- `new_value`：新值
- `reason`：修改原因
- `actor`：谁做的

对应代码：
- `EntityLinkingPipeline._run_linking()` 里调用 `insert_audit_log()`

### 7.7 一条链路的实际对应关系

下面是从输入到数据库的顺序对应：

1. 输入文本进入 `pipeline_run`
2. 开始执行时写入 `pipeline_step`
3. NER 抽取结果写入 `mention`
4. 每个 mention 的候选写入 `candidate`
5. 最终结果写入 `link_result`
6. 每一步的原值、新值、原因写入 `audit_log`

### 7.8 命令行查看时怎么看

如果你想先看总表：

```powershell
python -c "import sqlite3; db_path='data/trace.db'; conn=sqlite3.connect(db_path); cursor=conn.cursor(); rows=cursor.execute('SELECT run_id, task_name, status, start_ts FROM pipeline_run ORDER BY id DESC LIMIT 5').fetchall(); print(rows); conn.close()"
```

如果你想看某条链路的全部步骤：

```powershell
python -c "import sqlite3; db_path='data/trace.db'; trace_id='20260701T015326Z_7825d042-141b-4c36-9c34-9ed8f54aa79e'; conn=sqlite3.connect(db_path); cursor=conn.cursor(); rows=cursor.execute('SELECT stage_name, status, message FROM pipeline_step WHERE run_id=? ORDER BY id', (trace_id,)).fetchall(); print(rows); conn.close()"
```

### 8 上面的如果看不懂或者懒得看直接看我：可用单行查询命令（示例）
(base) D:\Doc\shixun\2\EL-KA>python -c "import sqlite3, json; db_path='data/trace.db'; trace_id='20260701T020956Z_27f3af7e-a666-4cf9-94a6-8806728c2ff0'; conn=sqlite3.connect(db_path); conn.row_factory=sqlite3.Row; cursor=conn.cursor(); run=cursor.execute('SELECT * FROM pipeline_run WHERE run_id=?', (trace_id,)).fetchone(); steps=cursor.execute('SELECT * FROM pipeline_step WHERE run_id=? ORDER BY id', (trace_id,)).fetchall(); mentions=cursor.execute('SELECT * FROM mention WHERE task_id=? ORDER BY id', (trace_id,)).fetchall(); candidates=cursor.execute('SELECT c.*, m.mention_text FROM candidate c JOIN mention m ON c.mention_id=m.id WHERE m.task_id=? ORDER BY c.id', (trace_id,)).fetchall(); results=cursor.execute('SELECT lr.*, m.mention_text FROM link_result lr JOIN mention m ON lr.mention_id=m.id WHERE m.task_id=? ORDER BY lr.id', (trace_id,)).fetchall(); print('===== 总任务 pipeline_run ====='); print(json.dumps(dict(run) if run else {}, ensure_ascii=False, indent=2)); print('\n===== 流水线步骤 pipeline_step ====='); print(json.dumps([dict(r) for r in steps], ensure_ascii=False, indent=2)); print('\n===== NER实体提及 mention ====='); print(json.dumps([dict(r) for r in mentions], ensure_ascii=False, indent=2)); print('\n===== 候选实体 candidate ====='); print(json.dumps([dict(r) for r in candidates], ensure_ascii=False, indent=2)); print('\n===== 最终链接结果 link_result ====='); print(json.dumps([dict(r) for r in results], ensure_ascii=False, indent=2)); conn.close()"
