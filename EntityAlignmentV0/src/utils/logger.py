# src/utils/logger.py
import logging
import uuid
from datetime import datetime

# 创建 logger 实例（在模块级别）
logger = logging.getLogger("entity_linker")
logger.setLevel(logging.INFO)

# 如果还没有 handler，添加一个
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def generate_trace_id() -> str:
    """生成全链路追踪 ID"""
    return f"trace_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"