# 查询百炼可用模型
import openai

client = openai.OpenAI(
    api_key="sk-ws-H.RERDMME.mtnS.MEYCIQC52O9l9Bdvlaq-cxsuVO6isL-njt7bRLHTvo9r0jR5RQIhAMenFxknVyXygcQM3u9V_lkT4JuI6W1aDH_DqfQ3ogsH",  # 您的百炼API Key
    base_url="https://ws-nf0fhf5rgskiv5w2.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
)

# 获取可用模型列表
models = client.models.list()
for model in models.data:
    print(f"模型名: {model.id}")