from paddlenlp import Taskflow
import paddle

# 设置使用GPU
paddle.set_device('gpu')

# 加载模型（首次会下载到 ~/.paddlenlp/）
coref = Taskflow("coreference_resolution", model="coref_ernie_3.0")

text = "华为和腾讯都是科技巨头。它们都在深圳有总部。"
result = coref(text)
print(result)