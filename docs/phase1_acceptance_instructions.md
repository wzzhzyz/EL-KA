# 阶段一验收使用说明

## 1. 目的

本说明面向阶段一验收，验证当前实体链接流水线的“端到端可执行性”“数据流转正确性”和“Ground Truth 匹配链路是否可用”。

当前实现范围：
- `entity_linker` pipeline 调度
- `NER -> 候选生成 -> 数据库留痕` 流程
- 批量文本输入与 `SQLite` 追踪
- `EntityAlignmentV0` 的 BGE/消歧组件为可选接入项；若模型未下载，则自动回退到本地 fallback 实现

## 2. 先决条件

1. 仓库根目录：`D:\Doc\shixun\2\EL-KA`
2. Python 环境：`D:/Programfiles/anaconda/envs/EL-KA/python.exe`
3. 数据文件：
   - `data/batch_ground_truth.json`
   - `data/batch_texts.txt`
4. 可选 BGE 模型目录：如果准备好 `EntityAlignmentV0` BGE 模型，则将路径传给 `--bge-model-path`。

## 3. 验收流程

### 3.1 数据完整性检查

确认数据文件存在并可读取：

```powershell
D:/Programfiles/anaconda/envs/EL-KA/python.exe -c "import json; from pathlib import Path; p=Path('data/batch_ground_truth.json'); print(p.exists()); print(len(json.loads(p.read_text(encoding='utf-8'))['entries']))"
```

### 3.2 运行端到端测试脚本

默认运行（fallback 模式）：

```powershell
D:/Programfiles/anaconda/envs/EL-KA/python.exe scripts/e2e_from_ground_truth.py --ground-truth data/batch_ground_truth.json --texts data/batch_texts.txt --trace-prefix phase1 --verbose
```

如果已经准备好 BGE 模型目录，则可启用 EntityAlignmentV0：

```powershell
D:/Programfiles/anaconda/envs/EL-KA/python.exe scripts/e2e_from_ground_truth.py --ground-truth data/batch_ground_truth.json --texts data/batch_texts.txt --trace-prefix phase1 --use-ea --bge-model-path D:\path\to\bge-small-zh --verbose
```

### 3.3 检查运行结果

运行结束后，关注脚本输出：
- `backend`：当前执行的后端，应该为 `local` 或 `entity_alignment`
- `samples`：使用的样本数
- `total_mentions`：Ground Truth 中参与对比的 mention 数
- `accuracy`：链接准确率
- `nil_precision`：NIL 命中率
- `missing_predictions`：预测输出中没有找到的 mention 数

### 3.4 查询数据库留痕

验证链路是否正确写入 SQLite：

```powershell
D:/Programfiles/anaconda/envs/EL-KA/python.exe -c "import sqlite3; conn=sqlite3.connect('data/trace.db'); conn.row_factory=sqlite3.Row; print(conn.execute('SELECT COUNT(*) FROM pipeline_run').fetchone()[0]); print(conn.execute('SELECT COUNT(*) FROM pipeline_step').fetchone()[0]); print(conn.execute('SELECT COUNT(*) FROM mention').fetchone()[0]); conn.close()"
```

### 3.5 单条 trace 回放

取一条 `trace_id`，查看全链路数据：

```powershell
D:/Programfiles/anaconda/envs/EL-KA/python.exe -c "import sqlite3,json; conn=sqlite3.connect('data/trace.db'); conn.row_factory=sqlite3.Row; trace_id='YOUR_TRACE_ID'; run=conn.execute('SELECT * FROM pipeline_run WHERE run_id=?',(trace_id,)).fetchone(); print(dict(run)); steps=[dict(r) for r in conn.execute('SELECT * FROM pipeline_step WHERE run_id=? ORDER BY id',(trace_id,)).fetchall()]; print(steps); conn.close()"
```

## 4. 验收标准

### 必须通过

1. 端到端脚本能够运行，且不因语法错误或环境导入失败终止。
2. `data/batch_ground_truth.json` 与 `data/batch_texts.txt` 能正确装载，且 `text_idx` 对应关系有效。
3. pipeline 能成功写入 `pipeline_run` / `pipeline_step` / `mention` / `candidate` / `link_result` 表。
4. 运行日志中若出现 `BGE 模型路径不存在`，应可正常回退并继续执行。

### 优先判断

- 若有 BGE 模型目录，`backend` 应切换到 `entity_alignment`。
- 若无 BGE 模型目录，`backend` 应为 `local`，但仍要保证数据流转完整。
- `missing_predictions` 应最小化；若出现大量缺失，说明 pipeline 的 NER/mention 匹配或评测脚本对齐需要调整。

## 5. 备注

- 本阶段验收关注“流水线可执行与数据流转”，不强求最终链接准确率达到某个数值。当前 `EntityAlignmentV0` BGE 模型缺失时，仍可验证 pipeline 回退能力和 DB 留痕。
- 若需要后续对比历史指标，请统一使用同一个 Ground Truth 版本 `phase1_e2e_ground_truth`。
