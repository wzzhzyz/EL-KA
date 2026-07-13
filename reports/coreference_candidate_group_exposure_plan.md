# 集合共指候选协调组暴露方案

## 1. 目的与边界

本方案仅为离线篇章状态实验暴露全部合法协调组候选，不改变当前 `RuleBasedCoreferenceResolver.resolve()`、`resolve_link_results()` 或 HTTP API。候选暴露本身不选择唯一答案、不写入数据库、不使用模型，也不依赖样例 ID 或实体名称特例。

正式规则、Acceptance Main、Challenge Dev v1 与 frozen blind holdout v1 均不在本方案的执行范围内。

## 2. 当前实际调用链

```text
Pipeline.process(..., enable_coreference=true)
  -> RuleBasedCoreferenceResolver.resolve_link_results()             [pipeline.py:1166-1174]
  -> RuleBasedCoreferenceResolver.resolve()                          [coreference.py:262-320]
  -> _resolve_anaphor()                                              [coreference.py:422-580]
  -> find_collective_antecedents()                                  [coreference.py:338-401]
  -> _has_coordinate_conjunction()                                 [coreference.py:328-336]
```

集合指代在 `_resolve_anaphor()` 中由 `COLLECTIVE_ANAPHORS` 识别；取得候选前件后，`collective_cardinality_satisfied()` 检查二元、三元或至少两个实体的数量约束，再构造 `CoreferenceResolution` 的 `rule`、`evidence` 和固定 `confidence=0.9`。

`find_collective_antecedents()` 的处理顺序如下：

1. 仅保留目标 mention 同句、位于目标前、且不是指代的 `named_mentions`；
2. 用 `_has_coordinate_conjunction()` 检测相邻 mention 间的 `COORDINATE_CONJUNCTIONS`；
3. 形成长度至少为 2 的 `groups`；
4. 过滤未链接成员、非同质类型组、非 ORG/PERSON 组，以及去重后不足两个 `entity_id` 的组；
5. `for group in reversed(groups): ... return group` 返回首个合格组。

因此，第 5 步只保留最近合法组；更早的组仍在局部变量 `groups` 中，但会在函数返回时丢弃。当前识别支持三实体及以上：连续的 `、`、`和`、`及`、`以及`、`同`、`跟`、`连同`、`会同` 均可将成员累加进同一组。实体 ID 在 `_resolve_anaphor()` 中用 `seen_ids` 保序去重。

## 3. 最小侵入式候选暴露设计

待后续确认后，可在 `entity_linker/coreference.py` 内部新增以下**非公开**辅助函数，或将其作为 `RuleBasedCoreferenceResolver` 的私有方法：

```python
def _collect_coordinated_group_candidates(
    self,
    text: str,
    current_index: int,
    mentions: Sequence[CoreferenceMention],
) -> list[CoordinatedGroupCandidate]:
    ...
```

建议实验数据对象：

```python
@dataclass
class CoordinatedGroupCandidate:
    entity_ids: list[str]
    mention_indices: list[int]
    entity_types: list[str]
    source_sentence_index: int
    source_span_start: int
    source_span_end: int
    group_text: str
    conjunctions: list[str]
    is_nearest_group: bool
    sentence_distance: int
    extraction_rule: str
    evidence: str
```

### 复用与抽取原则

|现有逻辑|处理方式|说明|
|-|-|-|
|`_has_coordinate_conjunction()`|直接复用|确保连接词判断与正式规则完全一致。|
|`COORDINATE_CONJUNCTIONS`|直接复用|不新增或替换连接词集合。|
|同句、位置、非指代过滤|从 `find_collective_antecedents()` 抽取|保持当前合法组定义。|
|已链接、同质类型、ORG/PERSON、去重校验|从 `find_collective_antecedents()` 抽取|避免实验候选比正式规则宽松。|
|`find_collective_antecedents()`|改为调用候选收集器后取最后一个候选|保持“最近合法组优先”的当前行为。|

候选对象中的 `entity_ids`、`mention_indices`、`entity_types`、源句索引和源 span 可由现有 mention 直接得到；`group_text` 由源 span 切片获得；`conjunctions` 需在相邻成员跨度间扫描；`is_nearest_group` 由保留顺序的最后一项标记；`sentence_distance` 由目标与源句索引相减；`extraction_rule` 和 `evidence` 为新增实验解释字段。

## 4. 行为不变保证

正式实现时，`find_collective_antecedents()` 必须继续返回候选列表中的最后一个合法组，且 `_resolve_anaphor()` 继续使用该函数，不能改用篇章分数或候选排序。候选暴露只供离线脚本在明确传入实验开关时调用，不进入 `resolve()` 返回对象、`resolve_link_results()` 或 Pipeline trace。

验证方式：在未开启实验脚本的情况下，对历史 257 条、Acceptance Main 和 Challenge Dev v1 比较 `entity_ids`、`is_nil`、`rule`、`evidence` 与改动前完全一致；另外断言 `find_collective_antecedents()` 的返回值等于候选列表中 `is_nearest_group=true` 的成员列表。

## 5. 当前阻塞

当前 `find_collective_antecedents()` 明确只接受同句候选；跨句候选、句子文本和主题失效状态并不存在。因此仅暴露现有候选组不会自动支持跨句解析。跨句窗口、主体切换与新组覆盖应由独立离线实验层计算，只有满足预先定义的安全门槛后，才评估是否需要最小实现改动。
