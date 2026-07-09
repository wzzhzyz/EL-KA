# src/service.py
"""
实体链接服务 - 懒加载入口
"""
import os
import sys
from typing import Dict, Any, Optional

from src.utils.config import load_config, get_config, resolve_path
from src.utils.logger import logger
from src.utils.lazy_loader import get_model_stats, clear_model_cache

# 全局服务实例
_service_instance = None


class EntityLinkerService:
    """
    实体链接服务 - 懒加载模式
    """

    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self._initialized = False

        # 懒加载组件
        self._kb = None
        self._vector_index = None
        self._candidate_generator = None
        self._disambiguator = None

        logger.info("🚀 实体链接服务初始化（懒加载模式）")

    def _ensure_initialized(self):
        """确保所有组件已初始化（懒加载）"""
        if self._initialized:
            return

        logger.info("📦 懒加载：初始化知识库...")
        self._init_kb()
        self._init_vector_index()
        self._init_candidate_generator()
        self._init_disambiguator()

        self._initialized = True
        logger.info("✅ 所有组件初始化完成")

    def _init_kb(self):
        """初始化知识库（轻量级）"""
        from src.knowledge.kb_manager import KnowledgeBase
        kb_config = self.config.get("knowledge_base", {})
        self._kb = KnowledgeBase(kb_config)
        logger.info(f"   📚 知识库: {len(self._kb.entities)} 个实体")

    def _init_vector_index(self):
        """初始化向量索引（不加载模型）"""
        from src.knowledge.vector_index import VectorIndex
        model_path = self.config.get("bge_model_path", "./models_cache/bge-large-zh-v1.5")
        self._vector_index = VectorIndex(model_path, kb=self._kb)
        self._vector_index.build(self._kb.entities)
        logger.info("   🔍 向量索引已就绪（模型懒加载）")

    def _init_candidate_generator(self):
        """初始化候选生成器（轻量级）"""
        from src.core.candidate import CandidateGenerator
        self._candidate_generator = CandidateGenerator(self._kb, self._vector_index)
        logger.info("   🎯 候选生成器已就绪")

    def _init_disambiguator(self):
        """初始化消歧器（不加载模型）"""
        from src.core.disambiguate import Disambiguator
        self._disambiguator = Disambiguator(self.config)
        logger.info("   🎯 消歧器已就绪")

    def link(self, mention_text: str, context: str = "", mention_type: str = ""):
        """
        实体链接主接口

        Args:
            mention_text: 实体指称文本
            context: 上下文
            mention_type: 实体类型提示

        Returns:
            Dict: 链接结果
        """
        # 确保组件已初始化
        self._ensure_initialized()

        # 生成候选
        candidates = self._candidate_generator.generate(
            mention_text,
            top_k=50,
            context=context
        )

        # 消歧精排
        result = self._disambiguator.disambiguate(
            mention=mention_text,
            candidates=candidates,
            context=context,
            mention_type=mention_type
        )

        return result

    def get_stats(self) -> Dict:
        """获取服务统计"""
        stats = {
            "initialized": self._initialized,
            "models": get_model_stats(),
        }

        if self._kb:
            stats["kb"] = self._kb.get_stats()

        if self._disambiguator:
            stats["disambiguator"] = self._disambiguator.get_stats()

        return stats

    def clear_cache(self):
        """清空所有缓存"""
        if self._disambiguator:
            self._disambiguator.clear_cache()
        clear_model_cache()
        logger.info("🧹 所有缓存已清空")


def get_service(config_path: str = "config.yaml") -> EntityLinkerService:
    """获取全局服务实例（单例）"""
    global _service_instance
    if _service_instance is None:
        _service_instance = EntityLinkerService(config_path)
    return _service_instance