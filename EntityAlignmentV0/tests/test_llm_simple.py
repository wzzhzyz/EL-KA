# tests/test_llm_simple.py
"""
简单测试LLM调用
"""

import sys
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.disambiguate import Disambiguator
from src.models.candidate import Candidate
from src.utils.config import load_config


def test_llm_simple():
    """简单测试LLM调用"""

    config = load_config()

    # 检查配置
    llm_config = config.get("llm_fallback", {})
    if not llm_config.get("enabled"):
        print("❌ LLM未启用，请在config.yaml中启用")
        return

    api_key = llm_config.get("api_key")
    if not api_key or api_key == "your-api-key-here":
        print("❌ 请先配置有效的API Key")
        return

    model = llm_config.get("model", "qwen-turbo")
    print(f"📋 配置: model={model}")
    print(f"   api_key={api_key[:10]}...{api_key[-4:]}")

    # 创建消歧器
    disambiguator = Disambiguator(config)

    # 简单测试 - 直接调用API
    try:
        system_prompt = "你是一个助手，请用JSON格式回复"
        user_prompt = '{"test": "OK"}'

        # 测试_call_openai方法
        result = disambiguator._call_openai(system_prompt, user_prompt)
        print(f"✅ LLM调用成功: {result}")
    except Exception as e:
        print(f"❌ LLM调用失败: {e}")


def test_disambiguate_with_llm():
    """测试完整的消歧流程（含LLM）"""

    from src.models.entity import StandardEntity

    config = load_config()

    # 确保LLM启用
    config["llm_fallback"]["enabled"] = True

    disambiguator = Disambiguator(config)

    # 创建测试实体
    entity = StandardEntity(
        entity_id="company_001",
        standard_name="国家电网有限公司",
        entity_type="ORG",
        description="中国最大的电力企业"
    )

    # 创建候选
    from src.models.candidate import Candidate
    candidates = [
        Candidate(entity=entity, score=0.55, method="vector")
    ]

    print("\n📝 测试消歧（含LLM）:")
    print(f"   mention: 国网")
    print(f"   context: 国网在电力行业")
    print(f"   候选: {entity.standard_name} (分数: 0.55)")
    print(f"   LLM触发阈值: {disambiguator.llm_trigger_threshold}")

    try:
        result = disambiguator.disambiguate(
            "国网", candidates, "国网在电力行业"
        )
        print(f"\n✅ 消歧结果:")
        print(f"   实体: {result['entity'].standard_name if result['entity'] else 'NIL'}")
        print(f"   分数: {result['score']:.3f}")
        print(f"   方法: {result['method']}")
        print(f"   依据: {result['evidence']}")
    except Exception as e:
        print(f"❌ 消歧失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 80)
    print("LLM简单测试")
    print("=" * 80)

    # 先测试简单调用
    test_llm_simple()

    # 再测试完整流程
    test_disambiguate_with_llm()