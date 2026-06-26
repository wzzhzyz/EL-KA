# src/core/ner.py
from typing import List, Dict
import hanlp
from src.utils.logger import logger


class NEREngine:
    def __init__(self, config: dict):
        self.model_name = config.get("hanlp_model", "CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH")
        self.linkable_types = set(config.get("linkable_types", ["ORG", "PERSON", "GPE", "LOC"]))
        self._model = None

    def _load_model(self):
        if self._model is None:
            logger.info(f"📦 加载HanLP NER: {self.model_name}")
            self._model = hanlp.load(self.model_name)
            logger.info("✅ NER加载完成")

    def extract(self, text: str) -> List[Dict]:
        self._load_model()
        result = self._model(text)

        mentions = []

        # 检查是否是 HanLP Document 对象
        if hasattr(result, 'to_dict'):
            # 转换为字典
            result_dict = result.to_dict()

            # 尝试从不同的 NER 字段提取（优先使用 pku，因为识别最完整）
            ner_data = None
            if 'ner/pku' in result_dict:
                ner_data = result_dict['ner/pku']
            elif 'ner/msra' in result_dict:
                ner_data = result_dict['ner/msra']
            elif 'ner/ontonotes' in result_dict:
                ner_data = result_dict['ner/ontonotes']

            if ner_data:
                for item in ner_data:
                    # 格式: ["实体文本", "类型", 开始, 结束]
                    if isinstance(item, (tuple, list)) and len(item) >= 4:
                        entity_text = str(item[0])
                        entity_type = str(item[1])
                        begin = int(item[2])
                        end = int(item[3])

                        # 类型映射：将 HanLP 的类型映射到标准类型
                        type_mapping = {
                            'ORGANIZATION': 'ORG',
                            'ORG': 'ORG',
                            'nt': 'ORG',
                            'PERSON': 'PERSON',
                            'nr': 'PERSON',
                            'LOCATION': 'GPE',
                            'LOC': 'GPE',
                            'ns': 'GPE',
                            'GPE': 'GPE'
                        }
                        mapped_type = type_mapping.get(entity_type, entity_type)

                        if mapped_type in self.linkable_types and entity_text:
                            mentions.append({
                                "mention": entity_text,
                                "type": mapped_type,
                                "start": begin,
                                "end": end
                            })

        # 如果上面的解析失败，尝试直接遍历（兼容其他格式）
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    entity_text = item.get("text", "")
                    entity_type = item.get("type", "")
                    begin = item.get("begin", 0)
                    end = item.get("end", 0)

                    if entity_type in self.linkable_types and entity_text:
                        mentions.append({
                            "mention": entity_text,
                            "type": entity_type,
                            "start": begin,
                            "end": end
                        })

        logger.info(f"NER识别: {len(mentions)} 个实体: {[m['mention'] for m in mentions]}")
        return mentions