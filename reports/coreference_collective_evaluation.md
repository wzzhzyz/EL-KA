# 集合共指正式验收详细回归报告

## 1. 评测对象与复现命令

- 数据集：`data/eval/coreference_collective_eval.json`（125 条文本、125 个 case）
- 知识库：`data/kb/energy_entities.json`
- 评测器：`scripts/evaluate_coreference_rules.py`
- 实际解析器：`entity_linker.coreference.RuleBasedCoreferenceResolver`

```powershell
python scripts/evaluate_coreference_rules.py `
  --dataset data/eval/coreference_collective_eval.json `
  --output reports/coreference_collective_evaluation.json
```

本报告只呈现正式集合集的详细规则回归。第五项验收的正式总体口径由统一脚本合并历史单实体集 257 个 case 与本集合集 125 个 case，并显式排除 8 条单元夹具；请以 `reports/coreference_acceptance_result.md` 为准。

## 2. 当前结果

|指标|结果|分子 / 分母|
|-|-:|-:|
|集合集 Overall Accuracy|86.40%|108 / 125|
|普通单数 NIL|100.00%|5 / 5|
|Collective Coreference Accuracy|85.83%|103 / 120|
|Collective Exact Match（正例）|84.34%|70 / 83|
|Collective NIL Accuracy|89.19%|33 / 37|
|Wrong cases|17|17 / 125|

集合正例按 `entity_ids` 的集合精确匹配：实体顺序不影响结果，但必须无重复、与 gold 集合完全一致，并同时满足 `is_collective=true`、`is_nil=false`。集合 NIL 必须同时满足 `entity_ids=[]`、`entity_id=null`、`is_collective=true`、`is_nil=true`。因此不能仅凭 `entity_id` 为空将集合成功误判为 NIL。

## 3. 数据范围与失败解释

正式集包括 83 条集合正例、37 条集合 NIL、5 条普通单数 NIL，其中 `acceptance_main` 100 条、`blind_challenge` 25 条。盲测覆盖跨句或远距离前件、主语切换、未支持连接词（如 `同`、`跟`、`连同`、`会同`）及未支持指代表达（如 `三方`、`各方`、`两者`、`该二者`、`上述单位`）。

当前 17 个错误是保留的边界压力样本，不通过删除样本或改写 gold 掩盖：8 个为 `false_nil`，4 个为 `false_positive`，5 个为 `collective_flag_error`。盲测正确 8 / 25，说明现有本地规则在受控主验收集上稳定，但对通用篇章集合回指仍存在明显边界。

## 4. 复核与限制

机器可读的逐 case 结果、分组统计和错误类型见 `reports/coreference_collective_evaluation.json`；人工标注复核见 `reports/coreference_collective_annotation_review.md`。本报告不覆盖 NER、候选生成、BGE、LLM 或通用篇章推理；运行知识库当前没有可用 `PERSON` 实体，故不对 PERSON 集合正例作端到端结论。
