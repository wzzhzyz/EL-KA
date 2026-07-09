from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


class AgentRegistry:
    """轻量注册表，后续可插入不同的实体链接、共指和外部模型实现。"""

    def __init__(self) -> None:
        self._agents: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, factory: Callable[..., Any]) -> None:
        self._agents[name] = factory

    def get(self, name: str) -> Optional[Callable[..., Any]]:
        return self._agents.get(name)

    def list(self) -> List[str]:
        return sorted(self._agents.keys())


registry = AgentRegistry()
