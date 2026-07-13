from __future__ import annotations

from .pipeline import EntityLinkingPipeline
from .registry import registry


def default_pipeline_factory() -> EntityLinkingPipeline:
    return EntityLinkingPipeline(
        {"entity_alignment": {"enabled": True}, "prefer_bge": True}
    )


def register_default_agents() -> None:
    """Register built-in agent factories for service startup and discovery."""
    registry.register("default", default_pipeline_factory)
    registry.register("local", default_pipeline_factory)


register_default_agents()
