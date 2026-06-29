"""通用参数校验工具。

提供轻量的运行时参数校验器，适合在 pipeline 各模块入口进行入参断言。
目前实现基于简单规则和类型检查，可按需扩展为 pydantic 等更严格实现。
"""

from typing import Any, Dict, Iterable, Tuple


class ValidationError(ValueError):
    pass


def require_keys(params: Dict[str, Any], keys: Iterable[str]) -> None:
    """确保 params 中包含指定 key 列表，否则抛出 ValidationError。"""
    missing = [k for k in keys if k not in params]
    if missing:
        raise ValidationError(f"Missing required params: {missing}")


def assert_type(params: Dict[str, Any], key: str, expected_type: type) -> None:
    """断言 params[key] 的类型为 expected_type。"""
    if key not in params:
        raise ValidationError(f"Missing param: {key}")
    if not isinstance(params[key], expected_type):
        raise ValidationError(
            f"Param '{key}' expected type {expected_type.__name__}, got {type(params[key]).__name__}"
        )


def assert_in_choices(params: Dict[str, Any], key: str, choices: Iterable[Any]) -> None:
    """断言 params[key] 的值在 choices 中。"""
    if key not in params:
        raise ValidationError(f"Missing param: {key}")
    if params[key] not in choices:
        raise ValidationError(
            f"Param '{key}' must be one of {list(choices)}, got {params[key]}"
        )


def validate_schema(
    params: Dict[str, Any], schema: Dict[str, Tuple[type, bool]]
) -> None:
    """按 schema 校验 params。

    schema: Dict[key, (type, required_bool)]
    """
    for k, (t, required) in schema.items():
        if required and k not in params:
            raise ValidationError(f"Missing required param: {k}")
        if k in params and not isinstance(params[k], t):
            raise ValidationError(
                f"Param '{k}' expected type {t}, got {type(params[k])}"
            )
