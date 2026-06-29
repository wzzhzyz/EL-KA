"""Trace / run id 生成与辅助工具。

提供简单的 `new_trace_id()` 生成器，以及可选的上下文管理器用于临时绑定 trace_id。
格式采用 UTC 时间 + UUID，便于排序与去重。
"""

from __future__ import annotations

import contextvars
import datetime
import uuid

_TRACE_CTX = contextvars.ContextVar("elka_trace_id", default=None)


def new_trace_id(prefix: str | None = None) -> str:
    """返回一个新的 trace id，例如: 20260629T123456Z_550e8400-e29b-41d4-a716-446655440000"""
    now = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    uid = uuid.uuid4()
    tid = f"{now}_{uid}"
    if prefix:
        return f"{prefix}_{tid}"
    return tid


def get_current_trace_id() -> str | None:
    return _TRACE_CTX.get()


class trace_context:
    """上下文管理器，临时绑定 trace id。"""

    def __init__(self, trace_id: str | None = None):
        self.trace_id = trace_id or new_trace_id()
        self._token = None

    def __enter__(self):
        self._token = _TRACE_CTX.set(self.trace_id)
        return self.trace_id

    def __exit__(self, exc_type, exc, tb):
        if self._token is not None:
            _TRACE_CTX.reset(self._token)
