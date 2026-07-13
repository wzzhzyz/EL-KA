# 集合共指篇章状态离线实验设计

## 1. 范围

本设计服务于 `coreference_challenge_dev_v2` 的离线开发实验。它不修改正式共指决策、不接入 BGE/FAISS、不变更公开 API，也不运行 frozen blind holdout v1。

候选组仅来自显式连接词与已链接 mention；篇章状态只对候选进行解释性打分。语义不确定时，实验方案必须倾向 NIL。

## 2. 实验对象

```python
@dataclass
class CollectiveDiscourseState:
    entity_ids: list[str]
    mention_indices: list[int]
    entity_types: list[str]
    source_sentence_index: int
    source_text: str
    conjunctions: list[str]
    activation_score: float
    invalidated: bool
    invalidation_reason: str | None


@dataclass
class DiscourseStateFeatures:
    sentence_distance: int
    is_nearest_group: bool
    has_new_subject_between: bool
    has_new_group_between: bool
    named_entity_count_between: int
    event_keyword_overlap: float
    verb_continuity: float
    entity_type_compatible: bool
    cardinality_match: bool
    subject_switch_marker: str | None
```

## 3. 特征口径

|特征|定义与计算|范围|正例预期|NIL 预期|风险|额外模型|
|-|-|-|-|-|-|-|
|`sentence_distance`|目标句索引减候选源句索引；只保留 0～2|整数 0～2|0 或 1 为主，少量 2|距离更大或受新事件干扰|短距离也可能语义切换|否|
|`is_nearest_group`|候选是否为目标前最后一个合法协调组|布尔|通常为真|多组竞争时不足以判定|会偏向最近组|否|
|`has_new_subject_between`|中间句是否出现新命名实体，且伴随主体切换词或主语位置启发式|布尔|通常为假|常为真|无句法分析时主语判断近似|否，启发式|
|`has_new_group_between`|候选源句与目标句之间是否形成另一合法协调组|布尔|通常为假；新组覆盖时应选择新组|竞争 NIL 时为真|新组可能是背景信息|否|
|`named_entity_count_between`|中间句中已链接 name mention 数量|非负整数|低|较高时增加不确定性|数量不能单独表示切换|否|
|`event_keyword_overlap`|候选源句与目标句的非停用词集合 Jaccard，去除实体表面词|0.0～1.0|相对较高|事件切换时较低|同义改写会被低估|否，词面近似|
|`verb_continuity`|两个句子是否共享轻量行动词词表或“发布→公布”等预定义通用动作类|0.0～1.0|较高|切换时较低|词表覆盖有限，不能当语义理解|否，词典近似|
|`entity_type_compatible`|集合前件 coarse type 与代词表面所允许类型是否兼容|布尔|真|如“她们”指 ORG 时为假|现有类型体系较粗|否|
|`cardinality_match`|调用现有 `collective_cardinality_satisfied()`|布尔|真|常为假，或虽真仍不足以选择|不解决多组歧义|否|
|`subject_switch_marker`|中间跨度是否含“随后由”“转而由”“接管”“与此同时”“另一方面”等通用切换标记|字符串或 `null`|通常为 `null`|可能有值|词面未覆盖会漏检|否|

`sentence_index` 不是所有输入数据的固有字段。离线脚本应在内存副本上用 `[。！？!?]` 终止符计算轻量句序号；不得把计算结果写回 gold 数据。候选源句和中间句文本可通过同一分句结果取得。

## 4. 可解释评分与决策

每个候选先经数量与类型硬过滤。其余项归一化后按以下结构评分：

```python
score = (
    recency_score
    + cardinality_score
    + type_compatibility_score
    + event_continuity_score
    - subject_switch_penalty
    - new_group_penalty
    - competing_group_penalty
)
```

最终 `total_score` 映射到 0.0～1.0，并同时保存每一个分项。`select_threshold`、`nil_threshold` 与 `margin_threshold` 本阶段不设定数值：后续只能在 Challenge Dev v2 的正例与 NIL 对照共同校准，不能针对单条样例设置。

决策约束为：最高候选达到 `select_threshold` 且与第二名差值达到 `margin_threshold` 才可选择；所有候选低于 `nil_threshold` 或差距不足时输出 NIL。若正例有所提升而 NIL Accuracy 明显下降，实验判为失败。

## 5. 方案对照与可行性门槛

离线脚本预留四种无模型方案：

|方案|含义|
|-|-|
|`baseline_current_rule`|原始 resolver 的输出，仅作基线。|
|`nearest_group_only`|只选择暴露候选中的最近组。|
|`recency_and_cardinality`|最近度加现有数量约束。|
|`discourse_features`|使用全部篇章特征和可解释评分。|

只有同时满足以下条件，才建议申请正式实现：

1. Challenge Dev v2 总体准确率相对基线提升至少 8 个百分点；
2. NIL Accuracy 下降不超过 2 个百分点；
3. Acceptance Main 不下降；
4. 历史单实体保持 257/257；
5. 不依赖样例 ID、固定文本或具体实体名特例。

## 6. 实现阻塞分析

|事项|状态|说明|
|-|-|-|
|现有同句协调组提取|可通过局部辅助函数解决|现有函数可复用，但只返回最近一个组。|
|三实体协调组|无阻塞|现有连续连接词逻辑可形成任意长度组。|
|实体 ID 去重|无阻塞|现有 `_resolve_anaphor()` 已用 `seen_ids` 保序去重。|
|`sentence_index` 总是存在|可通过局部辅助函数解决|运行时由上游结果决定；v2 数据未固化，需要实验内存补全。|
|可靠取得句间文本|可通过局部辅助函数解决|可用轻量分句；引号、缩写和复杂标点会降低可靠性。|
|新主体识别|可通过局部辅助函数解决|无依存句法，只能使用已链接 name、位置和切换标记近似。|
|谓词/事件连续性|需要额外 NLP 依赖才可可靠实现|当前无词性、依存或谓词分析；首版仅做词面近似。|
|产品统一 coarse type|可通过局部辅助函数解决|现有 `normalize_type()` 不会将产品类型归为 ORG/PERSON；需实验映射表，不能改变正式过滤。|
|跨句候选组|不建议在当前阶段直接实现|当前正式函数限定同句；应先验证离线收益。|
|公开 API|无阻塞|实验对象和分数不进入 API。|

## 7. 预期实验输出

每个 case 应保留 gold、候选组、特征、分项分数、选择结果与理由。若候选暴露尚未完成，输出必须明确标为 `NOT_EVALUATED`，不能将设计占位当成指标结果。
