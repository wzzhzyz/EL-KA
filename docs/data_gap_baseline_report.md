# 数据缺口基线统计报告

- 生成时间：2026-07-10T15:41:07
- 成员视角：第三成员欧小红（数据处理、评测数据建设、质量检查）
- 范围说明：本报告只审计数据、脚本和评测材料，不修改核心算法或 API 架构。

## 1. 仓库审计结论

### 1.1 正式回归数据路径

| 数据集 | 路径 |
| --- | --- |
| knowledge_base | data/kb/energy_entities.json |
| mention_linking | data/eval/mention_linking_test.json |
| eval_dataset | data/eval/eval_dataset.json |
| candidate_retrieval | data/eval/candidate_retrieval_test.json |
| disambiguation | data/eval/disambiguation_test.json |
| coreference | data/eval/coreference_long_text_test.json |
| llm_fallback_ambiguity | data/eval/llm_fallback_ambiguity_test.json |
| llm_fallback_difficult | data/eval/llm_fallback_difficult_cases.json |
| batch_texts | data/batch_texts.txt |
| batch_ground_truth | data/batch_ground_truth.json |

### 1.2 Schema 与 ID/NIL 规则摘要

- 知识库实体 ID：已观察到 `ENT_ENERGY_XXXX` 与 `ENT_GEN_XXXX` 两类；后续新增通用实体应沿用 `ENT_GEN_` 最大序号递增。
- mention linking：`MENTION_LINK_001` 连续编号；mention 需要 `char_start/char_end`；NIL 使用 `expected_entities[].entity_id = null`。
- eval dataset：`EVAL_001` 连续编号；NIL 使用 `gold_entity = null` 与 `expected_result.nil=true`。
- candidate retrieval：`CR_001` 连续编号；`expected_candidates` 是候选 entity_id 列表；`gold_entity=null` 表示 NIL-like。
- disambiguation：`DIS_001` 连续编号；`gold_entity=null` 且 `expected_nil=true` 表示 NIL。
- coreference：`COREF_LONG_001` 连续编号；`expected_coreferences[].mention_index` 指向 `mentions` 下标；集合/不可唯一绑定使用 `entity_id=null,is_nil=true`。
- LLM fallback：`LLM_AMB_001`/`LLM_HARD_001` 连续编号；`expected_nil=true,gold_entity_id=null` 表示 NIL。
- batch：`batch_texts.txt` 行号与 `batch_ground_truth.entries[].text_idx` 一一对应；每条可包含多个 `{mention, entity_id}`。

### 1.3 脚本审计

- 数据生成：`scripts/expand_knowledge_base.py`
- 数据校验：`scripts/validate_eval_data.py`
- 共指评测：`scripts/evaluate_coreference.py`、`scripts/evaluate_coreference_rules.py`
- E2E/API 辅助：`scripts/e2e_from_ground_truth.py`
- 本次新增统计：`scripts/report_data_distribution.py`
- `_repo_check/scripts` 下未发现日报截图专用脚本；日报截图工具若位于仓库外层 `scripts/`，不应作为核心业务脚本。

## 2. 主测试集 mention_linking

| 指标 | 数值 |
| --- | --- |
| 样本条数 | 505 |
| 文本条数 | 505 |
| 唯一文本数 | 499 |
| mention 总数 | 1052 |
| LINKED 数 | 867 |
| NIL 数 | 185 |
| LINKED 比例 | 0.8241 |
| NIL 比例 | 0.1759 |
| 重复文本数 | 6 |
| 重复样本 ID | 0 |

- 每条文本 mention 数量分布：`{'0': 2, '1': 208, '2': 137, '3': 90, '4': 48, '5': 13, '6': 6, '7': 1}`
- 实体类型覆盖：`{'AUTO_MANUFACTURER': 69, 'CONSUMER_PRODUCT': 41, 'EDUCATIONAL_INSTITUTION': 57, 'FINANCIAL_INSTITUTION': 92, 'GOVERNMENT_AGENCY': 48, 'GRID_COMPANY': 60, 'MEDIA_ORG': 49, 'MEDICAL_INSTITUTION': 42, 'NEW_ENERGY_ENTERPRISE': 31, 'NIL': 185, 'POWER_FACILITY': 21, 'POWER_GENERATOR': 26, 'REGION': 56, 'RESEARCH_INSTITUTION': 17, 'SOFTWARE_PLATFORM': 62, 'TECHNICAL_TERM': 28, 'TECH_COMPANY': 112, 'TRANSPORTATION_ORG': 56}`
- 难度标注分布：`{'unlabeled': 505}`
- 高频重复 mention（前20）：`{'国家电网': 14, '百度地图': 10, '百度': 9, 'Android': 9, '华为': 8, '腾讯': 8, '国家能源局': 8, '北京大学': 8, '中国移动': 8, '生态环境部': 8, 'iOS': 8, '腾讯会议': 8, '瑞金医院': 8, '国铁集团': 8, '工信部': 7, '上交所': 7, '广州': 7, '世界银行': 7, '阿里巴巴': 7, '飞书': 7}`

## 3. 知识库

| 指标 | 数值 |
| --- | --- |
| 实体总数 | 158 |
| 别名总数 | 490 |
| 缺失 description/summary/business 数 | 0 |
| 缺失 aliases 数 | 0 |
| 重复 entity_id 数 | 0 |
| 重复 canonical name 数 | 0 |
| alias 冲突数量 | 0 |

- 各 entity type 数量：`{'AUTO_MANUFACTURER': 9, 'CONSUMER_PRODUCT': 7, 'EDUCATIONAL_INSTITUTION': 7, 'FINANCIAL_INSTITUTION': 14, 'GOVERNMENT_AGENCY': 7, 'GRID_COMPANY': 8, 'MEDIA_ORG': 9, 'MEDICAL_INSTITUTION': 9, 'NEW_ENERGY_ENTERPRISE': 9, 'POWER_FACILITY': 7, 'POWER_GENERATOR': 10, 'REGION': 11, 'RESEARCH_INSTITUTION': 6, 'SOFTWARE_PLATFORM': 9, 'TECHNICAL_TERM': 12, 'TECH_COMPANY': 15, 'TRANSPORTATION_ORG': 9}`
- 每类平均 alias 数：`{'AUTO_MANUFACTURER': 2.89, 'CONSUMER_PRODUCT': 2.43, 'EDUCATIONAL_INSTITUTION': 3, 'FINANCIAL_INSTITUTION': 3, 'GOVERNMENT_AGENCY': 2.86, 'GRID_COMPANY': 3.75, 'MEDIA_ORG': 2.22, 'MEDICAL_INSTITUTION': 2.33, 'NEW_ENERGY_ENTERPRISE': 3.44, 'POWER_FACILITY': 3, 'POWER_GENERATOR': 4.6, 'REGION': 3.27, 'RESEARCH_INSTITUTION': 3, 'SOFTWARE_PLATFORM': 2.78, 'TECHNICAL_TERM': 3.33, 'TECH_COMPANY': 3.4, 'TRANSPORTATION_ORG': 2.78}`
- 弱覆盖类型（少于8个实体）：`{'CONSUMER_PRODUCT': 7, 'EDUCATIONAL_INSTITUTION': 7, 'GOVERNMENT_AGENCY': 7, 'POWER_FACILITY': 7, 'RESEARCH_INSTITUTION': 6}`
- alias 指向多个实体不直接判错，作为合法歧义/潜在消歧压力记录。

## 4. Candidate Retrieval

| 指标 | 数值 |
| --- | --- |
| 样本总数 | 212 |
| 正样本数 | 164 |
| NIL-like 数 | 48 |
| NIL-like 比例 | 0.2264 |
| 正确实体在 Top-K 中数量 | 164 |
| 正确实体在 Top-K 比例 | 1.0 |
| 无正确候选样本数 | 0 |
| 高相似错误候选样本数 | 157 |

- 候选数量分布：`{'0': 10, '1': 45, '2': 66, '3': 91}`
- 正样本实体类型覆盖：`{'AUTO_MANUFACTURER': 16, 'CONSUMER_PRODUCT': 8, 'EDUCATIONAL_INSTITUTION': 12, 'FINANCIAL_INSTITUTION': 19, 'GOVERNMENT_AGENCY': 8, 'GRID_COMPANY': 14, 'MEDIA_ORG': 11, 'MEDICAL_INSTITUTION': 9, 'NEW_ENERGY_ENTERPRISE': 6, 'POWER_FACILITY': 4, 'POWER_GENERATOR': 10, 'REGION': 3, 'RESEARCH_INSTITUTION': 2, 'SOFTWARE_PLATFORM': 9, 'TECHNICAL_TERM': 1, 'TECH_COMPANY': 19, 'TRANSPORTATION_ORG': 13}`

## 5. Coreference

| 指标 | 数值 |
| --- | --- |
| 样本总数 | 154 |
| 共指 case 总数 | 257 |
| 简单单数指代数 | 185 |
| 跨句指代数 | 158 |
| 跨 3 句以上数 | 6 |
| 集合指代数 | 36 |
| 多候选先行词样本数 | 122 |
| NIL 混合样本数 | 49 |
| 当前规则通过率 | 1.0 |

- 指代表达 Top20：`{'该机构': 32, '该公司': 30, '它': 26, '该平台': 20, '前者': 15, '后者': 15, '上述机构': 9, '该校': 8, '该系统': 8, '该市': 7, '双方': 7, '该院': 7, '该企业': 6, '他': 6, '当地': 5, '她': 5, '两家企业': 4, '上述企业': 4, '他们': 4, '两家公司': 3}`

## 6. LLM Fallback

### 6.1 LLM ambiguity

- 统计：`{'sample_count': 151, 'linked_samples': 108, 'nil_samples': 43, 'nil_ratio': 0.2848, 'difficulty_counts': {'hard': 93, 'medium': 58}, 'ambiguity_type_counts': {'abbreviation_polysemy': 5, 'ai_company_nil': 2, 'ai_company_oov': 1, 'ambiguous_collective': 1, 'ambiguous_coref_nil': 1, 'ambiguous_media_coref': 1, 'ambiguous_medical_coref': 1, 'auto_brand_vs_energy_business': 1, 'auto_company_nil': 1, 'auto_coref_ambiguous': 1, 'auto_short_name': 1, 'auto_vs_storage_business': 1, 'bank_coref_ambiguous': 1, 'bank_short_name': 1, 'collective_financial_nil': 1, 'collective_grid_nil': 1, 'collective_noun_nil': 1, 'collective_product_nil': 1, 'collective_pronoun_nil': 1, 'collective_school_nil': 1, 'common_word_vs_enterprise': 2, 'company_vs_business_line': 1, 'company_vs_product_platform': 1, 'culture_institution_nil': 2, 'education_nil': 2, 'english_alias_business_line': 1, 'english_alias_with_partner': 1, 'enterprise_vs_government': 3, 'exchange_vs_university': 1, 'facility_vs_enterprise': 8, 'government_agency': 4, 'government_agency_vs_energy_regulator': 1, 'historical_name': 1, 'international_org_nil': 1, 'manufacturing_nil': 1, 'medical_institution_nil': 2, 'missing_antecedent_nil': 1, 'multi_system_coref_nil': 1, 'near_name_nil': 10, 'newly_in_kb_after_expansion': 2, 'ordinal_coref_nil': 2, 'out_of_kb_cloud': 1, 'parent_product': 5, 'parent_subsidiary': 2, 'parent_subsidiary_or_business_line': 1, 'platform_enterprise': 1, 'product_alias_cross_language': 1, 'product_version': 2, 'product_vs_enterprise': 4, 'product_vs_parent_company': 2, 'region_similar_city': 3, 'region_vs_enterprise_context': 1, 'research_institution': 1, 'research_institution_short_name': 2, 'resolvable_coref': 1, 'short_name_polysemy': 2, 'similar_financial_institution': 6, 'similar_financial_market': 1, 'similar_grid_company': 3, 'similar_institution': 5, 'similar_power_generator': 1, 'similar_short_name': 10, 'similar_short_video_platform': 1, 'similar_telecom_operator': 4, 'similar_university_short_name': 3, 'single_entity_multi_role': 2, 'software_platform': 3, 'software_platform_comparison': 1, 'software_platform_short_name': 1, 'technical_term': 3, 'transport_coref': 1, 'transport_manufacturer_nil': 2, 'transport_resolvable_coref': 1, 'university_short_name': 1}, 'candidate_count_distribution': {'1': 5, '2': 35, '3': 111}, 'text_length_distribution': {'30-59': 51, '<30': 100}}`

### 6.2 LLM hard cases

- 统计：`{'sample_count': 110, 'linked_samples': 46, 'nil_samples': 64, 'nil_ratio': 0.5818, 'difficulty_counts': {'hard': 90, 'medium': 20}, 'ambiguity_type_counts': {'ai_company_nil': 1, 'ai_energy_lab_nil': 1, 'airline_research_institute_nil': 1, 'airport_consulting_company_nil': 1, 'airport_service_center_nil': 1, 'auto_cockpit_institute_nil': 1, 'auto_lab_nil': 1, 'auto_lab_role_contrast_nil': 1, 'auto_research_institute_nil': 1, 'auto_vs_energy': 1, 'bank_alias': 1, 'batch_c_交易研究所NIL': 1, 'batch_c_医学研究院NIL': 1, 'batch_c_医疗中心NIL': 1, 'batch_c_医疗集团NIL': 1, 'batch_c_地区电网NIL': 1, 'batch_c_电力研究院NIL': 1, 'batch_c_电网近似NIL': 1, 'batch_c_调度中心NIL': 1, 'business_line_vs_group': 1, 'cloud_rnd_center_nil': 1, 'collective_financial': 1, 'collective_government_coref': 1, 'collective_product': 1, 'collective_pronoun': 1, 'collective_school': 1, 'company_product_boundary': 1, 'company_vs_product': 1, 'company_vs_product_line': 1, 'coref_auto_business_cue': 1, 'coref_media_language_cue': 1, 'coref_role_disambiguation': 1, 'coref_semantic_override': 1, 'cross_domain_nil': 1, 'culture_institution_nil': 1, 'dispatch_center_nil': 1, 'education_vs_research_org': 1, 'english_alias_auto_link': 1, 'english_alias_business_line': 1, 'english_alias_grid_link': 1, 'english_alias_media_link': 1, 'exchange_oov_nil': 1, 'exchange_vs_university': 1, 'facility_vs_enterprise': 1, 'finance_platform_vs_exchange': 2, 'generic_alias': 1, 'government_agency': 1, 'government_agency_vs_regulator': 1, 'government_vs_enterprise': 1, 'grid_design_institute_nil': 1, 'hospital_short_name': 1, 'hospital_short_name_disambiguation': 1, 'international_finance_nil': 1, 'international_org_nil': 2, 'manufacturing_nil': 1, 'media_channel_nil': 1, 'media_data_institute_nil': 1, 'media_lab_nil': 1, 'media_lab_role_contrast_nil': 1, 'media_oov_nil': 1, 'medical_center_nil': 1, 'medical_group_nil': 1, 'medical_institution_nil': 1, 'medical_nil': 1, 'medical_research_institute_nil': 1, 'metro_research_institute_nil': 1, 'missing_antecedent': 1, 'near_alias_nil': 1, 'near_domain_ai_nil': 1, 'near_name_media_nil': 1, 'near_name_nil': 2, 'near_region_enterprise_nil': 1, 'office_product_oov': 1, 'oov_grid_like_org': 1, 'operator_disambiguation': 1, 'ordinal_coreference': 2, 'parent_product': 1, 'parent_subsidiary_shared_alias': 1, 'parent_vs_product': 1, 'power_trade_research_nil': 1, 'product_variant_nil': 1, 'product_vs_company': 1, 'product_vs_parent': 1, 'product_vs_parent_company': 1, 'region_similar_city': 1, 'regional_exchange_center_nil': 1, 'regional_exchange_nil': 1, 'regional_grid_alias': 1, 'research_institute_vs_grid_company': 1, 'research_institution_vs_parent_company': 1, 'role_contrast_nil': 1, 'same_prefix_nil': 1, 'short_alias_finance': 1, 'short_form_ambiguous_nil': 1, 'similar_financial': 1, 'similar_map_platform': 1, 'similar_telecom_operator': 3, 'similar_university': 2, 'software_platform_comparison': 1, 'software_product': 2, 'system_oov_nil': 1, 'telemedicine_center_nil': 1}, 'candidate_count_distribution': {'2': 3, '3': 107}, 'text_length_distribution': {'30-59': 57, '<30': 53}}`

## 7. Batch

| 指标 | 数值 |
| --- | --- |
| 样本总数 | 214 |
| 文本行数 | 214 |
| 长文本数量 | 0 |
| 多 mention 数量 | 127 |
| LINKED+NIL 混合数量 | 47 |
| 共指混合数量 | 15 |
| 重复 mention 请求数 | 1 |

- 每条请求 mention 数量分布：`{'0': 3, '1': 84, '2': 46, '3': 48, '4': 33}`
- 实体类型覆盖：`{'AUTO_MANUFACTURER': 41, 'CONSUMER_PRODUCT': 17, 'EDUCATIONAL_INSTITUTION': 10, 'FINANCIAL_INSTITUTION': 32, 'GOVERNMENT_AGENCY': 14, 'GRID_COMPANY': 38, 'MEDIA_ORG': 32, 'MEDICAL_INSTITUTION': 29, 'NEW_ENERGY_ENTERPRISE': 11, 'NIL': 86, 'POWER_FACILITY': 9, 'POWER_GENERATOR': 12, 'REGION': 18, 'RESEARCH_INSTITUTION': 4, 'SOFTWARE_PLATFORM': 28, 'TECH_COMPANY': 39, 'TRANSPORTATION_ORG': 32}`

## 8. 当前主要不足

1. mention linking 当前 379 条，距离 500～520 目标仍缺约 121～141 条。
2. 知识库弱类型仍明显存在，尤其 `GRID_COMPANY`、`MEDICAL_INSTITUTION`、`TRANSPORTATION_ORG`、`MEDIA_ORG`、`AUTO_MANUFACTURER` 都少于 8 个实体。
3. candidate retrieval 的 NIL-like 为 16/151，占比约 10.6%，候选召回层面的未入库与高相似干扰仍不足。
4. coreference 当前全通过，但跨 3 句以上样本为 0，说明长距离指代压力不足；多候选先行词数量虽有覆盖，但还需要更难的指代切换和部分集合指代。
5. LLM hard cases 当前 63 条，距离 100～120 目标仍缺 37～57 条。
6. batch 当前 155 条，距离 200～220 目标仍缺 45～65 条；长文本数量偏少，共指混合数量偏低。
