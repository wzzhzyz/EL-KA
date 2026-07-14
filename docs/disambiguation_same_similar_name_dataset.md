# 同名 / 相似名实体消歧专项验证集

## 1. 用途

`data/eval/disambiguation_same_similar_name_test.json` 是独立于既有 `disambiguation_test.json` 的专项评测集，用于验证候选实体已给定时，系统能否结合上下文区分名称相近、简称相近或同一行业内易混淆的实体，并识别高相似但知识库中不存在的实体（NIL）。

本数据集不修改既有消歧基准，也不作为知识库实体的来源。

## 2. 数据来源与边界

- 运行知识库：`data/kb/energy_entities.json`。
- 正例的 `gold_entity` 与全部 `candidate_entities` 均引用该知识库中的真实 `entity_id`。
- 上下文依据实体的名称、别名、行业、关键词和摘要信息构造；候选负例来自名称或别名相似的真实知识库实体。
- NIL 样本不虚构知识库实体：其 `gold_entity` 为 `null`，但会提供知识库中名称相近的候选，用于检验误链接风险。

当前运行知识库未发现可用于大规模构造的真实共享别名冲突，因此本版没有伪造“严格同名异指”样本；重点覆盖真实可追溯的相似名、简称 / 缩写竞争和高相似 NIL。

## 3. 根节点字段

| 字段 | 说明 |
| --- | --- |
| `dataset_name` | 数据集标识：`same_similar_name_disambiguation_test`。 |
| `version` | 数据版本。 |
| `purpose` | 专项评测目的。 |
| `nil_threshold` | NIL 判定参考阈值。 |
| `bge_llm_trigger_threshold` | BGE / LLM 兜底触发参考阈值。 |
| `kb_reference` | 构造所依据的运行知识库。 |
| `total_cases` | 样本总数，必须等于 `samples` 长度。 |
| `statistics` | 依据实际样本重新计算的统计信息。 |

## 4. 样本字段

| 字段 | 说明 |
| --- | --- |
| `id` | 唯一样本标识，格式为 `DISAMB_SIM_000001`。 |
| `text` | 具有消歧线索的上下文文本。 |
| `mention` | 待消歧指称。 |
| `gold_entity` | 正例对应的知识库实体 ID；NIL 时为 `null`。 |
| `candidate_entities` | 候选实体 ID 列表，至少含两个真实知识库实体。 |
| `confidence_level` | `easy`、`medium` 或 `hard`。 |
| `kb_status` | `in_kb` 或 `nil`。 |
| `expected_bge_score_range` | 与难度对应的预期 BGE 分数范围，使用 `[0, 1]` 标度。 |
| `expected_nil` | 是否应返回 NIL。 |
| `nil_reason` | 仅 NIL 样本必填；当前值为 `entity_not_in_kb`。 |
| `reason` | 正确候选与其他候选的区分依据。 |
| `scenario` | 消歧场景类别。 |

## 5. 构造规则

1. 对每个知识库实体，基于其实体名称、可用简称 / 别名、行业、关键词和摘要生成不同线索强度的正例。
2. 候选集合始终保留正确实体，并加入按名称或别名相似度选出的真实实体作为干扰候选。
3. 简称或缩写存在时标记为“简称 / 缩写竞争”；否则标记为“相似名异指-上下文消歧”。
4. 高相似 NIL 在真实实体名称基础上追加未收录的组织后缀；候选为相近的真实实体，不把该虚构指称写入知识库。
5. 严格同名异指只在运行知识库存在可验证的共享别名时构造。本版本检测到的共享别名冲突数为 0，因此不以人为制造冲突补足数量。

## 6. 当前统计

| 项目 | 数值 |
| --- | ---: |
| 总样本 | 500 |
| 知识库正例 | 474 |
| 高相似 NIL | 26 |
| 平均候选数 | 3.95 |
| `easy` / `medium` / `hard` | 158 / 158 / 184 |
| 严格共享别名冲突 | 0 |

| 场景 | 数量 |
| --- | ---: |
| 相似名异指-上下文消歧 | 316 |
| 简称 / 缩写竞争 | 158 |
| 高相似 NIL | 26 |

场景分布、候选数量和 NIL 比例以文件根节点 `statistics` 为准；每次重新构造数据都应重新生成该字段。

## 7. 使用方式

在仓库根目录运行：

```powershell
python scripts/check_disambiguation_same_similar_name.py
```

检查脚本校验 JSON、样本数、实体 ID、候选合法性、NIL 标注、正例候选包含关系、`mention + text` 重复及场景统计一致性。通过后会输出样本规模、场景 / 难度分布、NIL 数量和平均候选数。
