import os
import sys

root_path = os.path.abspath(".")
sys.path.insert(0, root_path)

# 修正导入路径
from entity_linker.db.writer import DBWriter

db = DBWriter("data/trace.db")

# 1. 单条链路完整回放
trace_id = "20260702T071644Z_d8bb7424-06d4-4c28-af99-ea18df470157"
full_trace = db.get_trace(trace_id)
print("=== 单任务完整回放 ===")
print(full_trace)

# 2. 批量查询历史任务
all_runs = db.list_pipeline_runs(status="success", limit=10)
print("\n=== 批量查询全部历史任务 ===")
for r in all_runs:
    print(r["run_id"], r["metadata"])
