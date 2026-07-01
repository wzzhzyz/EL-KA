# NIL场景人工判定标准

> 版本: 1.0 | 用途: NIL检测模块评测依据

---

## 1. NIL判定流程

```
mention + context
       │
       ▼
  alias精确命中? ──YES──> 非NIL (高置信)
       │NO
       ▼
  alias模糊命中(ed<=1)? ──YES──> BGE语义验证
       │NO                         │
       ▼                  score>=0.65? ──YES──> 非NIL
  BGE语义检索                        │NO
       │                              ▼
       ▼                             NIL
  max_similarity < nil_threshold(0.65)? ──YES──> NIL
       │NO
       ▼
  非NIL (低置信)
```

## 2. NIL分类体系

| # | nil_reason | 定义 | 判定条件 | 示例 |
|---|-----------|------|------|------|
| 1 | entity_not_in_kb | 实体不在KB中 | alias未命中 + BGE<0.4 | "阳光新能源"不在KB |
| 2 | mention_too_short | mention过短(1字) | len(mention)=1 且非知名简称 | "网" (无法确定指哪家电网) |
| 3 | ambiguous_collective | 集合指代 | 指代多个实体 | "两家央企" "这些企业" |
| 4 | mention_is_coref | 共指代词 | 需coref模块先解析 | "该公司" "其" "它" |
| 5 | cross_domain | 跨领域实体 | KB未覆盖该领域 | 医疗实体出现在能源KB中 |
| 6 | insufficient_context | 上下文不足 | 上下文窗口内无消歧信息 | 孤立mention无上下文 |

## 3. 阈值说明

| 阈值 | 默认值 | 含义 |
|------|:--:|------|
| nil_threshold | 0.65 | BGE最高相似度低于此值→NIL |
| bge_llm_trigger | 0.65 | 低于此值触发LLM兜底(如开启) |
| alias_fuzzy_ed | 1 | 模糊匹配最大编辑距离 |

## 4. NIL判定示例

| mention | context | alias命中 | BGE max | 判定 | nil_reason |
|------|------|:--:|:--:|:--:|------|
| 国网 | 特高压输电... | YES | 0.96 | 非NIL | — |
| 阳光新能源 | 光伏逆变器... | NO | 0.35 | NIL | entity_not_in_kb |
| 工信部 | 5G发展规划 | NO | 0.28 | NIL | entity_not_in_kb |
| 两家央企 | 加大了新能源投资 | NO | 0.15 | NIL | ambiguous_collective |
| 该公司 | 营收同比增长8% | NO | 0.10 | NIL | mention_is_coref |
| 囯网 | 特高压输电... | NO(模糊ed=1) | 0.72 | 非NIL | —(OCR容错后确认) |
