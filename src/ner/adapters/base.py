# src/ner/adapters/base.py
from abc import ABC, abstractmethod
from typing import List
from src.models.mention import StandardMention


class NERAdapter(ABC):
    """NER 适配器基类 - 将各种 NER 模型输出转换为内部标准 Mention"""

    @abstractmethod
    def extract(self, text: str) -> List[StandardMention]:
        """从文本中提取实体，返回 StandardMention 列表"""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """返回模型名称"""
        pass