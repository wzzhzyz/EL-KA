# src/core/ner.py
from typing import List
from src.models.mention import StandardMention, LINKABLE_TYPES
from src.ner.adapters.factory import NERAdapterFactory
from src.utils.logger import logger


class NEREngine:
    """
    NER 引擎 - 只处理内部标准 Mention

    职责：
    1. 通过适配器加载 NER 模型
    2. 执行 NER，返回 StandardMention 列表
    3. 类型过滤
    """

    def __init__(self, config: dict):
        self.config = config
        self.linkable_types = set(config.get("linkable_types", ["ORG", "PERSON", "GPE", "LOC"]))

        # 通过工厂创建适配器
        self.adapter = NERAdapterFactory.create(config)
        logger.info(f"✅ NER 引擎初始化: {self.adapter.get_model_name()}")

    def extract(self, text: str) -> List[StandardMention]:
        """
        从文本中提取实体

        Returns:
            List[StandardMention]: 内部标准 Mention 列表
        """
        # 调用适配器提取
        mentions = self.adapter.extract(text)

        # 类型过滤（只保留可链接的类型）
        filtered = [m for m in mentions if m.mention_type in self.linkable_types]

        logger.info(f"NER识别: {len(filtered)} 个实体: {[m.mention for m in filtered]}")
        return filtered