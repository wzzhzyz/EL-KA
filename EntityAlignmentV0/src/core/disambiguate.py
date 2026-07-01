# src/core/disambiguate.py
import numpy as np
import json
import hashlib
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer
from src.models.entity import StandardEntity
from src.models.candidate import Candidate
from src.utils.logger import logger


class Disambiguator:
    """消歧排序：BGE 语义相似度 + LLM 兜底（可选）"""

    def __init__(self, config):
        bge_path = config.get("bge_model_path", "./models_cache/bge-small-zh")
        self.bge_model = SentenceTransformer(bge_path)

        self.nil_threshold = config.get("disambiguator", {}).get("nil_threshold", 0.65)
        self.llm_trigger_threshold = config.get("disambiguator", {}).get("bge_llm_trigger_threshold", 0.65)

        # LLM 兜底配置
        llm_config = config.get("llm_fallback", {})
        self.enable_llm = llm_config.get("enabled", False)
        self.llm_provider = llm_config.get("provider", "openai")
        self.llm_api_key = llm_config.get("api_key")
        self.llm_model = llm_config.get("model", "gpt-4o-mini")
        self.llm_base_url = llm_config.get("base_url")
        self.llm_timeout = llm_config.get("timeout", 10)
        self.llm_max_retries = llm_config.get("max_retries", 2)

        # 缓存配置
        self.cache_enabled = config.get("llm_fallback", {}).get("cache_enabled", True)
        self.cache_ttl = config.get("llm_fallback", {}).get("cache_ttl", 86400)  # 24小时
        self._cache = {}  # 内存缓存

        # 统计信息
        self.stats = {
            "bge_calls": 0,
            "llm_calls": 0,
            "llm_cache_hits": 0,
            "llm_errors": 0,
            "avg_llm_time": 0.0,
            "nil_by_bge": 0,
            "nil_by_llm": 0
        }

        logger.info("✅ 消歧器初始化完成")
        logger.info(f"   📊 NIL阈值: {self.nil_threshold}")
        if self.enable_llm:
            logger.info(f"   🤖 LLM兜底已启用: {self.llm_provider}/{self.llm_model}")
            logger.info(f"   ⚡ 触发阈值: {self.llm_trigger_threshold}")
            logger.info(f"   💾 缓存: {'启用' if self.cache_enabled else '禁用'}")
        else:
            logger.info("   ℹ️ LLM兜底未启用")

    def _build_query_text(self, mention: str, context: str = "") -> str:
        """
        构建结构化的 query 文本（消歧专用）

        Args:
            mention: 实体指称
            context: 上下文文本

        Returns:
            结构化的 query 字符串
        """
        if context and context.strip():
            context_text = context[:300]
            return f"query: 上下文中的mention指的是什么？上下文：{context_text}，mention：{mention}"
        else:
            return f"query: 实体指称 {mention} 指的是什么？"

    def _build_passage_text(self, entity: StandardEntity) -> str:
        """
        构建结构化的 passage 文本（消歧专用）

        Args:
            entity: 标准实体

        Returns:
            结构化的 passage 字符串
        """
        text = f"标准实体名：{entity.standard_name}"

        if entity.aliases:
            aliases_str = "、".join(entity.aliases[:5])
            text += f"，别名：{aliases_str}"

        if entity.entity_type and entity.entity_type != "UNKNOWN":
            text += f"，类型：{entity.entity_type}"

        if entity.description:
            text += f"，描述：{entity.description}"

        industry = entity.metadata.get("industry", "")
        if industry:
            text += f"，所属行业：{industry}"

        tags = entity.metadata.get("tags", [])
        if tags:
            tags_str = "、".join(tags[:5])
            text += f"，标签：{tags_str}"

        return f"passage: {text}"

    def _bge_rank(self, mention: str, candidates: List[Candidate], context: str = "") -> List[Candidate]:
        """
        使用 BGE 计算语义相似度并排序（使用结构化 query/passage 提示）
        """
        if not candidates:
            return []

        self.stats["bge_calls"] += 1

        # 构建结构化的 query
        query_text = self._build_query_text(mention, context)

        # 构建候选文本（结构化 passage 提示）
        candidate_texts = []
        for cand in candidates:
            entity = cand.entity
            passage_text = self._build_passage_text(entity)
            candidate_texts.append(passage_text)

        # 编码
        mention_emb = self.bge_model.encode([query_text], normalize_embeddings=True)
        cand_embs = self.bge_model.encode(candidate_texts, normalize_embeddings=True)

        # 计算余弦相似度（内积，因为已归一化）
        scores = np.dot(cand_embs, mention_emb.T).flatten()

        # 更新分数并排序
        for i, cand in enumerate(candidates):
            cand.score = float(scores[i])

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def _get_cache_key(self, mention: str, context: str, candidate_ids: List[str]) -> str:
        """生成缓存键"""
        data = f"{mention}|{context[:200]}|{','.join(candidate_ids)}"
        return hashlib.md5(data.encode('utf-8')).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """从缓存获取结果"""
        if not self.cache_enabled:
            return None

        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() - entry["timestamp"] < timedelta(seconds=self.cache_ttl):
                self.stats["llm_cache_hits"] += 1
                logger.debug(f"  💾 LLM缓存命中: {key[:8]}")
                return entry["result"]
            else:
                del self._cache[key]
        return None

    def _set_cache(self, key: str, result: Dict):
        """存入缓存"""
        if self.cache_enabled:
            self._cache[key] = {
                "result": result,
                "timestamp": datetime.now()
            }
            if len(self._cache) > 1000:
                sorted_keys = sorted(self._cache.keys(),
                                     key=lambda k: self._cache[k]["timestamp"])
                for k in sorted_keys[:500]:
                    del self._cache[k]

    def _build_llm_prompt(self, mention: str, candidates: List[Candidate], context: str) -> tuple:
        """
        构建LLM提示词（使用结构化信息）
        """
        # 构建候选列表描述（使用结构化信息）
        candidate_descriptions = []
        for i, cand in enumerate(candidates[:10], 1):
            entity = cand.entity

            # 构建结构化的候选描述
            desc = f"ID: {entity.entity_id}"
            desc += f", 标准实体名：{entity.standard_name}"

            if entity.aliases:
                aliases_str = "、".join(entity.aliases[:5])
                desc += f", 别名：{aliases_str}"

            if entity.entity_type and entity.entity_type != "UNKNOWN":
                desc += f", 类型：{entity.entity_type}"

            if entity.description:
                desc += f", 描述：{entity.description[:100]}"

            industry = entity.metadata.get("industry", "")
            if industry:
                desc += f", 所属行业：{industry}"

            tags = entity.metadata.get("tags", [])
            if tags:
                tags_str = "、".join(tags[:3])
                desc += f", 标签：{tags_str}"

            desc += f", BGE相似度：{cand.score:.3f}"
            candidate_descriptions.append(f"{i}. {desc}")

        candidates_text = "\n".join(candidate_descriptions)

        system_prompt = """你是一个专业的实体链接助手。你的任务是根据给定的上下文，从候选实体列表中选择最匹配的实体。

【重要】NIL检测规则：
1. 如果没有任何候选实体与上下文中提及的实体匹配，必须输出"NIL"
2. 以下几种情况应判定为NIL：
   a) 所有候选实体都与上下文语义不相关（BGE分数普遍较低）
   b) 候选实体虽然名称相似，但类型/领域完全不匹配
   c) 上下文中的提及是一个通用词汇，没有特指某个具体实体
   d) 候选实体都不符合上下文中描述的实体特征
3. 如果多个候选实体都部分匹配，但都不完全匹配，倾向于输出"NIL"
4. NIL判断的阈值：宁可多输出NIL，也不要把错误实体链接上

输出格式要求：
- 必须输出JSON格式
- 如果选择实体：{"entity_id": "实体ID", "reason": "选择理由", "confidence": 0.0-1.0}
- 如果选择NIL：{"entity_id": "NIL", "reason": "NIL判定理由", "confidence": 0.0-1.0}

注意：
- entity_id必须从候选列表中选取（或NIL）
- 请基于上下文语义做判断，而不仅仅依赖名称相似度
- 如果BGE分数普遍低于0.5，强烈建议输出NIL"""

        user_prompt = f"""上下文：
{context}

待链接的提及："{mention}"

候选实体列表：
{candidates_text}

请选择最匹配的实体，或判定为NIL。"""

        return system_prompt, user_prompt

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        """调用OpenAI API（百炼兼容模式）"""
        try:
            import openai
        except ImportError:
            raise ImportError("请安装openai: pip install openai")

        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        model_name = self.llm_model
        if model_name == "qwen":
            model_name = "qwen-turbo"

        client = openai.OpenAI(
            api_key=self.llm_api_key,
            base_url=base_url,
            timeout=self.llm_timeout
        )

        try:
            logger.info(f"  🤖 调用LLM: model={model_name}")

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )

            if response is None:
                raise ValueError("API返回空响应")

            if not hasattr(response, 'choices') or response.choices is None:
                raise ValueError("API响应缺少choices字段")

            if len(response.choices) == 0:
                raise ValueError("API返回空choices列表")

            choice = response.choices[0]
            if choice is None:
                raise ValueError("API返回的choice为None")

            if not hasattr(choice, 'message') or choice.message is None:
                raise ValueError("API响应缺少message字段")

            message = choice.message

            if not hasattr(message, 'content') or message.content is None:
                raise ValueError("API响应缺少content字段")

            content = message.content
            if not content or not content.strip():
                raise ValueError("API返回空内容")

            display_content = content[:200] + "..." if len(content) > 200 else content
            logger.info(f"  ✅ LLM响应内容: {display_content}")

            return content

        except Exception as e:
            logger.error(f"  ❌ LLM调用失败: {e}")
            raise

    def _safe_parse_response(self, content: str) -> Dict:
        """安全解析LLM响应"""
        if isinstance(content, dict):
            return content

        if not content or not isinstance(content, str):
            return {"entity_id": "NIL", "reason": "无效响应", "confidence": 0.0}

        content = content.strip()

        # 尝试1：直接JSON解析
        try:
            return json.loads(content)
        except:
            pass

        # 尝试2：提取JSON代码块
        import re
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, content)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass

        # 尝试3：提取JSON对象
        json_pattern = r'\{[\s\S]*\}'
        match = re.search(json_pattern, content)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass

        # 尝试4：提取 entity_id
        id_pattern = r'"entity_id"\s*:\s*"([^"]+)"'
        match = re.search(id_pattern, content)
        if match:
            entity_id = match.group(1)
            reason_pattern = r'"reason"\s*:\s*"([^"]+)"'
            reason_match = re.search(reason_pattern, content)
            reason = reason_match.group(1) if reason_match else "从响应中提取"
            conf_pattern = r'"confidence"\s*:\s*([0-9.]+)'
            conf_match = re.search(conf_pattern, content)
            confidence = float(conf_match.group(1)) if conf_match else 0.8
            return {
                "entity_id": entity_id,
                "reason": reason,
                "confidence": confidence
            }

        # 尝试5：检查是否包含NIL
        if "NIL" in content.upper():
            return {
                "entity_id": "NIL",
                "reason": f"响应中包含NIL: {content[:100]}",
                "confidence": 0.7
            }

        return {
            "entity_id": "NIL",
            "reason": f"无法解析响应: {content[:100]}",
            "confidence": 0.0
        }

    def _llm_disambiguate(self, mention: str, candidates: List[Candidate], context: str) -> Dict:
        """LLM兜底消歧（包含NIL检测）"""
        candidate_ids = [c.entity.entity_id for c in candidates[:10]]
        cache_key = self._get_cache_key(mention, context, candidate_ids)

        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        start_time = time.time()

        for attempt in range(self.llm_max_retries + 1):
            try:
                logger.info(f"  🤖 LLM尝试 {attempt + 1}/{self.llm_max_retries + 1}")

                system_prompt, user_prompt = self._build_llm_prompt(mention, candidates, context)
                raw_content = self._call_openai(system_prompt, user_prompt)
                result = self._safe_parse_response(raw_content)

                elapsed = time.time() - start_time

                if self.stats["llm_calls"] > 0:
                    self.stats["avg_llm_time"] = (
                                                         self.stats["avg_llm_time"] * (
                                                             self.stats["llm_calls"] - 1) + elapsed
                                                 ) / self.stats["llm_calls"]
                else:
                    self.stats["avg_llm_time"] = elapsed

                logger.info(f"  ✅ LLM解析结果: {result}")

                if "error" in result:
                    raise Exception(result["error"])

                entity_id = result.get("entity_id", "NIL")
                reason = result.get("reason", "")
                confidence = result.get("confidence", 0.5)

                if entity_id == "NIL":
                    self.stats["nil_by_llm"] += 1
                    llm_result = {
                        "entity": None,
                        "score": 0.0,
                        "method": "llm_nil",
                        "evidence": f"LLM判定为NIL: {reason} (置信度: {confidence:.2f})"
                    }
                else:
                    found_entity = None
                    for cand in candidates:
                        if cand.entity.entity_id == entity_id:
                            found_entity = cand.entity
                            break

                    if found_entity:
                        llm_result = {
                            "entity": found_entity,
                            "score": confidence,
                            "method": "llm",
                            "evidence": f"LLM选择: {reason} (置信度: {confidence:.2f})"
                        }
                    else:
                        self.stats["nil_by_llm"] += 1
                        llm_result = {
                            "entity": None,
                            "score": 0.0,
                            "method": "llm_nil",
                            "evidence": f"LLM返回无效实体ID: {entity_id}"
                        }

                self._set_cache(cache_key, llm_result)
                return llm_result

            except Exception as e:
                logger.warning(f"  ⚠️ LLM尝试 {attempt + 1}/{self.llm_max_retries + 1} 失败: {e}")
                if attempt == self.llm_max_retries:
                    return {
                        "entity": None,
                        "score": 0.0,
                        "method": "llm_failed_nil",
                        "evidence": f"LLM调用失败，保守判定为NIL: {e}"
                    }
                time.sleep(1)

        return {
            "entity": None,
            "score": 0.0,
            "method": "llm_fallback_nil",
            "evidence": "LLM重试全部失败，保守判定为NIL"
        }

    def _call_llm(self, mention: str, candidates: List[Candidate], context: str) -> Dict:
        """调用LLM进行消歧（包含NIL检测）- 入口方法"""
        self.stats["llm_calls"] += 1
        return self._llm_disambiguate(mention, candidates, context)

    def _call_azure(self, system_prompt: str, user_prompt: str) -> Dict:
        """调用Azure OpenAI API"""
        try:
            from openai import AzureOpenAI
        except ImportError:
            raise ImportError("请安装openai: pip install openai")

        client = AzureOpenAI(
            api_key=self.llm_api_key,
            azure_endpoint=self.llm_base_url,
            api_version="2024-02-15-preview",
            timeout=self.llm_timeout
        )

        response = client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=300
        )

        content = response.choices[0].message.content
        return json.loads(content)

    def _call_local_llm(self, system_prompt: str, user_prompt: str) -> Dict:
        """调用本地LLM"""
        try:
            import requests
        except ImportError:
            raise ImportError("请安装requests: pip install requests")

        url = self.llm_base_url or "http://localhost:8000/v1/chat/completions"

        payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 300,
            "response_format": {"type": "json_object"}
        }

        headers = {"Content-Type": "application/json"}
        if self.llm_api_key:
            headers["Authorization"] = f"Bearer {self.llm_api_key}"

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.llm_timeout
        )
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]
        return json.loads(content)

    def _check_nil_by_bge(self, ranked_candidates: List[Candidate]) -> bool:
        """
        基于BGE分数判断是否为NIL

        判断策略：
        1. 最高分低于阈值 → NIL
        2. 最高分与次高分差距过小（无明显区分度）→ NIL
        3. 所有分数都普遍偏低 → NIL
        """
        if not ranked_candidates:
            return True

        top = ranked_candidates[0]

        # 策略1：最高分低于阈值
        if top.score < self.nil_threshold:
            logger.info(f"  📊 BGE NIL判定: 最高分 {top.score:.3f} < 阈值 {self.nil_threshold}")
            return True

        # 策略2：最高分与次高分差距过小（歧义大）
        if len(ranked_candidates) >= 2:
            second = ranked_candidates[1]
            gap = top.score - second.score
            if gap < 0.1 and top.score < 0.75:
                logger.info(f"  📊 BGE NIL判定: 最高分 {top.score:.3f}, 次高分 {second.score:.3f}, 差距 {gap:.3f} < 0.1")
                return True

        # 策略3：所有分数都偏低（平均分 < 阈值-0.1）
        if len(ranked_candidates) >= 3:
            avg_score = sum(c.score for c in ranked_candidates[:3]) / 3
            if avg_score < self.nil_threshold - 0.1:
                logger.info(f"  📊 BGE NIL判定: 平均分 {avg_score:.3f} < {self.nil_threshold - 0.1:.3f}")
                return True

        return False

    def disambiguate(self, mention: str, candidates: List[Candidate], context: str = "") -> Dict[str, Any]:
        """
        消歧主入口（包含完整的NIL检测逻辑）

        Returns:
            {
                "entity": StandardEntity or None,  # None表示NIL
                "score": float,
                "method": str,  # "bge", "bge_nil", "llm", "llm_nil", "bge_fallback"
                "evidence": str
            }
        """
        if not candidates:
            return {
                "entity": None,
                "score": 0.0,
                "method": "none",
                "evidence": "无候选实体 → NIL"
            }

        # 如果只有一个候选，用阈值判断
        if len(candidates) == 1:
            single_cand = candidates[0]
            ranked = self._bge_rank(mention, candidates, context)
            if ranked and ranked[0].score >= self.nil_threshold:
                return {
                    "entity": ranked[0].entity,
                    "score": ranked[0].score,
                    "method": "bge_single",
                    "evidence": f"唯一候选且分数 {ranked[0].score:.3f} >= 阈值 {self.nil_threshold}"
                }
            else:
                self.stats["nil_by_bge"] += 1
                return {
                    "entity": None,
                    "score": ranked[0].score if ranked else 0.0,
                    "method": "bge_nil",
                    "evidence": f"唯一候选分数 {ranked[0].score if ranked else 0:.3f} < 阈值 {self.nil_threshold} → NIL"
                }

        # 多候选：BGE排序（使用结构化提示）
        ranked = self._bge_rank(mention, candidates, context)
        if not ranked:
            return {
                "entity": None,
                "score": 0.0,
                "method": "none",
                "evidence": "BGE 计算失败 → NIL"
            }

        top = ranked[0]

        # 记录BGE结果
        logger.info(f"  📊 BGE消歧: {mention} → {top.entity.standard_name} (分数: {top.score:.3f})")
        if len(ranked) > 1:
            logger.info(f"      次优: {ranked[1].entity.standard_name} (分数: {ranked[1].score:.3f})")

        # ============================================================
        # Step 1: BGE NIL检测
        # ============================================================
        if self._check_nil_by_bge(ranked):
            self.stats["nil_by_bge"] += 1
            nil_reason = f"BGE NIL判定: 最高分 {top.score:.3f}"
            if len(ranked) >= 2:
                nil_reason += f", 次高分 {ranked[1].score:.3f}"
            logger.info(f"  ❌ BGE判定为NIL")

            if self.enable_llm:
                logger.info(f"  🤖 BGE判定NIL，触发LLM二次确认")
                llm_result = self._llm_disambiguate(mention, ranked, context)
                if llm_result.get("entity") is not None:
                    logger.info(f"  ✅ LLM确认有实体: {llm_result['entity'].standard_name}")
                    return llm_result
                else:
                    logger.info(f"  ✅ LLM也判定为NIL")
                    self.stats["nil_by_llm"] += 1
                    return {
                        "entity": None,
                        "score": 0.0,
                        "method": "bge_llm_nil",
                        "evidence": f"BGE和LLM均判定为NIL: {nil_reason}"
                    }

            return {
                "entity": None,
                "score": top.score,
                "method": "bge_nil",
                "evidence": nil_reason
            }

        # ============================================================
        # Step 2: BGE通过NIL检测，检查是否需要LLM兜底
        # ============================================================
        if self.enable_llm and top.score < self.llm_trigger_threshold:
            logger.info(f"  🤖 BGE分数 {top.score:.3f} < 阈值 {self.llm_trigger_threshold}，触发LLM兜底")

            llm_result = self._llm_disambiguate(mention, ranked, context)

            if llm_result.get("entity") is not None:
                logger.info(f"  ✅ LLM选择实体: {llm_result['entity'].standard_name}")
                return {
                    "entity": llm_result["entity"],
                    "score": llm_result["score"],
                    "method": "llm",
                    "evidence": llm_result["evidence"]
                }
            elif llm_result.get("method") in ["llm_nil", "llm_failed_nil"]:
                self.stats["nil_by_llm"] += 1
                logger.info(f"  ❌ LLM判定为NIL，覆盖BGE结果")
                return {
                    "entity": None,
                    "score": 0.0,
                    "method": "llm_nil_override",
                    "evidence": llm_result["evidence"]
                }
            else:
                logger.info(f"  ⚠️ LLM异常，回退到BGE结果")
                return {
                    "entity": top.entity,
                    "score": top.score,
                    "method": "bge_fallback",
                    "evidence": f"LLM异常，使用BGE结果: {top.entity.standard_name} (分数: {top.score:.3f})"
                }

        # ============================================================
        # Step 3: 返回BGE结果（正常情况）
        # ============================================================
        return {
            "entity": top.entity,
            "score": top.score,
            "method": "bge",
            "evidence": f"BGE语义相似度: {top.score:.3f} (来源: {top.method})"
        }

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "bge_calls": self.stats["bge_calls"],
            "llm_calls": self.stats["llm_calls"],
            "llm_cache_hits": self.stats["llm_cache_hits"],
            "llm_errors": self.stats["llm_errors"],
            "avg_llm_time": self.stats["avg_llm_time"],
            "cache_size": len(self._cache),
            "nil_by_bge": self.stats["nil_by_bge"],
            "nil_by_llm": self.stats["nil_by_llm"]
        }

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("💾 LLM缓存已清空")