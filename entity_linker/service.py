from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .pipeline import EntityLinkingPipeline
from .registry import registry


class MentionInput(BaseModel):
    mention: str = Field(..., min_length=1, description="实体 mention 文本")
    type: str = Field(default="UNKNOWN", description="mention 类型，如 ORG/PERSON/GPE")
    char_start: int = Field(default=0, description="mention 在文本中的起始字符索引")
    char_end: int = Field(default=0, description="mention 在文本中的结束字符索引")
    confidence: float = Field(default=1.0, description="mention 置信度")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="可选元数据")

    class Config:
        title = "Mention 输入"


class LinkRequest(BaseModel):
    text: str = Field(..., min_length=1, description="原始文本")
    mentions: Optional[List[MentionInput]] = Field(
        None, description="已识别的 mention 列表，优先使用"
    )
    kb: Optional[str] = Field(
        None,
        description="可选的知识库标识或路径。当前版本中该字段作为保留项，后续可用于指定本地知识库或标准实体集。",
    )
    options: Dict[str, Any] = Field(
        default_factory=dict, description="可选配置，例如 enable_coreference"
    )

    class Config:
        title = "实体链接请求"
        schema_extra = {
            "example": {
                "text": "国家电网发布了公告。",
                "mentions": [
                    {
                        "mention": "国家电网",
                        "type": "ORG",
                        "char_start": 0,
                        "char_end": 4,
                        "confidence": 1.0,
                        "metadata": {},
                    }
                ],
                "kb": "data/kb.json",
                "options": {"enable_coreference": False},
            }
        }


class LinkResponse(BaseModel):
    trace_id: str = Field(..., description="请求追踪 ID")
    text: str = Field(..., description="输入文本")
    input_mode: str = Field(
        ..., description="输入模式，如 provided_mentions 或 provided_mentions_required"
    )
    results: List[Dict[str, Any]] = Field(..., description="链接结果列表")
    stats: Dict[str, Any] = Field(..., description="统计信息")
    backend: str = Field(..., description="后端类型，例如 local 或 bge")
    message: Optional[str] = Field(None, description="可选附加消息")

    class Config:
        title = "实体链接响应"
        schema_extra = {
            "example": {
                "trace_id": "123e4567-e89b-12d3-a456-426614174000",
                "text": "国家电网发布了公告。",
                "input_mode": "provided_mentions",
                "results": [
                    {
                        "mention": "国家电网",
                        "type": "ORG",
                        "char_start": 0,
                        "char_end": 4,
                        "entity_id": "ENT_ENERGY_0001",
                        "standard_entity": "国家电网有限公司",
                        "confidence": 0.95,
                        "is_nil": False,
                        "evidence": "fallback规则消歧选择最高分候选",
                        "link_basis": {
                            "reason": "entity_selected",
                            "entity_id": "ENT_ENERGY_0001",
                            "standard_name": "国家电网有限公司",
                            "evidence": "候选分数最高",
                            "source": "disambiguation",
                        },
                    }
                ],
                "stats": {
                    "total_mentions": 1,
                    "linked": 1,
                    "nil": 0,
                    "coreference_resolved": 0,
                },
                "backend": "local",
                "message": "",
            }
        }


class HealthResponse(BaseModel):
    status: str = Field(..., description="健康状态")
    backend: str = Field(..., description="当前后端类型")

    class Config:
        title = "健康检查响应"


def create_app(pipeline: Optional[EntityLinkingPipeline] = None) -> FastAPI:
    app = FastAPI(
        title="EL-KA 实体链接服务",
        version="0.1.0",
        description="提供文本 + mention + KB 的实体链接 HTTP API，支持可配置的共指消解与可插拔后端。",
    )
    if pipeline is None:
        agent_name = os.getenv("EL_KA_AGENT", "default")
        factory = registry.get(agent_name)
        if factory is not None:
            pipeline = factory()
        else:
            pipeline = EntityLinkingPipeline({"entity_alignment": {"enabled": False}})
    app.state.pipeline = pipeline

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="服务健康检查",
        description="返回服务运行状态和当前后端信息。",
    )
    def health() -> HealthResponse:
        return HealthResponse(status="ok", backend=app.state.pipeline.backend)

    @app.post(
        "/v1/link",
        response_model=LinkResponse,
        summary="实体链接",
        description="根据输入文本和预识别 mentions 执行实体链接，支持可选共指消解。",
    )
    def link(req: LinkRequest) -> LinkResponse:
        options = dict(req.options)
        if req.mentions is not None:
            options["mentions"] = [item.model_dump() for item in req.mentions]
        if req.kb is not None:
            options["kb_path"] = req.kb
        result = app.state.pipeline.run(
            req.text,
            options=options,
            trace_id=None,
        )
        return LinkResponse(**result)

    return app


app = create_app()
