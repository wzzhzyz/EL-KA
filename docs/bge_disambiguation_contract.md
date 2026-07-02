# BGE 消歧端口对齐草案

## 目标

把同事 `EntityAlignmentV0` 中的 BGE 消歧能力，统一接到我们当前的 `entity_linker` 结构上，先对齐端口和数据契约，明天再接入真实模型实现。

## 输入契约

消歧端口约定为：

- `mention: str`
- `candidates: Sequence[Candidate]`
- `context: str = ""`

其中 `Candidate` 为：

- `entity: StandardEntity`
- `score: float`
- `method: str`
- `metadata: dict`

## 输出契约

统一输出为字典或可归一化结果：

- `entity: StandardEntity | None`
- `score: float`
- `method: str`
- `evidence: str`
- `raw: dict`（可选）

如果判定为 NIL，`entity` 为空或 `entity_id = NIL`。

## 文本构造规则

与同事 BGE 逻辑保持一致：

- query:
  - 有上下文：`query: 上下文中的mention指的是什么？上下文：...，mention：...`
  - 无上下文：`query: 实体指称 ... 指的是什么？`
- passage:
  - `标准实体名`
  - `别名`
  - `类型`
  - `描述`
  - `所属行业`
  - `标签`

## 现阶段已完成

- `entity_linker/ports.py`
- `entity_linker/bge_contract.py`
- `entity_linker/models.py` 中的 `Candidate` / `StandardEntity` / `StandardMention`

## 明天接入时的对接点

- 在 `EntityLinkingPipeline` 中把 `_NullDisambiguator` 替换为 BGE 实现
- 保持 `CandidateGeneratorPort.generate(...)` 返回 `List[Candidate]`
- 保持 `DisambiguatorPort.disambiguate(...)` 返回标准结果字典
