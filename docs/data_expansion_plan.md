# 数据扩充实施计划

- 生成时间：2026-07-10T15:41:07
- 成员视角：第三成员欧小红
- 当前状态：已完成阶段一仓库审计与阶段二基线统计；本计划用于后续分批扩充，不在本阶段直接批量造数。

## 1. 目标表

| 数据集 | 当前数量 | 目标数量 | 预计新增 | 主要补充类型 | 校验方式 |
| --- | --- | --- | --- | --- | --- |
| mention linking | 505 | 500～520 | 5 | 类型平衡、NIL、歧义、多表达体裁 | Schema + validate_eval_data + 抽检 |
| candidate retrieval | 212 | 210 | 0 | NIL-like、高相似错误候选、未入库实体 | Schema + TopK 覆盖统计 |
| coreference | 154 | 150 | 0 | 多候选、跨3句、集合、NIL混合、指代切换 | 共指回归 + badcase 记录 |
| LLM fallback hard | 110 | 100～120 | 0 | 同名异指、信息稀疏、行业知识、冲突线索 | 人工抽检 + 回归 |
| batch | 214 | 200～220 | 0 | 长文本、多mention、LINKED+NIL、共指混合 | batch ground truth 校验 |

## 2. 分批策略

### 批次 A：Schema 和生成器验证

- 新增规模：mention linking 10～15 条，candidate 5～10 条，coreference 5～8 条，LLM hard 5 条，batch 5 条。
- 覆盖内容：各文件最小闭环样本、NIL 表示、连续 ID、span、batch text_idx。
- 校验：`python scripts/validate_eval_data.py`、`python scripts/evaluate_coreference_rules.py --fail-on-wrong`、人工抽检 10 条。
- Git 建议：`数据扩充批次A schema验证样本`。

### 批次 B：弱类型知识库与正样本

- 新增规模：每个弱类型 2～4 个实体，合计约 12～18 个实体；mention 正样本约 35～45 条。
- 重点类型：`GRID_COMPANY`、`MEDICAL_INSTITUTION`、`TRANSPORTATION_ORG`、`MEDIA_ORG`、`AUTO_MANUFACTURER`。
- 同步文件：`data/kb/energy_entities.json`、`mention_linking_test.json`、`eval_dataset.json`、`candidate_retrieval_test.json`、`batch_*`。
- 校验：实体 ID 唯一、alias 非空、description/summary 可消歧、至少一条正样本覆盖。
- Git 建议：`补充弱类型知识库实体和正样本`。

### 批次 C：NIL 与候选召回压力样本

- 新增规模：candidate retrieval 35～45 条，其中 NIL-like 至少 25 条；mention linking 30～40 条。
- 覆盖内容：未入库机构、地区前缀差异、同名近似、错别字/缩写、候选存在高相似错误实体。
- 不修改核心算法；若正确实体未召回，应记录为候选召回边界，而不是强行改 expected result。
- Git 建议：`增强NIL和候选召回压力样本`。

### 批次 D：困难共指样本

- 新增规模：coreference 35～40 条。
- 覆盖内容：跨 3 句以上、多候选先行词、前者/后者连续切换、集合指代只覆盖部分实体、NIL 与已链接实体混合。
- 若共指规则失败：先输出 badcase 分析，区分样本错误与算法真实边界；不擅自重构算法。
- Git 建议：`补充困难共指评测样本`。

### 批次 E：LLM Fallback 困难样本

- 新增规模：LLM hard cases 40～50 条，目标达到 100～120 条。
- 覆盖内容：同名异指、候选描述高度接近、信息稀疏、长距离上下文、行业知识依赖、旧称/简称混合、NIL。
- 抽检要求：新增样本不能是简单精确别名匹配；每条必须有 decisive_evidence。
- Git 建议：`扩充LLM兜底困难样本`。

### 批次 F：Batch 回归样本

- 新增规模：batch 45～55 条，目标达到 200～220 条。
- 覆盖内容：长文本、多 mention、LINKED+NIL 混合、重复 mention、同一实体多别名、中英文别名、共指链、部分失败场景。
- 校验：text_idx 连续、mention 在文本中、输出数量与输入 mention 一致、NIL 不串位。
- Git 建议：`扩充batch回归样本`。

## 3. 数据质量控制

- 避免数据泄漏：测试样本不直接复制知识库 summary；使用上下文证据而不是把答案写进模板。
- 防止伪多样性：每批限制同一模板复用，覆盖新闻体、公告体、对话体、报告体、行业分析体、长段落和中英文混合。
- LINKED/NIL 比例：主测试集维持 NIL mention 约 18%～25%；candidate retrieval 将 NIL-like 提升到约 25%～35%。
- 类型覆盖：弱类型实体数量至少提升到 8～10 个，并确保每个新增实体至少被一个正样本和一个 batch/候选样本覆盖。
- 难度覆盖：eval 与 LLM hard 中 hard/medium 样本比例保持可解释，不把简单精确匹配伪装成 hard。
- 回滚方式：每批独立提交；若校验失败，优先回滚本批新增样本，不删除历史样本、不降低断言。

## 4. 当前不执行的事项

- 不训练或实现 NER。
- 不重构实体链接 pipeline、API 服务或其他成员负责模块。
- 不为了让困难共指样本通过而修改核心算法；失败样本先进入 badcase。
