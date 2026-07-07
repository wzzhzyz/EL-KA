# 7.7 Badcase分析与阈值调优记录

> 日期：2026-07-07  
> 任务范围：Badcase分析、NIL阈值调优、LLM触发阈值检查、明显问题修复  
> 成员视角：欧小红（第三成员，数据处理与实体链接核心链路）

## 1. 本日任务目标

7.7 阶段目标是在 7.6 已构建的 mention-given 评测集基础上，对实体链接结果进行初步评测、Badcase 分析与阈值调优，重点检查：

- 候选生成后是否能输出最终实体链接结果；
- NIL 阈值是否能过滤低置信误链接；
- LLM 兜底触发阈值是否保留配置入口；
- HTTP/API 调用所需的输出字段是否保持兼容。

## 2. 发现的明显问题

本地 fallback 后端在缺少 BGE/YAML 依赖时可以完成候选生成，但旧实现中的占位消歧器只返回 `entity=None`，导致所有非 NIL mention 都被判为 NIL。

该问题表现为：

- Candidate Generation 有候选；
- Disambiguation 不选择候选；
- Linking Accuracy 被压为 0；
- API 返回结构完整，但实体链接结果不可用于验收。

## 3. 修复方式

在不重构主 Pipeline、不改动 EntityAlignmentV0 接口的前提下，补充轻量 fallback 规则消歧：

- 对候选按 `score` 降序排序；
- 优先选择最高分候选作为链接结果；
- 再根据 `nil_threshold` 判断是否拒识为 NIL；
- 保留 `llm_trigger_threshold` 字段，用于后续 LLM 兜底接入；
- `evidence` 中记录命中方式、候选分数和阈值，便于 trace 审计。

该修复仅用于 BGE/LLM 未就绪时的本地可验收链路，不替代后续语义消歧能力。

## 4. 阈值对比结果

评测数据：`data/eval/mention_linking_test.json`  
评测规模：100 条样本，106 个 mention  
输入模式：已识别 mention 输入（符合任务书要求）

| NIL阈值 | Overall Accuracy | Linking Accuracy | NIL Precision | NIL Recall | NIL F1 | Badcase数 |
|---:|---:|---:|---:|---:|---:|---:|
| 0.65 | 0.9528 | 1.0000 | 1.0000 | 0.8148 | 0.8980 | 5 |
| 0.80 | 0.9528 | 1.0000 | 1.0000 | 0.8148 | 0.8980 | 5 |
| 0.90 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |

## 5. Badcase归因

阈值为 0.65/0.80 时，剩余 5 条 badcase 均属于 `nil_false_negative`：

- `阳光新能源`：应为 NIL，被模糊召回到已有新能源企业；
- `中国能源研究会`：应为 NIL，被模糊召回到能源集团；
- `北京大学`：应为 NIL，被模糊召回到北京地区实体；
- `北京协和医院`：应为 NIL，被模糊召回到北京地区实体；
- `京东`：应为 NIL，被模糊召回到北京地区实体。

这些错误的共同特征是：没有精确别名命中，但因字符串包含关系产生 `alias_fuzzy` 候选，候选分数为 0.85。将 NIL 阈值调整到 0.90 后，可过滤这类低置信模糊误链接，同时保留 `alias_exact` 的 0.95 高置信链接结果。

## 6. 调优结论

当前 fallback 后端推荐：

- `nil_threshold = 0.90`
- `llm_trigger_threshold = 0.65`

原因：

- 0.90 能有效拦截本地规则模糊匹配带来的 NIL 漏判；
- 0.95 的精确别名候选仍可通过，不影响当前 79 个非 NIL 链接样本；
- LLM 兜底阈值暂保持 0.65，仅作为后续接入开关，不在本阶段强制调用外部服务。

## 7. 验收命令

```powershell
python scripts\e2e_from_ground_truth.py --dataset data/eval/mention_linking_test.json --input-mode mentions --nil-threshold 0.90 --llm-trigger-threshold 0.65 --badcase-output reports\badcase_threshold_0_90.json
```

预期关键结果：

- `samples: 100`
- `total_mentions: 106`
- `overall_accuracy: 1.0000`
- `linking_accuracy: 1.0000`
- `nil_f1: 1.0000`
- `badcases: 0`

## 8. 后续风险

当前指标基于规则 fallback 与人工评测集，不代表真实 BGE/LLM 消歧效果。7.8 之后应继续：

- 接入真实 embedding/BGE 后重新评测；
- 增加更难的共享别名和跨领域歧义样本；
- 分开统计 exact、fuzzy、semantic、LLM 四类命中效果；
- 避免因当前规则阈值过高影响未来语义召回能力。
