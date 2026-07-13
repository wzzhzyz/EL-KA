# 集合共指正式验收集设计说明

## 1. 建设目的

`data/eval/coreference_collective_eval.json` 是集合共指的正式验收金标集，用于补充 `coreference_collective_test.json` 仅作为规则单元夹具、规模仅 8 条的不足。

该集验证已识别 mention 在当前本地规则和运行知识库中的集合回指：多个已链接前件通过显式协调关系共同指向一个集合代词或集合名词短语。它不测试 NER、候选生成、未知实体发现、BGE、LLM 或通用篇章推理。

## 2. 数据契约

根字段：

```json
{
  "dataset_name": "coreference_collective_eval",
  "version": "1.0",
  "evaluation_scope": "acceptance",
  "requires_runtime_kb": true,
  "samples": []
}
```

每个样本包含 `text`、带半开区间偏移的 `mentions` 与至少一个 `expected_coreferences`。正例前件的 `entity_id` 及 gold `entity_ids` 必须存在于 `data/kb/energy_entities.json`；禁止使用 `TEST_*`、`PER_TEST_*` 或 `SYS_TEST_*` 夹具 ID。

|结果|`entity_id`|`entity_ids`|`is_collective`|`is_nil`|
|-|-|-|-|-|
|单实体成功|单个 ID|`[单个 ID]`|`false`|`false`|
|集合成功|`null`|至少两个去重 ID|`true`|`false`|
|集合未解析|`null`|`[]`|`true`|`true`|
|普通 NIL|`null`|`[]`|`false`|`true`|

集合成功以 `entity_ids` 的集合精确匹配评估，实体顺序不影响正确性。不能仅根据 `entity_id` 是否为空判定 NIL，必须读取 `is_nil`。

## 3. 当前规模与覆盖

当前正式集共 125 条文本，每条包含 1 个待验证指代，共 125 个 case：83 条集合正例、37 条集合 NIL、5 条普通单数 NIL。正例中有 68 条双实体、13 条三实体和 2 条四实体集合，均引用运行知识库中的真实实体。数据逻辑划分为 100 条 `acceptance_main` 与 25 条 `challenge_dev`；后者已参与 P0 规则开发，只用于暴露边界，不是最终泛化盲测。

已覆盖：

- 同句显式 `和`、`与`、`及`、`以及` 与顿号组合，以及 P0 已支持的 `同`、`跟`、`连同`、`会同`；
- 能源、科技、金融、医疗、交通、教育、媒体等领域的双/三/四实体集合；
- `双方`、`二者`、`两家公司`、`两家企业`、`两家机构`、`两家央企`、`两家高校`、`两所高校`、`两所大学`、`多家企业`、`这些企业`、`这些机构`、`上述企业`、`上述机构`、`他们` 与 `它们`，以及盲测中的 `三方`、`各方`、`两者`、`该二者`、`上述单位`；
- 事件成分插入、多协调组最近前件选择、跨句距离和主语切换压力；
- 类型不兼容、未链接前件、重复实体 ID、缺少协调关系、单数代词及看似集合但不应链接的 NIL 边界。

## 4. 非覆盖范围与解释限制

- 运行知识库没有可用 `PERSON` 实体，因此 PERSON 集合正例与“她们”未纳入端到端 KB 验收；
- “他们”既含 `ORG` / `GPE` 类型不兼容的 NIL 边界，也含机构集合回指样本；这不等同于 PERSON 集合成功能力；
- `challenge_dev` 中的跨句隐式集合、远距离篇章前件、复杂省略、嵌套集合和类型范围问题用于暴露边界；失败样本保留，不以改写 gold 追求满分；
- 独立 `coreference_blind_holdout.json` 在 P0 冻结后一次性运行，25 条中 18 条正确（72.00%）。该结果达到基本泛化参考线（60%），但低于复杂集合共指参考线（80%）；不得据此继续调规则。
- 正式集的受控规则回归结果不能外推为通用共指系统能力。

## 5. 质量与评测

质量审计由 `scripts/check_dataset_quality.py` 执行，检查验收范围标记、运行 KB ID、集合 ID 去重、前件索引和字符偏移。逐条人工复核见 `reports/coreference_collective_annotation_review.md`。

第五项验收的统一评测命令：

```powershell
python scripts/evaluate_coreference_acceptance.py `
  --legacy data/eval/coreference_long_text_test.json `
  --collective data/eval/coreference_collective_eval.json `
  --holdout data/eval/coreference_blind_holdout.json `
  --output-json reports/coreference_blind_holdout_result.json `
  --output-md reports/coreference_blind_holdout_result.md
```

该脚本直接调用冻结的 `RuleBasedCoreferenceResolver`，既有统一口径合并历史单实体集 257 个 case 与正式集合集 125 个 case，显式排除 8 条单元夹具和失败驱动回归集。当前统一结果为 375 / 382（98.17%），满足 ≥80% 的第五项验收阈值；集合正例精确匹配为 79 / 83（95.18%），集合 NIL 为 34 / 37（91.89%）。`acceptance_main` 为 100 / 100，`challenge_dev` 为 18 / 25。独立 holdout 为 18 / 25（72.00%），不混入既有统一总体；其正例精确匹配为 11 / 16，NIL 为 7 / 9。统一报告见 `reports/coreference_acceptance_result.md`，holdout 结果见 `reports/coreference_blind_holdout_result.md`。
