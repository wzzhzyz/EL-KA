# src/utils/lazy_loader.py
"""
懒加载工具 - 降低启动内存占用
"""
import functools
import logging
from typing import Dict, Any, Optional, Callable
from threading import Lock

logger = logging.getLogger("entity_linker")

# 全局模型实例缓存
_model_cache: Dict[str, Any] = {}
_model_lock = Lock()


def lazy_load(name: str, loader_func: Callable, force_reload: bool = False) -> Any:
    """
    懒加载模型

    Args:
        name: 模型名称（用于缓存key）
        loader_func: 加载模型的函数（无参数）
        force_reload: 是否强制重新加载

    Returns:
        模型实例
    """
    with _model_lock:
        if force_reload or name not in _model_cache:
            logger.info(f"🔄 懒加载模型: {name}")
            _model_cache[name] = loader_func()
            logger.info(f"✅ 模型加载完成: {name}")
        return _model_cache[name]


def clear_model_cache():
    """清空模型缓存（释放内存）"""
    global _model_cache
    with _model_lock:
        for name, model in _model_cache.items():
            try:
                # 尝试释放GPU内存
                if hasattr(model, 'to'):
                    model.to('cpu')
                if hasattr(model, 'model') and hasattr(model.model, 'to'):
                    model.model.to('cpu')
                if hasattr(model, 'model') and hasattr(model.model, 'cpu'):
                    pass
            except:
                pass
        _model_cache.clear()
        logger.info("🧹 模型缓存已清空")


def get_model_stats() -> Dict:
    """获取模型缓存统计"""
    return {
        "cached_models": list(_model_cache.keys()),
        "cache_size": len(_model_cache)
    }