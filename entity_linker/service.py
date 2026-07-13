from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, root_validator

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
        json_schema_extra = {
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


class BatchLinkItem(LinkRequest):
    class Config:
        title = "批量实体链接项"


class BatchLinkRequest(BaseModel):
    items: List[BatchLinkItem] = Field(
        ..., description="批量实体链接任务列表，每个任务单独指定 text、mentions、kb 和 options"
    )
    default_kb: Optional[str] = Field(
        None,
        description="可选默认知识库路径，当单条任务未指定 kb 时使用。",
    )

    class Config:
        title = "批量实体链接请求"
        json_schema_extra = {
            "example": {
                "default_kb": "data/kb.json",
                "items": [
                    {
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
                        "options": {"enable_coreference": False},
                    },
                    {
                        "text": "上海石化集团已经发布环保报告。",
                        "mentions": [
                            {
                                "mention": "上海石化集团",
                                "type": "ORG",
                                "char_start": 0,
                                "char_end": 6,
                                "confidence": 1.0,
                                "metadata": {},
                            }
                        ],
                        "kb": "data/energy_entities.json",
                        "options": {"enable_coreference": True},
                    },
                ],
            }
        }

    @root_validator(pre=True)
    def validate_items(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if "items" not in values or not isinstance(values["items"], list):
            raise ValueError("请求体必须包含 items 列表")
        return values


class FileLinkRequest(BaseModel):
    file_path: str = Field(..., description="本地 JSON 文件路径，文件中包含批量请求参数。")
    default_kb: Optional[str] = Field(
        None,
        description="可选默认知识库路径，当文件中未指定 kb 时使用。",
    )

    class Config:
        title = "本地 JSON 文件批量链接请求"

    @root_validator(pre=True)
    def validate_file_path(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        file_path = values.get("file_path")
        if not file_path or not isinstance(file_path, str):
            raise ValueError("file_path 必须是本地 JSON 文件路径字符串")
        return values


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
        json_schema_extra = {
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
            # 默认构造 pipeline 时禁用 LLM 兜底，便于演示时只使用 KB
            pipeline = EntityLinkingPipeline(
                {
                    "entity_alignment": {
                        "enabled": True,
                        "llm_fallback": {"enabled": False},
                    },
                    "prefer_bge": True,
                }
            )
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

    def _load_request_payload(file_path: str) -> Dict[str, Any]:
        resolved_path = Path(file_path)
        if not resolved_path.is_absolute():
            resolved_path = Path(os.getcwd()) / resolved_path
        if not resolved_path.exists():
            raise HTTPException(status_code=400, detail=f"本地 JSON 文件不存在: {file_path}")
        try:
            with open(resolved_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"读取 JSON 文件失败: {exc}")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON 文件必须包含一个对象")
        return payload

    @app.post(
        "/v1/link_from_file",
        response_model=List[LinkResponse],
        summary="从本地 JSON 文件执行批量实体链接",
        description="读取本地 JSON 文件中的批量请求参数，执行实体链接。",
    )
    def link_from_file(req: FileLinkRequest) -> List[LinkResponse]:
        payload = _load_request_payload(req.file_path)
        if req.default_kb is not None and "default_kb" not in payload:
            payload["default_kb"] = req.default_kb
        try:
            batch_request = BatchLinkRequest(**payload)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"JSON 文件内容不符合批量实体链接请求格式: {exc}",
            )
        responses: List[LinkResponse] = []
        for item in batch_request.items:
            options = dict(item.options)
            if item.mentions is not None:
                options["mentions"] = [mention.model_dump() for mention in item.mentions]
            options["kb_path"] = item.kb or batch_request.default_kb
            result = app.state.pipeline.run(
                item.text,
                options=options,
                trace_id=None,
            )
            responses.append(LinkResponse(**result))
        return responses

    @app.post(
        "/v1/link_batch",
        response_model=List[LinkResponse],
        summary="批量实体链接",
        description="接收多个实体链接任务，每个任务可单独指定 text、mentions、kb 和 options。",
    )
    def link_batch(req: BatchLinkRequest) -> List[LinkResponse]:
        responses: List[LinkResponse] = []
        for item in req.items:
            options = dict(item.options)
            if item.mentions is not None:
                options["mentions"] = [mention.model_dump() for mention in item.mentions]
            options["kb_path"] = item.kb or req.default_kb
            result = app.state.pipeline.run(
                item.text,
                options=options,
                trace_id=None,
            )
            responses.append(LinkResponse(**result))
        return responses

    @app.get(
        "/agents",
        summary="查询可用 agent",
        description="返回当前注册的 agent 名称列表，用于运行时选择不同实现。",
    )
    def list_agents() -> Dict[str, list]:
        return {"agents": registry.list()}

    return app


app = create_app()
