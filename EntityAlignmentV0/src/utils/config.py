# src/utils/config.py
import os
import yaml
from typing import Dict, Any

_config: Dict[str, Any] = {}


def get_project_root() -> str:
    """获取项目根目录"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # src/utils/config.py → 向上两级到项目根目录
    return os.path.abspath(os.path.join(current_dir, "../.."))


def resolve_path(path: str) -> str:
    """将相对路径转换为绝对路径"""
    if os.path.isabs(path):
        return path
    return os.path.join(get_project_root(), path)


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    global _config
    config_full_path = os.path.join(get_project_root(), config_path)
    with open(config_full_path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)

    # 解析相对路径
    if "bge_model_path" in _config:
        _config["bge_model_path"] = resolve_path(_config["bge_model_path"])
    if "knowledge_base" in _config and "path" in _config["knowledge_base"]:
        _config["knowledge_base"]["path"] = resolve_path(_config["knowledge_base"]["path"])
    if "tracer_db" in _config:
        _config["tracer_db"] = resolve_path(_config["tracer_db"])

    return _config


def get_config() -> Dict[str, Any]:
    global _config
    if not _config:
        load_config()
    return _config