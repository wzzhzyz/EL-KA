# 阶段一简易评测记录

> 日期：2026-07-02
> 数据版本：`phase1_e2e_ground_truth` 1.0
> 代码基线：`fc78115` 及其前置提交
> 负责人视角：欧小红（测试数据与评测记录）

## 1. 评测范围

- 输入文本：36条。
- 人工标注mention：42个。
- NIL标注mention：5个。
- 无实体负样本：1条。
- 执行脚本：`scripts/e2e_from_ground_truth.py`。
- 执行命令：`python scripts/e2e_from_ground_truth.py --trace-prefix d6_eval --verbose`。

## 2. 数据预检

| 检查项 | 结果 |
|---|---:|
| 文本数量与Ground Truth数量一致 | 通过（36/36） |
| `text_idx`连续覆盖 | 通过（0-35） |
| 标注mention存在于对应原文 | 通过 |
| 非NIL实体ID存在于知识库 | 通过 |

## 3. 本次运行结果

| 指标 | 结果 |
|---|---:|
| 实际参与评测样本 | 36 |
| 标注mention总数 | 42 |
| 正确链接数 | 0 |
| 当前链接准确率 | 0.0000 |
| NIL标注数 | 5 |
| NIL正确数 | 0 |
| 当前NIL命中率 | 0.0000 |
| 缺失预测 | 5 |

## 4. 结果解释

本次运行未加载真实BGE/EntityAlignmentV0后端。初始化阶段因运行环境缺少`yaml`模块而回退到`local`后端；回退链路能够完成NER、候选生成和SQLite留痕，但不执行最终消歧，候选非空时也不会输出最终`entity_id`。因此，本次0准确率反映的是当前环境与主链路集成状态，不代表知识库或人工标注质量为0。

## 5. 已确认问题

1. `EntityAlignmentV0`初始化受缺失依赖阻断，日志为`No module named 'yaml'`。
2. 当前`local`后端仍是候选生成与存储链路，未形成最终实体链接结果。
3. 5个NIL mention未被NER输出，评测脚本将其计为`missing_predictions`，需要在后续评测中区分“NER漏检”和“NIL判定错误”。
4. 评测脚本当前输出字段名为`nil_precision`，实际计算公式为`nil_correct / nil_total`，语义更接近NIL召回率或命中率。

## 6. 阶段一验收判断

- 数据集完整性：通过。
- 标注一致性：通过。
- 命令行链路可执行：通过。
- 真实BGE消歧链路：未通过，受环境依赖与接入状态阻断。
- 实体链接效果指标：暂不具备有效验收条件。

本记录只归档客观运行结果。待真实后端可用后，应使用同一版本数据集复跑并保留前后指标对比。

## 7. 任务书输入口径修订（2026-07-06）

根据《智能体研究课题任务书（终稿）》“文本 + 已识别实体指称 + 知识库”的要求，新增`data/eval/mention_linking_test.json`，将`mentions`输入与`expected_entities`金标结果分离。评测脚本默认改为调用`EntityLinkingPipeline.run_with_mentions()`，原始文本NER模式通过`--input-mode raw`保留为辅助测试。

mention-given模式复测结果：36条样本、42个给定mention全部进入实体链接阶段，`missing_predictions`由原始文本模式的5降为0。由于当前环境仍回退到不执行最终消歧的`local`后端，37个非NIL mention均被判为NIL，因此链接准确率仍为0，NIL F1为0.2128。该结果说明输入边界已按任务书对齐，但真实BGE后端阻断尚未解除。
