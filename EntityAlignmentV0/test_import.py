# test_import.py
print("测试导入...")

print("1. 导入 logger...")
from src.utils.logger import logger, generate_trace_id
print("   ✅ logger 导入成功")

print("2. 测试 logger...")
logger.info("这是一条测试日志")

print("3. 测试 generate_trace_id...")
tid = generate_trace_id()
print(f"   trace_id: {tid}")

print("\n✅ 导入测试通过！")