# src/api/routes.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from src.core.linker import EntityLinker
from src.utils.config import get_config
from src.utils.logger import logger

# 加载配置
config = get_config()

# 创建 FastAPI 应用
app = FastAPI(
    title="实体链接与知识对齐智能体",
    description="从原始文本中识别实体，并链接到知识库中的标准实体",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化链接器
linker = None

@app.on_event("startup")
async def startup_event():
    global linker
    logger.info("🚀 启动实体链接服务...")
    try:
        linker = EntityLinker(config)
        logger.info("✅ 实体链接器初始化完成")
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        raise


# ============================================================
# 请求/响应模型
# ============================================================

class LinkRequest(BaseModel):
    text: str
    options: Optional[Dict[str, Any]] = {}

class LinkResponse(BaseModel):
    trace_id: str
    text: str
    results: List[Dict]
    stats: Dict[str, int]

class HealthResponse(BaseModel):
    status: str
    entities_count: Optional[int] = None


# ============================================================
# API 端点
# ============================================================

@app.get("/")
async def root():
    return {"message": "实体链接与知识对齐智能体", "status": "running", "docs": "/docs"}

@app.get("/health", response_model=HealthResponse)
async def health():
    if linker is None:
        return {"status": "initializing"}
    return {"status": "healthy", "entities_count": len(linker.get_knowledge_base())}

@app.post("/link", response_model=LinkResponse)
async def link_entities(request: LinkRequest):
    if linker is None:
        raise HTTPException(status_code=503, detail="服务正在初始化")
    try:
        result = linker.link(request.text, request.options)
        return result
    except Exception as e:
        logger.error(f"链接失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/link_with_mentions")
async def link_with_mentions(request: LinkRequest):
    """已有 mention 列表时直接链接（跳过 NER）"""
    if linker is None:
        raise HTTPException(status_code=503, detail="服务正在初始化")
    try:
        # 从 text 字段解析 mentions (格式: "mention1,mention2" 或 JSON)
        mentions = request.options.get("mentions", [])
        if isinstance(mentions, str):
            mentions = [{"mention": m.strip(), "type": "UNKNOWN"} for m in mentions.split(",")]
        result = linker.link_with_mentions(request.text, mentions, request.options)
        return result
    except Exception as e:
        logger.error(f"链接失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/knowledge")
async def get_knowledge():
    if linker is None:
        raise HTTPException(status_code=503, detail="服务正在初始化")
    entities = linker.get_knowledge_base()
    return {"total_entities": len(entities), "entities": entities[:50]}

@app.get("/trace/{trace_id}")
async def get_trace(trace_id: str):
    if linker is None:
        raise HTTPException(status_code=503, detail="服务正在初始化")
    records = linker.get_trace(trace_id)
    if not records:
        raise HTTPException(status_code=404, detail=f"未找到 trace_id: {trace_id}")
    return {"trace_id": trace_id, "records": records}