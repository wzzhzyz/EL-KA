# src/ner/adapters/hanlp_adapter.py
from typing import List, Tuple
import hanlp
from src.models.mention import StandardMention, TYPE_MAPPING, LINKABLE_TYPES
from src.ner.adapters.base import NERAdapter
from src.utils.logger import logger


class HanLPAdapter(NERAdapter):
    """HanLP NER 适配器 - 将 HanLP 输出转换为 StandardMention"""

    def __init__(self, model_name: str = "CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            logger.info(f"📦 加载 HanLP NER: {self.model_name}")
            self._model = hanlp.load(self.model_name)
            logger.info("✅ HanLP NER 加载完成")

    def _token_to_char_position(self, text: str, tokens: List[str],
                                token_start: int, token_end: int) -> Tuple[int, int]:
        """
        通过 token 文本在原始文本中查找字符位置

        Args:
            text: 原始文本
            tokens: token 列表（来自 tok/fine）
            token_start: 起始 token 索引
            token_end: 结束 token 索引（不含）

        Returns:
            (char_start, char_end): 字符级位置
        """
        # 获取 token 范围内的所有 token 文本
        token_texts = tokens[token_start:token_end]
        if not token_texts:
            return (0, 0)

        # 拼接 token 文本（注意：原始文本中 token 之间没有空格）
        target_text = "".join(token_texts)

        # 在原始文本中查找
        pos = text.find(target_text)
        if pos != -1:
            return (pos, pos + len(target_text))

        # 如果精确查找失败，尝试用第一个 token 定位
        # 这种情况可能发生在 token 有重叠时
        first_token = token_texts[0]
        pos = text.find(first_token)
        if pos != -1:
            # 从 pos 开始，尝试匹配所有 token
            current_pos = pos
            for tok in token_texts:
                if text[current_pos:current_pos + len(tok)] == tok:
                    current_pos += len(tok)
                else:
                    # 如果不匹配，尝试重新查找
                    return (0, 0)
            return (pos, current_pos)

        return (0, 0)

    def extract(self, text: str) -> List[StandardMention]:
        """从文本中提取实体，返回 StandardMention 列表"""
        self._load_model()
        result = self._model(text)
        mentions = []

        if not hasattr(result, 'to_dict'):
            logger.warning("⚠️ HanLP 返回结果不是 Document 对象")
            return mentions

        result_dict = result.to_dict()

        # 获取 token 列表（用于字符位置计算）
        tokens = result_dict.get('tok/fine', [])

        # 获取 NER 数据（优先使用 pku）
        ner_data = result_dict.get('ner/pku') or result_dict.get('ner/msra') or result_dict.get('ner/ontonotes')

        if not ner_data:
            return mentions

        for item in ner_data:
            if not (isinstance(item, (tuple, list)) and len(item) >= 4):
                continue

            entity_text = str(item[0])
            entity_type = str(item[1])
            token_start = int(item[2])
            token_end = int(item[3])

            # 类型映射
            mapped_type = TYPE_MAPPING.get(entity_type, entity_type)

            if mapped_type not in LINKABLE_TYPES or not entity_text:
                continue

            # Token 索引 → 字符级位置
            if tokens and token_start < len(tokens):
                char_start, char_end = self._token_to_char_position(
                    text, tokens, token_start, token_end
                )
            else:
                # 兜底：直接在文本中查找
                pos = text.find(entity_text)
                if pos != -1:
                    char_start = pos
                    char_end = pos + len(entity_text)
                else:
                    char_start = 0
                    char_end = 0

            # 创建 StandardMention
            mentions.append(StandardMention(
                mention=entity_text,
                mention_type=mapped_type,
                char_start=char_start,
                char_end=char_end
            ))

        return mentions

    def get_model_name(self) -> str:
        return f"hanlp_{self.model_name}"