# Postman接口联调说明

## 导入文件

1. 导入`entity_linking_api.postman_collection.json`；
2. 导入`entity_linking_local.postman_environment.json`；
3. 选择环境“课题10-本地环境”；
4. 确认`base_url`为`http://127.0.0.1:8000`。

环境文件不保存模型密钥或外部LLM密钥。

## 启动服务

在`EntityAlignmentV0`目录运行：

```powershell
python run_api.py
```

服务启动后可访问：

- API：`http://127.0.0.1:8000`；
- Swagger：`http://127.0.0.1:8000/docs`。

## 建议运行顺序

1. 运行“健康检查”；
2. 运行“知识库摘要”；
3. 运行“基准-默认阈值-功能关闭”；
4. 依次运行低阈值、高阈值、共指开关、LLM开关和NIL请求；
5. 运行“查询上一请求Trace”；
6. 运行异常请求并确认HTTP 422。

成功的链接请求会自动把响应中的`trace_id`写入集合变量，Trace查询会复用该变量。

## 对比记录

参数组合定义在`api_parameter_matrix.json`。联调时至少记录：

- HTTP状态；
- trace_id；
- entity_id与standard_entity；
- confidence与is_nil；
- evidence；
- stats；
- 功能开启前后的结果差异。

## 当前边界

- Mention-Given请求是任务书规定的主要验收入口；
- Raw-Text请求仅作为NER加实体链接的辅助检查；
- `enable_llm_fallback`请求级开关目前属于待联调项；
- 模型、依赖或配置未准备好时，服务可能在启动阶段失败，不应将其误记为接口断言失败。
