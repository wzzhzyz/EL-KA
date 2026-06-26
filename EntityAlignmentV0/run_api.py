# run_api.py
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from src.api.routes import app

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 启动实体链接与知识对齐智能体 API")
    print("=" * 60)
    print(f"📚 知识库: ./data/knowledge_base.json")
    print(f"📦 模型: ./models_cache/bge-small-zh")
    print(f"🌐 访问: http://localhost:8000")
    print(f"📖 API文档: http://localhost:8000/docs")
    print("=" * 60)

    uvicorn.run(
        "src.api.routes:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )