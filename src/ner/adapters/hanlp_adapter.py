# src/ner/adapters/hanlp_adapter.py
from typing import List, Tuple, Dict, Set
import hanlp
from src.models.mention import StandardMention, TYPE_MAPPING, LINKABLE_TYPES
from src.ner.adapters.base import NERAdapter
from src.utils.logger import logger


class HanLPAdapter(NERAdapter):
    """
    HanLP NER 适配器

    合并三种 NER 标注体系（MSRA、PKU、Ontonotes）的识别结果，取并集以提高召回率。
    - MSRA: 英文标签（ORGANIZATION, PERSON, LOCATION）
    - PKU: 中文缩写标签（nt, nr, ns），中文专用，对简称识别较好
    - Ontonotes: 标准英文标签（ORG, PERSON, GPE），多语言统一
    """

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
        """
        # 获取 token 范围内的所有 token 文本
        token_texts = tokens[token_start:token_end]
        if not token_texts:
            return (0, 0)

        # 拼接 token 文本
        target_text = "".join(token_texts)

        # 在原始文本中查找
        pos = text.find(target_text)
        if pos != -1:
            return (pos, pos + len(target_text))

        # 兜底：直接用第一个 token 查找
        first_token = token_texts[0]
        pos = text.find(first_token)
        if pos != -1:
            current_pos = pos
            for tok in token_texts:
                if text[current_pos:current_pos + len(tok)] == tok:
                    current_pos += len(tok)
                else:
                    return (0, 0)
            return (pos, current_pos)

        return (0, 0)

    def _parse_ner_item(self, item, tokens: List[str], text: str) -> Dict:
        """
        解析单个 NER 条目

        Returns:
            {"mention": str, "type": str, "char_start": int, "char_end": int, "source": str}
        """
        if not (isinstance(item, (tuple, list)) and len(item) >= 4):
            return None

        entity_text = str(item[0])
        entity_type = str(item[1])
        token_start = int(item[2])
        token_end = int(item[3])

        # 类型映射
        mapped_type = TYPE_MAPPING.get(entity_type, entity_type)

        if mapped_type not in LINKABLE_TYPES or not entity_text:
            return None

        # Token 索引 → 字符级位置
        char_start, char_end = self._token_to_char_position(
            text, tokens, token_start, token_end
        )

        # 如果位置计算失败，用 text.find 兜底
        if char_start == 0 and char_end == 0:
            pos = text.find(entity_text)
            if pos != -1:
                char_start = pos
                char_end = pos + len(entity_text)

        return {
            "mention": entity_text,
            "type": mapped_type,
            "char_start": char_start,
            "char_end": char_end,
            "source": entity_type  # 记录原始标签，便于调试
        }

    # src/ner/adapters/hanlp_adapter.py

    def _merge_ner_results(self, all_results: List[Dict]) -> List[StandardMention]:
        """
        合并多个来源的 NER 结果，去重并处理冲突

        去重策略：
        1. 按 (char_start, char_end, mention) 精确去重
        2. 如果位置相同但 mention 不同，保留类型优先级更高的
        3. 如果 mention 相同但位置重叠，保留位置更精确的（区间更小）
        """
        # 类型优先级（越高越优先）
        type_priority = {
            "ORG": 3,
            "GPE": 3,
            "PERSON": 3,
            "LOC": 2,
            "UNKNOWN": 1
        }

        # 来源优先级（MSRA > Ontonotes > PKU）
        source_priority = {
            "msra": 3,
            "ontonotes": 2,
            "pku": 1
        }

        # ============================================================
        # 第一步：按 (char_start, char_end, mention) 精确去重
        # ============================================================
        unique: Dict[str, Dict] = {}

        for r in all_results:
            if not r:
                continue

            # 精确匹配 key：起始位置 + 结束位置 + mention 文本
            key = f"{r['char_start']}:{r['char_end']}:{r['mention']}"

            if key not in unique:
                unique[key] = r
            else:
                # 完全相同的实体，保留类型优先级更高的
                existing = unique[key]
                existing_priority = type_priority.get(existing["type"], 1)
                new_priority = type_priority.get(r["type"], 1)

                if new_priority > existing_priority:
                    unique[key] = r

        # ============================================================
        # 第二步：处理位置重叠但 mention 不同的情况
        # ============================================================
        # 转换为列表并排序（按起始位置）
        result_list = list(unique.values())
        result_list.sort(key=lambda x: (x["char_start"], x["char_end"]))

        # 处理重叠：如果两个实体位置相同但 mention 不同，保留类型优先级更高的
        final: Dict[str, Dict] = {}

        for r in result_list:
            key = f"{r['char_start']}:{r['char_end']}"

            if key not in final:
                final[key] = r
            else:
                # 相同位置，不同 mention，比较类型优先级
                existing = final[key]
                existing_priority = type_priority.get(existing["type"], 1)
                new_priority = type_priority.get(r["type"], 1)

                if new_priority > existing_priority:
                    final[key] = r
                elif new_priority == existing_priority:
                    # 优先级相同，比较来源优先级
                    existing_source = source_priority.get(existing.get("source", ""), 1)
                    new_source = source_priority.get(r.get("source", ""), 1)
                    if new_source > existing_source:
                        final[key] = r

        # ============================================================
        # 第三步：处理包含关系（A 包含 B 的情况）
        # ============================================================
        # 例如："国家电网有限公司" 和 "国家电网" 同时存在
        # 保留更长的（更完整）
        result_list = list(final.values())
        result_list.sort(key=lambda x: (x["char_start"], x["char_end"]))

        filtered = []
        for i, r in enumerate(result_list):
            is_contained = False

            # 检查是否被其他实体包含
            for j, other in enumerate(result_list):
                if i == j:
                    continue

                # 如果 other 完全包含 r（且 other 更长），则跳过 r
                if (other["char_start"] <= r["char_start"] and
                        other["char_end"] >= r["char_end"] and
                        other["char_end"] - other["char_start"] > r["char_end"] - r["char_start"]):
                    # 如果包含的实体类型不同，保留更重要的类型
                    if type_priority.get(other["type"], 1) >= type_priority.get(r["type"], 1):
                        is_contained = True
                        break

            if not is_contained:
                filtered.append(r)

        # ============================================================
        # 转换为 StandardMention
        # ============================================================
        results = []
        for r in filtered:
            results.append(StandardMention(
                mention=r["mention"],
                mention_type=r["type"],
                char_start=r["char_start"],
                char_end=r["char_end"]
            ))

        logger.debug(f"  合并后: {len(results)} 个实体")
        return results

    def extract(self, text: str) -> List[StandardMention]:
        """从文本中提取实体，合并三种 NER 来源"""
        self._load_model()
        result = self._model(text)

        if not hasattr(result, 'to_dict'):
            logger.warning("⚠️ HanLP 返回结果不是 Document 对象")
            return []

        result_dict = result.to_dict()
        tokens = result_dict.get('tok/fine', [])

        # ============================================================
        # 从三种来源提取 NER 结果
        # ============================================================
        all_results = []

        # 1. MSRA 来源
        for item in result_dict.get('ner/msra', []):
            parsed = self._parse_ner_item(item, tokens, text)
            if parsed:
                parsed["source"] = "msra"
                all_results.append(parsed)

        # 2. PKU 来源
        for item in result_dict.get('ner/pku', []):
            parsed = self._parse_ner_item(item, tokens, text)
            if parsed:
                parsed["source"] = "pku"
                all_results.append(parsed)

        # 3. Ontonotes 来源
        for item in result_dict.get('ner/ontonotes', []):
            parsed = self._parse_ner_item(item, tokens, text)
            if parsed:
                parsed["source"] = "ontonotes"
                all_results.append(parsed)

        logger.debug(f"  MSRA: {len(result_dict.get('ner/msra', []))} 个实体")
        logger.debug(f"  PKU: {len(result_dict.get('ner/pku', []))} 个实体")
        logger.debug(f"  Ontonotes: {len(result_dict.get('ner/ontonotes', []))} 个实体")
        logger.debug(f"  合并前: {len(all_results)} 个实体")

        # 合并去重
        mentions = self._merge_ner_results(all_results)

        logger.info(f"NER识别: {len(mentions)} 个实体: {[m.mention for m in mentions]}")
        return mentions

    def get_model_name(self) -> str:
        return f"hanlp_{self.model_name}"