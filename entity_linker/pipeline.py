"""Pipeline 调度空壳框架。

该模块提供一个可扩展的 Pipeline 类：
- 可注册各阶段的可调用模块（callable），
- 支持按顺序执行并传递上下文字典，
- 每一步执行结果会加入 trace 信息。

当前实现为最小可运行骨架，后续可替换具体模块实现（NER、候选召回、消歧等）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .utils.trace import new_trace_id, get_current_trace_id, trace_context


StageCallable = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass
class PipelineStage:
    name: str
    fn: StageCallable


class Pipeline:
    def __init__(self, name: str = "entity_linking_pipeline"):
        self.name = name
        self.stages: List[PipelineStage] = []

    def register(self, name: str, fn: StageCallable) -> None:
        """注册一个阶段函数。阶段函数接受并返回 context(dict)。"""
        self.stages.append(PipelineStage(name=name, fn=fn))

    def run(self, context: Optional[Dict[str, Any]] = None, trace_id: Optional[str] = None) -> Dict[str, Any]:
        ctx = context.copy() if context else {}
        ctx.setdefault("trace_id", trace_id or new_trace_id())
        ctx.setdefault("pipeline_name", self.name)
        ctx.setdefault("stage_log", [])

        with trace_context(ctx["trace_id"]):
            for stage in self.stages:
                try:
                    ctx = stage.fn(ctx) or ctx
                    ctx["stage_log"].append({"stage": stage.name, "status": "ok"})
                except Exception as e:
                    ctx["stage_log"].append({"stage": stage.name, "status": "error", "error": str(e)})
                    # propagate after logging
                    raise

        return ctx


def example_stage_load(context: Dict[str, Any]) -> Dict[str, Any]:
    # placeholder: 读取/归一化输入
    context.setdefault("input_docs", [])
    return context


def example_stage_ner(context: Dict[str, Any]) -> Dict[str, Any]:
    # placeholder: NER 模块应该在这里被注入
    context.setdefault("mentions", [])
    return context


if __name__ == "__main__":
    # 简单示例：注册占位阶段并运行
    p = Pipeline()
    p.register("load", example_stage_load)
    p.register("ner", example_stage_ner)
    out = p.run({"input_path": "data/input.txt"})
    print("Pipeline finished, trace_id=", out.get("trace_id"))
