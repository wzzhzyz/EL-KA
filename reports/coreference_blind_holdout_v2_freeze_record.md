# Blind Holdout v2 运行前冻结记录

- Git HEAD：运行前由 `git rev-parse HEAD` 记录。
- 配置默认值：`enable_collective_ambiguity_rejection=false`。
- 冻结阈值：共享模块 `FROZEN_EVIDENCE_MAX=2`。
- 触发条件：至少两个合法协调组、最近组数量合法、无主体持续且存在主体/事件切换证据。
- 纪律：Holdout v2 生成后先做质量审计；本阶段不运行 OFF/ON，也不据此改规则、阈值、gold 或数据。
