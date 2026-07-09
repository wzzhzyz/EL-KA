# src/ner/adapters/spacy_adapter.py
from typing import List
import spacy
from src.models.mention import StandardMention, LINKABLE_TYPES
from src.ner.adapters.base import NERAdapter


class SpacyAdapter(NERAdapter):
    """SpaCy NER 适配器 - 将 SpaCy 输出转换为 StandardMention"""

    def __init__(self, model_name: str = "zh_core_web_sm"):
        self.model_name = model_name
        self._nlp = None

    def _load_model(self):
        if self._nlp is None:
            self._nlp = spacy.load(self.model_name)

    def extract(self, text: str) -> List[StandardMention]:
        self._load_model()
        doc = self._nlp(text)
        mentions = []

        for ent in doc.ents:
            # SpaCy 标签映射
            label_mapping = {
                "ORG": "ORG",
                "PERSON": "PERSON",
                "GPE": "GPE",
                "LOC": "LOC"
            }
            mapped_type = label_mapping.get(ent.label_, "UNKNOWN")

            if mapped_type in LINKABLE_TYPES:
                mentions.append(StandardMention(
                    mention=ent.text,
                    mention_type=mapped_type,
                    char_start=ent.start_char,
                    char_end=ent.end_char
                ))

        return mentions

    def get_model_name(self) -> str:
        return f"spacy_{self.model_name}"