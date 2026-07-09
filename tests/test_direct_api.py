# tests/test_api_direct.py
"""
直接测试百炼API，不通过disambiguate模块
"""

import openai
import json
import os


def test_api_direct():
    """直接测试百炼API"""

    # 从环境变量或直接配置
    api_key = "sk-ws-H.RERDMME.mtnS.MEYCIQC52O9l9Bdvlaq-cxsuVO6isL-njt7bRLHTvo9r0jR5RQIhAMenFxknVyXygcQM3u9V_lkT4JuI6W1aDH_DqfQ3ogsH"  # 替换为您的实际API Key
    base_url = "https://ws-nf0fhf5rgskiv5w2.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    model = "qwen-max"

    print("=" * 80)
    print("直接测试百炼API")
    print("=" * 80)
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    print("-" * 80)

    client = openai.OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=30
    )

    # 测试1：简单对话
    print("\n📝 测试1: 简单对话")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "你好，请用JSON格式回复 {'status': 'ok'}"}
            ],
            temperature=0.1,
            max_tokens=50
        )

        print(f"✅ 响应类型: {type(response)}")
        print(f"✅ 响应属性: {dir(response)}")

        if hasattr(response, 'choices'):
            print(f"✅ choices: {response.choices}")
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                print(f"✅ choice: {choice}")
                if hasattr(choice, 'message'):
                    print(f"✅ message: {choice.message}")
                    if hasattr(choice.message, 'content'):
                        print(f"✅ content: {choice.message.content}")
        else:
            print(f"❌ 响应没有choices字段")
            print(f"   响应内容: {response}")

    except Exception as e:
        print(f"❌ 调用失败: {e}")
        print(f"   错误类型: {type(e)}")
        if hasattr(e, 'body'):
            print(f"   错误体: {e.body}")
        if hasattr(e, 'response'):
            print(f"   响应: {e.response}")

    # 测试2：获取模型列表
    print("\n" + "-" * 80)
    print("\n📝 测试2: 获取模型列表")
    try:
        models = client.models.list()
        print(f"✅ 可用模型:")
        for m in models.data[:10]:
            print(f"   - {m.id}")
    except Exception as e:
        print(f"❌ 获取模型列表失败: {e}")

    # 测试3：使用不同的base_url
    print("\n" + "-" * 80)
    print("\n📝 测试3: 测试不同的base_url")

    urls = [
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "https://dashscope.aliyuncs.com/api/v1",
        "https://dashscope.aliyuncs.com",
    ]

    for url in urls:
        try:
            client2 = openai.OpenAI(
                api_key=api_key,
                base_url=url,
                timeout=10
            )
            response = client2.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10
            )
            print(f"✅ {url} 可用")
            break
        except Exception as e:
            print(f"❌ {url} 失败: {str(e)[:50]}")


def test_with_config():
    """从配置文件读取并测试"""

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src.utils.config import load_config

    config = load_config()
    llm_config = config.get("llm_fallback", {})

    api_key = llm_config.get("api_key")
    model = llm_config.get("model", "qwen-turbo")
    base_url = llm_config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    if not api_key or api_key == "your-api-key-here":
        print("❌ 请先在config.yaml中配置有效的API Key")
        return

    print("=" * 80)
    print("从配置文件测试百炼API")
    print("=" * 80)
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    print("-" * 80)

    client = openai.OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=30
    )

    # 简单测试
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "请回复OK"}
            ],
            max_tokens=10
        )

        print(f"✅ 调用成功!")
        print(f"   响应: {response.choices[0].message.content}")
        print(f"   完整响应: {response}")

    except Exception as e:
        print(f"❌ 调用失败: {e}")
        print(f"   错误类型: {type(e)}")

        # 尝试打印更多错误信息
        if hasattr(e, 'body'):
            print(f"   错误体: {e.body}")
        if hasattr(e, 'response'):
            print(f"   响应状态码: {e.response.status_code if hasattr(e.response, 'status_code') else '未知'}")
            if hasattr(e.response, 'text'):
                print(f"   响应文本: {e.response.text[:200]}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--config":
        test_with_config()
    else:
        test_api_direct()