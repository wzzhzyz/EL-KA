# src/core/llm_client.py
"""
通用 LLM 抽象层 - 兼容通义/智谱/OpenAI 多厂商 API

支持：
1. 通义千问 (Qwen) - dashscope
2. 智谱 (Zhipu) - zhipuai
3. OpenAI (GPT) - openai
4. 本地模型 (Local) - vLLM/Ollama
"""

import json
import time
import hashlib
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from src.utils.logger import logger


class LLMProvider(ABC):
    """LLM 提供商基类"""

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """执行对话"""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """获取模型名称"""
        pass


# ============================================================
# 具体实现：各厂商适配器
# ============================================================

class OpenAIProvider(LLMProvider):
    """OpenAI API 适配器"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = None, timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://api.openai.com/v1"
        self.timeout = timeout

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        import openai

        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 300)
        )

        return response.choices[0].message.content

    def get_model_name(self) -> str:
        return f"openai/{self.model}"


class QwenProvider(LLMProvider):
    """通义千问 API 适配器 (DashScope)"""

    def __init__(self, api_key: str, model: str = "qwen-turbo", base_url: str = None, timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.timeout = timeout

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        import openai

        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 300)
        )

        return response.choices[0].message.content

    def get_model_name(self) -> str:
        return f"qwen/{self.model}"


class ZhipuProvider(LLMProvider):
    """智谱 AI API 适配器"""

    def __init__(self, api_key: str, model: str = "glm-4-flash", base_url: str = None, timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://open.bigmodel.cn/api/paas/v4"
        self.timeout = timeout

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        import openai

        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 300)
        )

        return response.choices[0].message.content

    def get_model_name(self) -> str:
        return f"zhipu/{self.model}"


class LocalLLMProvider(LLMProvider):
    """本地 LLM 适配器 (vLLM / Ollama)"""

    def __init__(self, model: str = "qwen2.5-7b", base_url: str = "http://localhost:8000/v1", timeout: int = 60):
        self.model = model
        self.base_url = base_url
        self.timeout = timeout

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        import requests

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.1),
            "max_tokens": kwargs.get("max_tokens", 300)
        }

        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()

        result = response.json()
        return result["choices"][0]["message"]["content"]

    def get_model_name(self) -> str:
        return f"local/{self.model}"


# ============================================================
# 工厂类
# ============================================================

class LLMClientFactory:
    """LLM 客户端工厂"""

    PROVIDERS = {
        "openai": OpenAIProvider,
        "qwen": QwenProvider,
        "zhipu": ZhipuProvider,
        "local": LocalLLMProvider,
    }

    @classmethod
    def create(cls, config: Dict[str, Any]) -> LLMProvider:
        """
        根据配置创建 LLM 客户端

        Args:
            config: {
                "provider": "openai" | "qwen" | "zhipu" | "local",
                "api_key": "xxx",          # OpenAI/通义/智谱需要
                "model": "gpt-4o-mini",    # 模型名称
                "base_url": "https://...", # 可选
                "timeout": 30              # 超时时间
            }

        Returns:
            LLMProvider: LLM 客户端实例
        """
        provider = config.get("provider", "openai")
        api_key = config.get("api_key")
        model = config.get("model", "gpt-4o-mini")
        base_url = config.get("base_url")
        timeout = config.get("timeout", 30)

        if provider not in cls.PROVIDERS:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

        if provider != "local" and not api_key:
            raise ValueError(f"{provider} 需要 api_key")

        provider_class = cls.PROVIDERS[provider]
        return provider_class(api_key=api_key, model=model, base_url=base_url, timeout=timeout)


# ============================================================
# LLM 消歧客户端（带缓存和重试）
# ============================================================

class LLMDisambiguator:
    """
    LLM 消歧客户端 - 通用消歧调用

    功能：
    1. 支持多厂商 API
    2. 支持缓存
    3. 支持重试
    4. 支持结构化输出解析
    5. 支持关闭/开启切换
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: {
                "enabled": True,
                "provider": "openai",
                "api_key": "xxx",
                "model": "gpt-4o-mini",
                "base_url": "https://...",
                "timeout": 30,
                "max_retries": 2,
                "cache_enabled": True,
                "cache_ttl": 86400,  # 24小时
                "trigger_threshold": 0.55,  # BGE分数低于此值触发
            }
        """
        self.enabled = config.get("enabled", False)
        self.trigger_threshold = config.get("trigger_threshold", 0.55)
        self.max_retries = config.get("max_retries", 2)
        self.cache_enabled = config.get("cache_enabled", True)
        self.cache_ttl = config.get("cache_ttl", 86400)

        self._provider = None
        self._cache = {}
        self._stats = {
            "calls": 0,
            "cache_hits": 0,
            "errors": 0,
            "avg_time": 0.0
        }

        if self.enabled:
            try:
                self._provider = LLMClientFactory.create(config)
                logger.info(f"✅ LLM 消歧客户端初始化: {self._provider.get_model_name()}")
                logger.info(f"   ⚡ 触发阈值: {self.trigger_threshold}")
                logger.info(f"   💾 缓存: {'启用' if self.cache_enabled else '禁用'}")
            except Exception as e:
                logger.error(f"❌ LLM 客户端初始化失败: {e}")
                self.enabled = False

    def _get_cache_key(self, messages: List[Dict], model: str) -> str:
        """生成缓存键"""
        content = json.dumps(messages, ensure_ascii=False) + model
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _call_with_retry(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """带重试的 LLM 调用"""
        if self._provider is None:
            return None

        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()
                result = self._provider.chat(messages)
                elapsed = time.time() - start_time

                # 更新统计
                self._stats["calls"] += 1
                self._stats["avg_time"] = (
                    self._stats["avg_time"] * (self._stats["calls"] - 1) + elapsed
                ) / self._stats["calls"]

                logger.debug(f"  🤖 LLM 响应 (尝试 {attempt+1}): {elapsed:.2f}s")
                return result

            except Exception as e:
                logger.warning(f"  ⚠️ LLM 尝试 {attempt+1} 失败: {e}")
                if attempt == self.max_retries:
                    self._stats["errors"] += 1
                    return None
                time.sleep(1)

        return None

    def disambiguate(self, query: str, candidates: List[Dict], context: str = "",
                     mention_type: str = "") -> Dict[str, Any]:
        """
        执行 LLM 消歧

        Args:
            query: 查询文本（mention + 上下文）
            candidates: 候选列表 [{"entity_id": "xxx", "standard_name": "xxx", "description": "xxx", "score": 0.5}, ...]
            context: 上下文
            mention_type: 实体类型

        Returns:
            {
                "entity_id": "xxx" or "NIL",
                "reason": "选择理由",
                "confidence": 0.0-1.0
            }
        """
        if not self.enabled:
            return {"entity_id": "NIL", "reason": "LLM已禁用", "confidence": 0.0}

        if not candidates:
            return {"entity_id": "NIL", "reason": "无候选", "confidence": 0.0}

        # 构建消息
        messages = self._build_llm_messages(query, candidates, context, mention_type)

        # 检查缓存
        cache_key = self._get_cache_key(messages, self._provider.get_model_name())
        if self.cache_enabled and cache_key in self._cache:
            entry = self._cache[cache_key]
            if datetime.now() - entry["timestamp"] < timedelta(seconds=self.cache_ttl):
                self._stats["cache_hits"] += 1
                logger.debug(f"  💾 LLM 缓存命中")
                return entry["result"]

        # 调用 LLM
        content = self._call_with_retry(messages)
        if content is None:
            return {"entity_id": "NIL", "reason": "LLM调用失败", "confidence": 0.0}

        # 解析响应
        result = self._parse_response(content, candidates)

        # 缓存结果
        if self.cache_enabled:
            self._cache[cache_key] = {
                "result": result,
                "timestamp": datetime.now()
            }
            # 限制缓存大小
            if len(self._cache) > 1000:
                sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k]["timestamp"])
                for k in sorted_keys[:500]:
                    del self._cache[k]

        return result

    def _build_llm_messages(self, query: str, candidates: List[Dict], context: str,
                            mention_type: str) -> List[Dict[str, str]]:
        """构建 LLM 消息"""
        # 构建候选描述
        candidate_descs = []
        for i, cand in enumerate(candidates[:10], 1):
            desc = f"候选{i}: "
            desc += f"ID={cand.get('entity_id', '')}, "
            desc += f"名称={cand.get('standard_name', '')}"
            if cand.get('description'):
                desc += f", 描述={cand.get('description', '')[:100]}"
            if cand.get('entity_type'):
                desc += f", 类型={cand.get('entity_type', '')}"
            desc += f", BGE分数={cand.get('score', 0.0):.3f}"
            candidate_descs.append(desc)

        candidates_text = "\n".join(candidate_descs)

        system_prompt = """你是一个专业的实体链接消歧助手。根据上下文判断"提及"最可能指代哪个候选实体。

【输出格式】
必须输出JSON格式：
{"entity_id": "实体ID或NIL", "reason": "选择理由", "confidence": 0.0-1.0}

注意：
- entity_id必须从候选列表中选择
- 如果都不匹配，输出"NIL"
- confidence表示确信度"""

        type_hint = f"（类型：{mention_type}）" if mention_type and mention_type != "UNKNOWN" else ""

        user_prompt = f"""【提及】
{query} {type_hint}

【上下文】
{context[:500] if context else "（无上下文）"}

【候选实体】
{candidates_text}

请选择最匹配的实体。"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def _parse_response(self, content: str, candidates: List[Dict]) -> Dict[str, Any]:
        """解析 LLM 响应"""
        import re

        # 尝试提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                result = json.loads(json_match.group())
                entity_id = result.get("entity_id", "NIL")
                # 验证 entity_id 是否在候选中
                if entity_id != "NIL":
                    valid = any(c.get("entity_id") == entity_id for c in candidates)
                    if not valid:
                        logger.warning(f"  ⚠️ LLM 返回无效 entity_id: {entity_id}")
                        return {"entity_id": "NIL", "reason": "返回无效实体ID", "confidence": 0.0}
                return {
                    "entity_id": entity_id,
                    "reason": result.get("reason", "LLM判断"),
                    "confidence": result.get("confidence", 0.7)
                }
            except json.JSONDecodeError:
                pass

        # 尝试提取 entity_id
        id_match = re.search(r'[a-zA-Z0-9_]+', content)
        if id_match:
            entity_id = id_match.group()
            if entity_id != "NIL":
                valid = any(c.get("entity_id") == entity_id for c in candidates)
                if not valid:
                    return {"entity_id": "NIL", "reason": "无法解析LLM响应", "confidence": 0.0}
            return {"entity_id": entity_id, "reason": "从响应中提取", "confidence": 0.6}

        if "NIL" in content.upper():
            return {"entity_id": "NIL", "reason": "LLM判定为NIL", "confidence": 0.7}

        return {"entity_id": "NIL", "reason": "无法解析LLM响应", "confidence": 0.0}

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "enabled": self.enabled,
            "calls": self._stats["calls"],
            "cache_hits": self._stats["cache_hits"],
            "errors": self._stats["errors"],
            "avg_time": self._stats["avg_time"],
            "cache_size": len(self._cache)
        }

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("💾 LLM 缓存已清空")

    def is_enabled(self) -> bool:
        return self.enabled

    def set_enabled(self, enabled: bool):
        """动态开关 LLM"""
        self.enabled = enabled
        logger.info(f"🔄 LLM 消歧已{'启用' if enabled else '禁用'}")