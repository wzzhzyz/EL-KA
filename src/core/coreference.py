# src/core/coreference.py
from typing import List, Dict, Optional
from src.utils.logger import logger
from src.utils.config import get_config


class CoreferenceResolver:
    """共指消解器：FastCoref + XLM-RoBERTa"""

    def __init__(self, config: dict = None):
        config = config or get_config().get("coreference", {})
        self.enabled = config.get("enabled", False)
        self.mode = config.get("mode", "fastcoref")
        self.model_name = config.get("model", "xlm-roberta-base")
        self.device = config.get("device", "cpu")
        self._model = None
        self._loaded = False

    def _load_model(self):
        """懒加载 FastCoref + XLM-RoBERTa"""
        if self._loaded:
            return

        if not self.enabled:
            logger.info("⏭️ 共指消解未启用，跳过模型加载")
            self._loaded = True
            return

        if self.mode == "fastcoref":
            try:
                logger.info(f"📦 加载 FastCoref + {self.model_name} ...")
                from fastcoref import FCoref

                self._model = FCoref(
                    model_name_or_path=self.model_name,
                    device=self.device
                )
                self._loaded = True
                logger.info(f"✅ FastCoref 加载完成 (模型: {self.model_name})")

            except ImportError as e:
                logger.error(f"❌ FastCoref 未安装: {e}")
                logger.info("   请运行: pip install fastcoref transformers torch")
                self.mode = "heuristic"
                self._loaded = True

            except Exception as e:
                logger.error(f"❌ FastCoref 加载失败: {e}")
                self.mode = "heuristic"
                self._loaded = True
        else:
            self._loaded = True

    def get_clusters(self, text: str) -> List[List[str]]:
        """
        获取 FastCoref 的共指链
        """
        # 如果未启用，直接返回空
        if not self.enabled:
            logger.info("⏭️ 共指消解未启用")
            return []

        # 确保模型已加载
        self._load_model()

        # 如果模型加载失败或模式不是 fastcoref，返回空
        if self.mode != "fastcoref" or self._model is None:
            logger.warning(f"⚠️ FastCoref 模型不可用 (mode={self.mode})")
            return []

        try:
            logger.info(f"🔍 FastCoref 正在分析文本... (长度: {len(text)} 字符)")
            preds = self._model.predict(text)
            clusters = preds.get_clusters(as_strings=True)
            logger.info(f"   FastCoref 识别到 {len(clusters)} 个共指链")
            for cluster in clusters:
                logger.info(f"      {cluster}")
            return clusters

        except Exception as e:
            logger.error(f"❌ FastCoref 推理失败: {e}")
            return []

    def get_all_mentions(self, text: str) -> List[Dict]:
        """使用 FastCoref 提取文本中所有提及"""
        clusters = self.get_clusters(text)
        if not clusters:
            return []

        all_mentions = set()
        for cluster in clusters:
            for mention in cluster:
                all_mentions.add(mention)

        mentions = []
        for mention in all_mentions:
            start = text.find(mention)
            if start != -1:
                mentions.append({
                    "mention": mention,
                    "type": "UNKNOWN",
                    "start": start,
                    "end": start + len(mention)
                })

        return mentions