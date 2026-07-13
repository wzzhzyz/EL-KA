# 实体链接与共指测试数据质量报告

## 1. 总体结论

良好：结构与偏移检查通过，正式集合共指集已具备 125 条 / 125 个 case 的验收数据，并新增 25 条独立 Blind Holdout；当前结果仍仅代表受控规则范围，PERSON、跨句隐式集合和复杂篇章语义仍是明确边界，且不得将规则夹具或受控集的高分外推为整体能力。

## 2. 审计范围与统计口径

data/eval/*.json + data/batch_ground_truth.json；主知识库为 data/kb/energy_entities.json。历史运行输出、索引文件和 trace.db 不作为 gold 测试集。

- `has_gold=false` 不等于文件无价值；本报告以 `gold_status` 区分完整 gold、任务 gold、NER gold、模板和非评测数据。
- 样本、mention、NIL 均按各文件原始任务契约累计，跨任务汇总不代表去重后的统一基准。

## 3. 核心统计

- 扫描 JSON 数据文件：15；Schema 已识别：14。
- 样本 / entry：2137；输入 mention 或 batch gold mention：3761。
- 显式 NIL 标注单元（跨数据集原始计数，不去重）：411。
- 共指总 case：435；历史格式：257；当前字段化：178（单实体对照：6；集合：172；集合成功：116；集合预期 NIL：56）。
- 知识库：158 个实体、490 条 alias。
- ID 非知识库引用：27（专项测试夹具 ID：7；历史测试夹具 ID：20）。

## 4. 文件分类、Schema 与 gold 状态

| 文件 | 分类 | Schema | gold 状态 | 样本 | mention | NIL 标注 |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `data\eval\alias_normalization_test.json` | 别名标准化正式金标集 | mention_linking_gold | complete_gold | 160 | 160 | 20 |
| `data\eval\candidate_retrieval_test.json` | 候选召回金标集 | candidate_retrieval_gold | complete_task_gold | 212 | 212 | 0 |
| `data\eval\coreference_blind_holdout.json` | 集合共指 Blind Holdout（独立泛化，不计入统一总体） | coreference_gold | complete_gold | 25 | 84 | 9 |
| `data\eval\coreference_collective_eval.json` | 集合共指正式金标集 | coreference_collective_acceptance_gold | complete_gold | 125 | 399 | 42 |
| `data\eval\coreference_collective_test.json` | 单元测试夹具 / 专项回归 | coreference_gold | complete_gold | 8 | 25 | 4 |
| `data\eval\coreference_failure_regression.json` | 集合共指失败驱动回归集（非正式验收） | coreference_gold | complete_gold | 20 | 66 | 6 |
| `data\eval\coreference_long_text_test.json` | 单实体共指正式金标集（历史 Schema） | coreference_gold | complete_gold | 154 | 559 | 59 |
| `data\eval\disambiguation_test.json` | 消歧金标集 | disambiguation_gold | complete_task_gold | 154 | 154 | 0 |
| `data\eval\eval_dataset.json` | 综合实体链接金标集 | comprehensive_linking_gold | complete_task_gold | 264 | 264 | 0 |
| `data\eval\llm_disambiguation_comparison_template.json` | 开发模板 / 非正式评测 | generic_samples | no_samples_or_template | 0 | 0 | 0 |
| `data\eval\llm_fallback_ambiguity_test.json` | LLM 消歧专项金标集 | llm_fallback_gold | complete_task_gold | 151 | 151 | 0 |
| `data\eval\llm_fallback_difficult_cases.json` | LLM 疑难专项金标集 | llm_fallback_gold | complete_task_gold | 110 | 110 | 0 |
| `data\eval\mention_linking_test.json` | 实体链接正式金标集 | mention_linking_gold | complete_gold | 505 | 1052 | 185 |
| `data\eval\ner_test_dataset.json` | NER 专项金标集（非实体链接 gold） | ner_gold | complete_ner_gold | 35 | 73 | 0 |
| `data\batch_ground_truth.json` | 批量回归金标 | mention_linking_gold | complete_gold | 214 | 452 | 86 |

### 补充知识库文件

| 文件 | 实体记录 | 样本记录 | 说明 |
| --- | ---: | ---: | --- |
| `data\kb\ambiguity_report.json` | 0 | 0 | 辅助知识库 / 扩充或歧义分析数据，不作为当前主 KB ID 有效性基准 |
| `data\kb\kb_expansion_20260709_step1.json` | 40 | 0 | 辅助知识库 / 扩充或歧义分析数据，不作为当前主 KB ID 有效性基准 |
| `data\kb\kb_expansion_sample.json` | 1 | 0 | 辅助知识库 / 扩充或歧义分析数据，不作为当前主 KB ID 有效性基准 |

## 5. Schema 识别、字符偏移与实体 ID

- JSON 解析错误：0；字段类型 / `confidence` 错误：0。
- 字符偏移：共统计 3761 个输入或 gold mention，其中 1859 个具备 `text`、`mention`、`char_start`、`char_end`；正确 1859，错误 0、越界 0。其余样本缺少偏移字段、仅含候选/gold，或采用历史位置表达。
- 集合共指契约错误：0。
- 非知识库 ID：27；测试夹具 ID 与历史测试夹具 ID 已按用途分类，不直接判为 gold 错误。

## 6. 重复、跨任务复用与泄漏风险

- `exact_duplicate_groups`：135；`exact_duplicate_instances_total`：316；`exact_duplicate_excess_instances`：181（每组保留 1 条后的多余实例）。
- `same_task_duplicate_groups`：33；`cross_task_reuse_groups`：102；`cross_file_same_text_groups`：217。不同任务的复用不直接等同于泄漏。
- `conflicting_duplicate_groups`：0；`cross_task_field_difference_groups`：0。
- 近重复候选：总计 79，展示 79，截断=False。方法：文本去空白与标点后精确比较；冲突仅比较同一规范化文本和同一规范化 mention 的不同 gold entity；近重复使用 SequenceMatcher 比率 >= 0.90 与长度差过滤。近重复仅供人工审查。 模板实体替换、中文短文本和相似实体可能误报，不能自动视为错误。
- 集合专项的 100% 是规则夹具回归结果，样本量仅 8 个 case 且与规则设计高度贴合，结论为“基本可信但覆盖有限”，不得外推为通用集合共指能力。
- 未发现训练集目录；仓库中的 `tests/tests/output` 与 `reports` 为运行输出，不作为 gold 测试集计入。

## 7. 功能覆盖矩阵

- **实体链接：标准名、别名、歧义、候选、NIL**：已覆盖（由 mention_linking、alias、candidate、disambiguation 与 LLM 难例集分担）
- **实体链接：轻微噪声 / 中英文数字**：部分覆盖；需要独立统计或增加对抗样本
- **实体链接：嵌套或重叠 mention**：尚未形成明确专项 gold
- **单实体共指：同句、跨句、类型不兼容、无前件**：已覆盖（coreference_long_text_test.json）
- **单实体共指：链式、多同类型候选、远距离**：部分覆盖；建议按场景建立显式分组统计
- **集合共指：两个 ORG、三实体 ORG、两个 PERSON**：ORG 双、三、四实体已由正式 125 条 / 125 case 验收集覆盖；运行知识库缺少可用 PERSON 实体，PERSON 正例未纳入端到端验收。
- **集合共指：和、与、顿号**：已覆盖（正式验收集与规则夹具）。
- **集合共指：及、以及**：已覆盖（正式验收集）。
- **集合共指：她们、它们、双方、二者、两家央企**：已覆盖它们、双方、二者、两家央企；他们用于类型不兼容 NIL 边界。她们与产品级“这些平台”尚无正式正例。
- **集合共指：混合类型、未链接、跨句、重复 ID、单数代词**：已覆盖为正式集的集合/普通 NIL 边界。
- **集合共指：非实体插入、非相邻候选、多协调组、复杂省略**：非实体插入和多协调组已覆盖；远距离隐式前件与复杂省略仍未覆盖。
- **检测依据**：集合数据：正式集 125 条 / 125 case（challenge_dev 25 条）、规则夹具 8 条；文本中含：和, 与, 、, 及, 以及, 同, 跟, 连同, 会同；集合代词观测：三方, 上述单位, 两家央企, 两者, 二者, 他们, 双方, 各方, 她们, 它们, 该二者, 这些机构。

## 8. 标签冲突人工复核

- 未发现同任务、同输入、不同 gold 的确认冲突。

## 9. 类型与 NIL 分布

- mention 原始类型分布见 JSON `aggregate.entity_type_mentions`；其中 `ORG`、`PERSON`、`GPE`、`LOC` 与知识库细粒度类型分层统计，未强行合并。
- 知识库细粒度实体类型分布见 JSON `knowledge_base.entity_types`；正式 gold 的 NIL 以各数据集原始契约累计为 411。

## 10. 问题分级与建议

### P0
- 未发现。

### P1
- 未发现。

### P2
- 正式集合共指集已扩充到 125 条 / 125 个 case（challenge_dev 25 条）；其结果仅代表当前规则与运行知识库组合，不能外推为通用篇章共指能力。
- 正式运行知识库缺少可用 PERSON 实体，PERSON 集合正例未纳入端到端 KB 验收；她们与产品级“这些平台”也尚无正式正例。
- 跨句集合、远距离隐式前件与复杂省略当前以 NIL 边界或未覆盖项处理。
- 历史长文本共指集未采用 entity_ids 集合 gold，无法单独衡量集合共指能力。
- 多份专项集可能包含模板化实体替换；近重复检测结果应作为扩充时的去重基线。
- 正式长文本共指集中存在 20 个不在当前运行知识库的历史测试夹具 ID；它们不构成结构错误，但不能直接用于端到端知识库 ID 一致性验收。

### P3
- 不同历史数据集的 gold 字段存在 schema 差异；评测时需按数据契约区分历史兼容格式与集合扩展格式。

## 11. 检查覆盖与局限

- 15 个 JSON 文件均完成 JSON 解析；只有 Schema 已识别的文件执行字段级统计。
- 只有具备偏移字段的数据能执行字符偏移检查；`has_gold=false` 不等于数据无价值。
- 近重复结果仅是人工审查候选；未发现训练目录也不能证明完全不存在数据泄漏。
- Blind Holdout 已建立独立人工复核清单，但当前为单人复核限制，不能替代第二位标注者审查。

## 12. 阶段验收与最终测试集建议

- **阶段性验收**：有条件适合。实体链接、NIL、候选、消歧、长文本单实体共指与集合共指均有独立数据；Holdout 结果应与 Challenge Dev 分开展示。
- **最终测试集**：已新增独立 Holdout；后续应优先补充 PERSON、跨句主体连续性、真实长文本和复杂篇章语义，而非重复受控模板。

## 13. 复现命令

```powershell
python scripts\check_dataset_quality.py
python -m py_compile scripts\check_dataset_quality.py
git diff --check
git status --short
```

## 14. 本轮文件变更

本报告由质量审计脚本生成；实际工作区变更范围应以 `git status --short` 为准。
