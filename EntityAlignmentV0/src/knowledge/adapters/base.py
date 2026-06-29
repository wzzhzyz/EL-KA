# src/knowledge/adapters/base.py
from abc import ABC, abstractmethod
from typing import List, Dict
from src.models.entity import StandardEntity


class KnowledgeAdapter(ABC):
    """知识库适配器基类 - 负责将任意格式转换为内部标准实体"""

    @abstractmethod
    def load(self) -> List[StandardEntity]:
        """加载并转换为内部标准实体列表"""
        pass

    @abstractmethod
    def get_stats(self) -> Dict:
        """返回知识库统计信息"""
        pass