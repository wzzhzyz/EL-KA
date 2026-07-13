# 中文共指模块调研与标准调用案例

> 日期：2026-07-02
> 用途：7.3阶段一验收材料及下一阶段共指模块接入依据

## 1. 项目约束

本项目的共指目标不是开放域全量共指，而是在实体已被识别并部分链接后，将代词或指代短语回链到知识库标准实体。任务书建议共指回链准确率达到80%以上，并要求结果可追溯、可回放。

## 2. 方案结论

采用“规则优先 + 可插拔重排”的结构：

1. 规则层处理高置信场景，包括`其`、`它`、`该公司`、`该集团`、`这家企业`等常见回指。
2. 候选先行词只从已经完成实体链接的激活实体中产生。
3. 实体类型、句距和最近出现位置作为硬约束或主要排序特征。
4. 满足显式协调、同类型且前件均已链接条件的多实体集合指代返回多个实体 ID；无先行词、低置信或不满足条件的集合场景返回NIL，不强行绑定。
5. 规则无法稳定决定时，允许后续接入模型或LLM重排，但默认关闭。

不建议把Coreferee直接作为中文默认实现；FastCoref可以保留为可选实验后端，但必须具备规则降级路径。仓库现有`Coreference Resolution/chinese_coref.py`已经实现规则基线所需的先行词、规则、置信度、evidence和NIL输出。

## 3. 标准输入契约

```json
{
  "trace_id": "trace_example_001",
  "mentions": [
    {
      "text": "国家电网",
      "entity_type": "ORG",
      "sentence_index": 0,
      "mention_role": "name",
      "linked_entity_id": "ENT_ENERGY_0001",
      "aliases": ["国网"]
    },
    {
      "text": "该公司",
      "entity_type": "ORG",
      "sentence_index": 1,
      "mention_role": "anaphor",
      "linked_entity_id": null,
      "aliases": []
    }
  ]
}
```

### 3.1 现有规则基线调用

在`Coreference Resolution`目录运行，调用方式与现有测试保持一致：

```python
from chinese_coref import ChineseCoreferenceResolver, Mention

mentions = [
    Mention(
        text="国家电网",
        entity_type="ORG",
        sentence_index=0,
        mention_role="name",
        linked_entity_id="ENT_ENERGY_0001",
        aliases=("国网",),
    ),
    Mention(
        text="该公司",
        entity_type="ORG",
        sentence_index=1,
        mention_role="anaphor",
    ),
]

results = ChineseCoreferenceResolver(nil_threshold=0.55).resolve(mentions)
resolved = results[1]
assert resolved.antecedent_entity_id == "ENT_ENERGY_0001"
assert resolved.is_nil is False
```

## 4. 标准输出契约

```json
{
  "trace_id": "trace_example_001",
  "mention": "该公司",
  "antecedent": "国家电网",
  "entity_id": "ENT_ENERGY_0001",
  "entity_name": "国家电网有限公司",
  "confidence": 0.79,
  "rule": "recency_and_type",
  "evidence": "ORG类型一致，且国家电网是最近的已链接先行实体",
  "is_nil": false
}
```

必要字段为`entity_id`、`entity_name`、`confidence`、`evidence`和`is_nil`；共指结果还应保留`antecedent`与命中规则，所有记录沿用调用链`trace_id`。

## 5. 标准调用案例

### 5.1 组织名词性回指

输入文本：`国家电网发布年度报告。该公司将继续投资特高压工程。`

预期：`该公司 -> 国家电网有限公司（ENT_ENERGY_0001）`。

依据：最近ORG类型先行词，语义角色与“公司”一致。

### 5.2 单字代词回指

输入文本：`南方电网公布投资计划，其重点包括数字电网建设。`

预期：`其 -> 中国南方电网有限责任公司（ENT_ENERGY_0002）`。

依据：同句最近已链接ORG实体。

### 5.3 人称与组织类型约束

输入文本：`张三参观华为研发中心。他随后参加了技术交流会。`

预期：`他`只能选择PERSON类型先行词；若“张三”没有可用标准实体ID，则返回NIL，不能错误绑定到华为。

### 5.4 链式共指

输入文本：`华为公布研发投入，其投入占比继续提高。未来它还将扩展云计算业务。`

预期：`其`和`它`均回链至`华为技术有限公司（ENT_GEN_0051）`，并保留原始先行词。

### 5.5 集合指代

对于同一句内存在“和、与、及、以及、、”等显式协调连接的、已链接且类型一致的 `ORG` 或 `PERSON` 前件，集合代词可以返回多个去重后的 `entity_ids`。当前集合代词范围包含“他们”“两家央企”“这些机构”等表面词。例如“人民日报社和新华通讯社……他们”可回指两个机构。集合成功采用 `entity_id: null`、非空 `entity_ids`、`is_collective: true`、`is_nil: false` 的结构；混合类型、跨句无显式连接、未链接前件和重复实体 ID 等情况仍保守返回 NIL。不能仅根据 `entity_id` 是否为空判断 NIL，必须读取 `is_nil`。

输入文本：`国家电网和南方电网发布年度报告。两家央企均增加新能源投资。`

预期：`两家央企 -> [ENT_ENERGY_0001, ENT_ENERGY_0002]`，并返回 `entity_id: null`、`is_collective: true`、`is_nil: false`。

依据：`两家央企`已在当前集合代词范围内；“国家电网”和“南方电网”由显式连接词“和”连接，均为已链接的同类型 `ORG` 前件。多个目标通过 `entity_ids` 表达，而非要求单一 `entity_id`。

### 5.6 无先行词

输入文本：`该公司计划扩大海外市场。`

预期：`该公司 -> NIL`。

依据：激活实体栈中没有兼容先行词，不允许根据常识猜测。

## 6. 接入与验收检查项

- 共指开关关闭时，不改变原实体链接结果。
- 共指开关开启时，只处理代词和名词性指代，不重复替代NER或候选生成。
- 类型不兼容的先行词必须排除。
- 集合指代和无先行词场景必须支持NIL。
- 输出必须包含`trace_id`、先行词、规则、置信度和证据。
- 在独立金标集上统计代词/指代回链准确率，目标不低于80%。
