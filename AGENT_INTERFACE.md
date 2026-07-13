**EL-KA 智能体 — 接口说明与演示用例**

目的
- 说明服务端点、输入/输出契约、可追溯的字段和如何用示例请求验证行为。

服务端点（主要）
- `GET /health` — 健康检查，返回当前 `backend`（`local` 或 `entity_alignment`）。
- `POST /v1/link` — 实体链接主入口，输入为 `text + mentions + kb + options`，返回每个 mention 的链接结果、NIL 判定、消歧依据与共指信息。

请求契约（LinkRequest）
- 字段：
  - `text` (string, 必需)：原始文本。
  - `mentions` (list, 可选)：已识别的 mention 列表，元素结构见下（优先使用）。
  - `kb` (string, 可选)：知识库路径或标识（可用于按请求加载不同 KB）。
  - `options` (dict, 可选)：配置项，例如 `enable_coreference`、`nil_threshold`、`allow_ner_fallback` 等。

Mention 元素结构示例：
```json
{
  "mention": "国家电网",
  "type": "ORG",
  "char_start": 0,
  "char_end": 4,
  "confidence": 1.0,
  "metadata": {}
}
```

响应契约（LinkResponse）
- 字段要点：
  - `trace_id`: 请求追踪 ID（可用于回放与审计）。
  - `text`: 原始输入文本。
  - `input_mode`: `provided_mentions` 或 `provided_mentions_required` 等。
  - `results`: 每个 mention 的链接结果列表（见下示例）。
  - `stats`: 统计信息（total_mentions, linked, nil, coreference_resolved）。
  - `backend`: 当前后端（`local` 或 `entity_alignment`）。

单个结果项典型字段（每项均写入 DB 并可回放）
- `mention`, `type`, `char_start`, `char_end`
- `entity_id`：链接到的标准实体唯一 ID（空字符串表示 NIL）
- `standard_name` 或 `standard_entity`：标准实体全称
- `confidence`：置信度分数（消歧器返回）
- `is_nil`：是否判定为 NIL
- `candidates`：候选列表（用于审计与回放）
- `candidate_count`：候选数量
- `evidence`：消歧/判定的文本证据（人可读）
- `link_basis`：结构化追溯信息，例如
  - `reason`：`entity_selected` / `nil_threshold` / `no_candidates` 等
  - `entity_id`, `standard_name`：被选实体
  - `evidence`：更详细说明
  - `source`：`candidate_generation` / `disambiguation` / `rule_coref` 等

演示用例（curl）
```bash
curl -X POST "http://localhost:8000/v1/link" \
  -H "Content-Type: application/json" \
  -d '{
    "kb": "data/kb.json",
    "mentions": [
      {
        "char_end": 4,
        "char_start": 0,
        "confidence": 1,
        "mention": "国家电网",
        "metadata": {},
        "type": "ORG"
      }
    ],
    "options": {"enable_coreference": false},
    "text": "国家电网发布了公告。"
  }'
```

从本地 JSON 文件读取批量请求示例：
```bash
curl -X POST "http://localhost:8000/v1/link_from_file" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "D:/Doc/shixun/2/EL-KA/data/test.json"
  }'
```

其中 `data/test.json` 应包含批量请求结构，例如：
```json
{
  "default_kb": "data/kb.json",
  "items": [
    {
      "text": "国家电网发布了公告。",
      "mentions": [
        {
          "mention": "国家电网",
          "type": "ORG",
          "char_start": 0,
          "char_end": 4,
          "confidence": 1.0,
          "metadata": {}
        }
      ],
      "options": {"enable_coreference": false}
    }
  ]
}
```

示例响应（示意，依据 `entity_linker/service.py` 的 response 模型示例）
```json
{
  "trace_id": "123e4567-e89b-12d3-a456-426614174000",
  "text": "国家电网发布了公告。",
  "input_mode": "provided_mentions",
  "results": [
    {
      "mention": "国家电网",
      "type": "ORG",
      "char_start": 0,
      "char_end": 4,
      "entity_id": "ENT_ENERGY_0001",
      "standard_entity": "国家电网有限公司",
      "confidence": 0.95,
      "is_nil": false,
      "evidence": "fallback规则消歧选择最高分候选",
      "link_basis": {
        "reason": "entity_selected",
        "entity_id": "ENT_ENERGY_0001",
        "standard_name": "国家电网有限公司",
        "evidence": "候选分数最高",
        "source": "disambiguation"
      }
    }
  ],
  "stats": {
    "total_mentions": 1,
    "linked": 1,
    "nil": 0,
    "coreference_resolved": 0
  },
  "backend": "local",
  "message": ""
}
```

可追溯性（审计与回放）
- 所有中间阶段（NER、候选生成、消歧、NIL 判定、共指）都写入 SQLite（`data/trace.db`），DB 表包含：`pipeline_run`, `pipeline_step`, `mention`, `candidate`, `link_result` 等。
- 每条 `results` 的 `link_basis` 与 `candidates` 字段即为可读的回溯证据；`trace_id` 可用于在 DB 中回放完整链路。

实现说明与注意点
- 若 `backend` 为 `local`：结果由别名匹配 + 规则消歧产生（短路优先），在受控数据集上精度高但泛化有限。日志中 `link_basis.source` 为 `candidate_generation` 或 `disambiguation`。
- 若 `backend` 为 `entity_alignment`：使用 BGE 向量召回 + 模型消歧，`link_basis` 会包含来自模型/重排序器的分数与证据。
- NIL 判定通过消歧器返回的 `score` 与 `nil_threshold` 比较完成；当 `is_nil` 为 true 时，`entity_id` 为空且 `link_basis.reason` 可能为 `nil_threshold` 或 `no_candidates`。

快速检查项（验证接口契约）
1. 启动服务：
```powershell
D:/Programfiles/anaconda/envs/EL-KA/python.exe -m uvicorn entity_linker.service:app --host 0.0.0.0 --port 8000
```
2. 健康检查查看后端：
```powershell
curl http://localhost:8000/health
```
3. 运行上面的 `POST /v1/link` 示例并检查 `backend`、`results[*].link_basis`、`stats` 字段是否存在。

演示注意：当前默认服务已在 `entity_linker/service.py` 中配置为禁用 LLM 兜底（`llm_fallback.enabled=false`），以便演示时仅依赖本地 KB；修改后需要重启服务生效。

结论
- 当前服务接口已满足“文本 + mentions + KB -> 标准实体 ID + 标准名 + NIL + 消歧依据 + 共指”的需求。为确保“模型路径下”的输出可信，请在验收时明确使用 `--bge-model-path` 或确保 `backend` 返回 `entity_alignment` 并保留 `reports/mini_eval_bge.json` 作为模型证据。

五类示例（覆盖常见演示场景）
1) 精确别名匹配（alias_exact, local 后端常见）
请求：
```json
{
  "kb": "data/kb.json",
  "mentions": [{"mention":"国家电网","type":"ORG","char_start":0,"char_end":4,"confidence":1}],
  "options": {},
  "text": "国家电网发布了公告。"
}
```
示意响应（local）：
```json
{
  "trace_id": "t-1",
  "text": "国家电网发布了公告。",
  "input_mode": "provided_mentions",
  "results": [
    {
      "mention":"国家电网",
      "type":"ORG",
      "char_start":0,
      "char_end":4,
      "entity_id":"ENT_ENERGY_0001",
      "standard_entity":"国家电网有限公司",
      "confidence":0.95,
      "is_nil":false,
      "candidate_count":1,
      "candidates":[{"entity_id":"ENT_ENERGY_0001","standard_name":"国家电网有限公司","score":0.95}],
      "evidence":"fallback规则消歧选择最高分候选",
      "link_basis":{"reason":"entity_selected","entity_id":"ENT_ENERGY_0001","standard_name":"国家电网有限公司","evidence":"alias_exact 匹配","source":"candidate_generation"}
    }
  ],
  "stats":{"total_mentions":1,"linked":1,"nil":0,"coreference_resolved":0},
  "backend":"local",
  "message":""
}
```

2) 模糊匹配（alias_fuzzy）
请求：
```json
{
  "kb":"data/kb.json",
  "mentions":[{"mention":"国网","type":"ORG","char_start":0,"char_end":2,"confidence":0.9}],
  "options":{},
  "text":"国网发布新规。"
}
```
示意响应（local，选中模糊候选）：
```json
{
  "trace_id":"t-2",
  "results":[
    {
      "mention":"国网",
      "entity_id":"ENT_ENERGY_0001",
      "standard_entity":"国家电网有限公司",
      "confidence":0.85,
      "is_nil":false,
      "candidate_count":2,
      "candidates":[{"entity_id":"ENT_ENERGY_0001","standard_name":"国家电网有限公司","score":0.85}],
      "link_basis":{"reason":"entity_selected","evidence":"alias_fuzzy 匹配","source":"candidate_generation"}
    }
  ],
  "backend":"local"
}
```

3) NIL 判定（无候选或低分被拒识）
请求：
```json
{
  "kb":"data/kb.json",
  "mentions":[{"mention":"不存在的实体X","type":"ORG","char_start":0,"char_end":7,"confidence":1}],
  "options":{"nil_threshold":0.9},
  "text":"不存在的实体X 发布声明。"
}
```
示意响应：
```json
{
  "trace_id":"t-3",
  "results":[
    {
      "mention":"不存在的实体X",
      "entity_id":"",
      "standard_entity":"",
      "confidence":0.0,
      "is_nil":true,
      "evidence":"无候选实体 或 低于 NIL 阈值",
      "link_basis":{"reason":"no_candidates","evidence":"无候选实体","source":"candidate_generation"}
    }
  ],
  "backend":"local"
}
```

4) 规则共指消解示例（enable_coreference=true）
请求：
```json
{
  "kb":"data/kb.json",
  "mentions":[
    {"mention":"李强","type":"PERSON","char_start":0,"char_end":2,"confidence":1},
    {"mention":"他","type":"PRON","char_start":10,"char_end":11,"confidence":1}
  ],
  "options":{"enable_coreference":true},
  "text":"李强今天签署合同，他表示将推进项目。"
}
```
示意响应（共指后）：
```json
{
  "trace_id":"t-4",
  "results":[
    {"mention":"李强","entity_id":"ENT_PERSON_0005","standard_entity":"李强","is_nil":false},
    {"mention":"他","entity_id":"ENT_PERSON_0005","standard_entity":"李强","is_nil":false,"is_coreference":true,"link_basis":{"reason":"coreference_resolved","source":"rule_coref","evidence":"代词指向前文实体 李强"}}
  ],
  "stats":{"coreference_resolved":1},
  "backend":"local"
}
```

5) BGE/EntityAlignment 示例（展示模型证据与 backend=entity_alignment）
请求：
```json
{
  "kb":"EntityAlignmentV0/models_cache/bge-small-zh",
  "mentions":[{"mention":"国家电网","type":"ORG","char_start":0,"char_end":4,"confidence":1}],
  "options":{},
  "text":"国家电网发布了公告。"
}
```
示意响应（entity_alignment）：
```json
{
  "trace_id":"t-5",
  "results":[
    {
      "mention":"国家电网",
      "entity_id":"ENT_ENERGY_0001",
      "standard_entity":"国家电网有限公司",
      "confidence":0.92,
      "is_nil":false,
      "candidates":[
        {"entity_id":"ENT_ENERGY_0001","standard_name":"国家电网有限公司","score":0.90},
        {"entity_id":"ENT_ENERGY_0002","standard_name":"国家电网股份有限公司","score":0.60}
      ],
      "evidence":"BGE 向量检索 top-k + reranker 得分",
      "link_basis":{"reason":"entity_selected","entity_id":"ENT_ENERGY_0001","standard_name":"国家电网有限公司","evidence":"bge_score=0.90; reranker_score=0.92","source":"disambiguation"}
    }
  ],
  "backend":"entity_alignment"
}
```



{
  "text": "人民日报社和新华通讯社和正在飞速发展，他们是我们的未来",
  "mentions": [
    {"mention":"人民日报社","type":"ORG","char_start":0,"char_end":5,"confidence":1},
    {"mention":"新华通讯社","type":"ORG","char_start":6,"char_end":11,"confidence":1},
    {"mention":"他们","type":"PRON","char_start":18,"char_end":20,"confidence":1}
  ],
  "options": {"enable_coreference": true}
}

{
  "text": "人民日报社、新华通讯社、上海报业集团澎湃新闻正在飞速发展，他们是我们的未来。",
  "mentions": [
    {"mention":"人民日报社","type":"ORG","char_start":0,"char_end":5,"confidence":1},
    {"mention":"新华通讯社","type":"ORG","char_start":6,"char_end":11,"confidence":1},
{"mention":"上海报业集团澎湃新闻","type":"ORG","char_start":12,"char_end":23,"confidence":1},
    {"mention":"他们","type":"PRON","char_start":24,"char_end":26,"confidence":1}
  ],
  "options": {"enable_coreference": true}
}



{
  "default_kb": "",
  "items": [
    {
      "text": "国家电网发布了公告。",
      "mentions": [
        {
          "mention": "国家电网",
          "type": "ORG",
          "char_start": 0,
          "char_end": 4,
          "confidence": 1.0,
          "metadata": {}
        }
      ],
      "kb": "",
      "options": {
        "enable_coreference": false
      }
    },
    {
      "text": "上海石化集团已经发布环保报告。",
      "mentions": [
        {
          "mention": "上海石化集团",
          "type": "ORG",
          "char_start": 0,
          "char_end": 6,
          "confidence": 1.0,
          "metadata": {}
        }
      ],
      "kb": "",
      "options": {
        "enable_coreference": false
      }
    }
  ]
}