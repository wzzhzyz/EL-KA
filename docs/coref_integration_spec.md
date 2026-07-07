# 共指消解（Coreference）可选分支设计说明

## 目标

在主流程中添加可选的共指消解分支，通过 API 参数或配置控制启用，以支持代词回链与 mention 合并，提升实体链接的一致性与召回。

## 总体思路

- 将共指消解作为流水线中可插拔的步骤（可选）。
- 默认不启用：保持现有行为。
- 当 `use_coref=True`（API 参数或服务配置）时，执行共指消解并把结果写入 trace 和 DB。

## 所在位置与时序

建议放在 NER 之后、候选生成之前或在初步消歧后进行两种模式之一：

1. 早期合并（NER 后、候选前）：
   - 优点：减少重复候选生成，合并代词到其先行项后统一生成候选。
   - 缺点：对部分系统依赖额外的先行项信息，可能影响候选覆盖率。

2. 后置回链（初步消歧后）：
   - 优点：可先利用上下文消歧出的实体，再把代词指向这些实体，精度更高。
   - 缺点：实现复杂度较高，需确保 link_result 可被回写并合并。

实现建议：先实现后置回链（风险低、便于回退），后续视效果再支持早期合并。

## API 参数约定

- 请求体新增字段：`use_coref: Optional[bool]`（默认 `false`）。
- 可选：`coref_model` 字段指定模型或规则集（例如 `rule-based`、`neural-small`）。

示例请求（JSON）：

{
  "text": "小明去了图书馆。他在那里借了书。",
  "use_ea": false,
  "use_coref": true,
  "coref_model": "neural-small",
}

## Trace 与 DB 留痕

- 在 `pipeline_step` 中新增步骤记录：`coref_resolution`，包含输入 mention 列表、输出合并关系、处理耗时与模型信息。
- 在 `mention` 表或 `link_result` 中写入代词回链字段（参见 `storage_pronoun_schema.md`）。
- 在 trace metadata 中记录 `coref_backend` 与 `fallback_reason`（如模型不可用回退规则）。

## 回退策略

- 若 `use_coref=True` 但共指模块初始化失败，应：
  - 记录 `fallback_reason='coref_init_failed'` 到运行 metadata。
  - 继续执行后续 pipeline（不阻断整体请求）。
  - 在响应 `meta` 中告知客户端。

## 性能与批量处理

- 共指消解可能带来额外延迟，API 应支持 `timeout` 或异步任务模式（批量场景建议异步处理并通过 `trace_id` 查询结果）。
- 批量接口应支持为每条记录单独指定 `use_coref`，也可在批量头部统一指定。

## 日志与监控建议

- 指标：`coref_calls`、`coref_success`、`coref_latency_ms`、`coref_fallbacks`。
- 监控模型准确性随时间变化，和合并后实体链接精度的影响。

## 备注

- 初版可先实现规则化回链（简单代词-人称规则），降低上线门槛。
- 文档中所述 DB 字段与迁移在 `storage_pronoun_schema.md` 中详细说明。