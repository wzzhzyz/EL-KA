# 已识别实体指称输入规范

## 1. 适用范围

本规范对齐《智能体研究课题任务书（终稿）》中课题10的期望输入：

```text
文本 + 已识别的实体指称（mention）+ 知识库/词库
```

实体识别不是本课题的主要验收对象。正式的链接准确率、消歧准确率和NIL F1应使用已给定mention的输入计算；原始文本端到端模式仅作为辅助测试。

## 2. 标准数据集

标准评测数据位于：

```text
data/eval/mention_linking_test.json
```

数据集根级字段：

- `input_contract`：输入字段约定；
- `knowledge_base`：知识库类型、路径、版本和实体数量；
- `statistics`：样本、mention和NIL数量；
- `samples`：mention级评测样本。

## 3. 单条样本格式

```json
{
  "id": "MENTION_LINK_001",
  "text": "国家电网有限公司发布了公告。",
  "mentions": [
    {
      "mention": "国家电网有限公司",
      "type": "ORG",
      "char_start": 0,
      "char_end": 10,
      "confidence": 1.0
    }
  ],
  "expected_entities": [
    {
      "mention": "国家电网有限公司",
      "entity_id": "ENT_ENERGY_0001"
    }
  ],
  "has_nil": false,
  "scenario": "标准全称"
}
```

`mentions`只包含系统输入，不携带金标实体ID；`expected_entities`只用于评测对照，二者不得混用。

## 4. 调用方式

正式mention级评测：

```powershell
python scripts/e2e_from_ground_truth.py
```

脚本默认读取`mention_linking_test.json`并调用`EntityLinkingPipeline.run_with_mentions()`。

辅助原始文本评测：

```powershell
python scripts/e2e_from_ground_truth.py --input-mode raw
```

该模式会先执行NER，只用于检查完整链路，不作为实体链接专项指标的唯一依据。

## 5. 指标边界

- `linking_accuracy`：只统计非NIL mention到标准实体ID的映射准确率；
- `nil_precision/recall/F1`：只统计知识库无对应实体的NIL判断；
- `missing_predictions`：给定mention未产生结果，属于链接链路缺失，不再归因于NER；
- NER召回率应使用独立NER数据集计算。
