# src/ner/adapters/factory.py
from typing import Dict
from .base import NERAdapter
from .hanlp_adapter import HanLPAdapter
from .spacy_adapter import SpacyAdapter


class NERAdapterFactory:
    """NER 适配器工厂"""

    @staticmethod
    def create(config: Dict) -> NERAdapter:
        backend = config.get("backend", "hanlp")

        if backend == "hanlp":
            model_name = config.get("hanlp_model", "CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH")
            return HanLPAdapter(model_name)
        elif backend == "spacy":
            model_name = config.get("spacy_model", "zh_core_web_sm")
            return SpacyAdapter(model_name)
        else:
            raise ValueError(f"不支持的 NER 后端: {backend}")