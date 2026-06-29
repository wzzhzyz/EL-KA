# 实体标注规范文档

> 版本: 1.0 | 日期: 2026-06-29 | 适用: 课题10 实体链接与知识对齐智能体

---

## 1. Mention 边界标注规则

### 1.1 基本原则

| 规则 | 说明 | 示例 |
|------|------|------|
| 最长匹配 | 优先标注完整实体名，不截断 | "华为技术有限公司深圳分公司" → 整体标注 |
| 嵌套允许 | 一个mention内部可嵌套另一个mention | "华为技术有限公司深圳分公司" 内含 "华为技术有限公司" |
| 人名全标注 | 姓+名完整标注 | "任正非"、"埃隆·马斯克" |
| 地名层级 | 省/市/区分别标注 | "广东省深圳市" → "广东省" + "深圳市" |
| 标点分隔 | 标点符号不作为实体的一部分 | "国家电网，" → 仅标注"国家电网" |

### 1.2 边界判定标准

```
✅ 正确:
  text: "国家电网有限公司2024年营收"
  mention: "国家电网有限公司" (0, 8)

❌ 错误:
  mention: "国家电网有限公司2" (0, 9) — 数字不属于实体名
  mention: "国家电网" (0, 4) — 截断不完整
```

---

## 2. 实体类型分类

### 2.1 NER层类型 → KB层类型映射

| NER类型 (HanLP) | 说明 | KB entity_type 枚举 |
|------|------|------|
| **ORG** | 机构/组织 | GRID_COMPANY, POWER_GENERATOR, NEW_ENERGY_ENTERPRISE, TECH_COMPANY, FINANCIAL_INSTITUTION, AUTO_MANUFACTURER, GOVERNMENT_AGENCY, EDUCATIONAL_INSTITUTION, RESEARCH_INSTITUTION |
| **PERSON** | 人物 | PERSON_BUSINESS, PERSON_POLITICAL, PERSON_ACADEMIC |
| **GPE** | 行政地理实体 | REGION (country/province/city) |
| **LOC** | 非行政地理位置 | POWER_FACILITY, REGION (facility/district) |

### 2.2 易混淆类型判定

| mention | 正确类型 | 说明 |
|------|:--:|------|
| 三峡水电站 | LOC | 具体设施，非行政区域 |
| 国家电网 | ORG | 企业实体，非地名 |
| 北京 | GPE | 直辖市，行政实体 |
| 中关村 | LOC | 功能区，非正式行政区 |
| 大亚湾核电站 | LOC | 电力设施 |

---

## 3. 链接标注规范

### 3.1 标注字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `gold_entity` | string\|null | KB中的entity_id，NIL时为null |
| `candidate_entities` | [string] | 候选实体ID列表（含gold在内） |
| `expected_result.linked` | bool | 是否可链接 |
| `expected_result.confidence` | string | high/medium/low |
| `difficulty` | string | easy/medium/hard |

### 3.2 置信度判定

| confidence | 条件 | 示例 |
|------|------|------|
| high | 精确匹配 + 上下文无歧义 | mention="国网" + 上下文含"特高压" |
| medium | 精确匹配 + 上下文需确认 | mention="国网" + 3个候选 |
| low | 模糊匹配/仅语义 | mention="塔拉滩光伏基地" (非标别名) |

### 3.3 NIL 判定标准

| nil_reason | 条件 |
|------|------|
| entity_not_in_kb | KB中无此实体 |
| mention_too_short | mention长度不足(1字)且非知名简称 |
| cross_domain | 实体属于KB未覆盖领域 |
| ambiguous_collective | 集合指代(如"两家央企") |

---

## 4. 共指标注规范（规则优先）

### 4.1 规则类型

| coref_rule_type | 说明 | 标注额外字段 |
|------|------|------|
| pronoun_backward | 代词回指 (其/它/他/该公司) | coref_antecedent + coref_rule |
| noun_backward | 名词回指 (该企业/这家公司) | coref_antecedent + coref_rule |
| abbreviation_fullname | 简称-全称共指 | coref_antecedent + coref_rule |
| repeated_mention | 同一mention多次出现 | coref_rule |
| english_chinese_coref | 中英文名称共指 | coref_antecedent + coref_rule |

### 4.2 共指标注示例

```json
{
  "mention": "该公司",
  "expected_result": {
    "coref_rule_type": "pronoun_backward",
    "coref_antecedent": "国家电网",
    "coref_rule": "代词'该公司'匹配最近ORG类型先行词(距离44字符)"
  }
}
```

---

## 5. 难度分级标准

| difficulty | 条件 | 比例目标 |
|------|------|:--:|
| easy | 单候选，精确别名匹配 | 50% |
| medium | 多候选需消歧，或非标别名 | 35% |
| hard | OCR错误、NIL、嵌套、共指、链式指代 | 15% |

---

## 6. 标注质量检查清单

```
每样本必检:
□ mention 是 text 的精确子串
□ start/end 位置正确
□ gold_entity 在KB中存在（非NIL时）
□ candidate_entities 含 gold_entity（非NIL时）
□ difficulty 在 {easy, medium, hard} 内
□ scenario 描述准确
□ 共指标注字段完整（如有coref_rule_type）
□ NIL 标注理由充分（如is_nil=true）
```

---

## 7. 协同规范：与NER模块对接

### 7.1 NER输出格式

```json
{
  "mention": "实体指称文本",
  "type": "ORG|PERSON|GPE|LOC",
  "start": 0,
  "end": 5
}
```

### 7.2 EL输入格式

```json
{
  "text": "原始文本",
  "mentions": [
    {"mention": "国网", "type": "ORG", "start": 0, "end": 2}
  ]
}
```

### 7.3 团队约定

- NER层输出 linkable_types: ["ORG", "PERSON", "GPE", "LOC"]
- NER不处理共指代词（"该公司""其""它"等，由coreference模块处理）
- mention边界以NER输出为准，EL不修改边界
- KB的entity_type通过 ner_type_mapping 映射到NER类型
