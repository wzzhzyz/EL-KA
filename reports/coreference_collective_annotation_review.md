# 集合共指正式验收集人工复核清单

## 1. 复核范围与口径

- 数据集：`data/eval/coreference_collective_eval.json`；`evaluation_scope=acceptance`，`requires_runtime_kb=true`。
- 复核对象：125 条文本、125 个 case；集合正例 83，集合 NIL 37，普通单数 NIL 5。
- Challenge Dev：25 条，已用于规则失败分析；单元夹具 `coreference_collective_test.json` 不计入。
- 正例要求集合 `entity_ids` 精确匹配且 `is_collective=true`、`is_nil=false`；集合成功的 `entity_id=null` 不表示 NIL。
- 原始 60 条为已冻结的首版正式集，未补写 `subset`/`difficulty` 字段；表中以 `acceptance_main（历史元数据）` 标记，避免改写既有 gold。

## 2. 逐条复核表

“需要二次人工确认”优先标记盲测、跨句、主体切换、多协调组、类型冲突和复杂 NIL；该标记表示需确认语义边界，不表示数据有错误。

|Sample ID|文本|目标指代|上下文前件（mention / ID）|Gold `entity_ids`|NIL|场景|难度|子集|审核说明|需要二次人工确认|
|-|-|-|-|-|-|-|-|-|-|-|
|CORE_COL_EVAL_001|国家电网和南方电网签署合作协议，双方将共建能源平台。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`|否|two_org_same_sentence_and|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_002|国家电网、南方电网及华能集团启动联合项目，这些企业将共享研究成果。|这些企业|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`；华能集团 / `ENT_ENERGY_0003`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`、`ENT_ENERGY_0003`|否|three_org_same_sentence_and|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_003|国家电网以及三峡集团联合发布公告，这些机构将推进清洁能源建设。|这些机构|国家电网 / `ENT_ENERGY_0001`；三峡集团 / `ENT_ENERGY_0008`|`ENT_ENERGY_0001`、`ENT_ENERGY_0008`|否|two_org_same_sentence_yiji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_004|华能集团及三峡集团共同建设水电基地，二者将共享调度经验。|二者|华能集团 / `ENT_ENERGY_0003`；三峡集团 / `ENT_ENERGY_0008`|`ENT_ENERGY_0003`、`ENT_ENERGY_0008`|否|two_org_same_sentence_ji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_005|国家电网和南方电网先后发布公告。双方将继续合作。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|当前规则不支持跨句隐式集合|是|
|CORE_COL_EVAL_006|国家电网和南方电网负责输电，华能集团与三峡集团负责发电，双方同步公布计划。|双方|华能集团 / `ENT_ENERGY_0003`；三峡集团 / `ENT_ENERGY_0008`|`ENT_ENERGY_0003`、`ENT_ENERGY_0008`|否|multiple_coordination_nearest_group|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|是|
|CORE_COL_EVAL_007|华为与广州市共同举办活动，他们随后发布公告。|他们|华为 / `ENT_GEN_0051`；广州市 / `ENT_GEN_0093`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|ORG与GPE前件类型不兼容|是|
|CORE_COL_EVAL_008|甲机构和乙机构联合发布报告，这些机构表示将继续合作。|这些机构|甲机构 / `未链接`；乙机构 / `未链接`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|前件未链接到运行知识库|否|
|CORE_COL_EVAL_009|国家电网和南方电网发布联合声明，他将继续跟进。|他|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|单数人物代词不能回指机构集合|否|
|CORE_COL_EVAL_010|华为和腾讯宣布成立联合实验室，两家公司将共同投入研发。|两家公司|华为 / `ENT_GEN_0051`；腾讯 / `ENT_GEN_0052`|`ENT_GEN_0051`、`ENT_GEN_0052`|否|two_company_same_sentence|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_011|国家电网及南方电网共同编制规划，双方将推进跨区输电。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`|否|two_org_same_sentence_ji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_012|国家电网以及南方电网发布联合倡议，两家央企将协同落实。|两家央企|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`|否|two_org_same_sentence_yiji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_013|华能集团和三峡集团签订技术协议，这些企业将共享水电数据。|这些企业|华能集团 / `ENT_ENERGY_0003`；三峡集团 / `ENT_ENERGY_0008`|`ENT_ENERGY_0003`、`ENT_ENERGY_0008`|否|two_generator_same_sentence_and|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_014|华能集团与三峡集团组织联合调度，上述企业将交流运行经验。|上述企业|华能集团 / `ENT_ENERGY_0003`；三峡集团 / `ENT_ENERGY_0008`|`ENT_ENERGY_0003`、`ENT_ENERGY_0008`|否|two_generator_same_sentence_yu|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_015|华为及腾讯发布开放平台，两家公司将投入研发资源。|两家公司|华为 / `ENT_GEN_0051`；腾讯 / `ENT_GEN_0052`|`ENT_GEN_0051`、`ENT_GEN_0052`|否|two_tech_same_sentence_ji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_016|华为以及腾讯共建实验室，双方计划开放测试环境。|双方|华为 / `ENT_GEN_0051`；腾讯 / `ENT_GEN_0052`|`ENT_GEN_0051`、`ENT_GEN_0052`|否|two_tech_same_sentence_yiji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_017|百度和腾讯联合开展安全研究，两家企业将发布白皮书。|两家企业|百度 / `ENT_GEN_0070`；腾讯 / `ENT_GEN_0052`|`ENT_GEN_0070`、`ENT_GEN_0052`|否|two_tech_same_sentence_and|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_018|北京大学及上海交通大学启动论坛，两所高校将共同组织报告会。|两所高校|北京大学 / `ENT_GEN_0064`；上海交通大学 / `ENT_GEN_0065`|`ENT_GEN_0064`、`ENT_GEN_0065`|否|two_university_same_sentence_ji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_019|北京大学以及上海交通大学建设课程平台，两家高校将共享教学资源。|两家高校|北京大学 / `ENT_GEN_0064`；上海交通大学 / `ENT_GEN_0065`|`ENT_GEN_0064`、`ENT_GEN_0065`|否|two_university_same_sentence_yiji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_020|国家电网、南方电网和华能集团发布年度计划，多家企业将联合实施。|多家企业|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`；华能集团 / `ENT_ENERGY_0003`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`、`ENT_ENERGY_0003`|否|three_org_same_sentence_dunhao|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_021|华为、腾讯及百度推进开源社区，这些企业将共同维护项目。|这些企业|华为 / `ENT_GEN_0051`；腾讯 / `ENT_GEN_0052`；百度 / `ENT_GEN_0070`|`ENT_GEN_0051`、`ENT_GEN_0052`、`ENT_GEN_0070`|否|three_tech_same_sentence_mixed_conjunction|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_022|国家电网与华能集团开展储能合作，二者将共享调峰能力。|二者|国家电网 / `ENT_ENERGY_0001`；华能集团 / `ENT_ENERGY_0003`|`ENT_ENERGY_0001`、`ENT_ENERGY_0003`|否|two_org_same_sentence_yu|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_023|三峡集团和国家电网联合建设基地，双方将统一项目进度。|双方|三峡集团 / `ENT_ENERGY_0008`；国家电网 / `ENT_ENERGY_0001`|`ENT_ENERGY_0008`、`ENT_ENERGY_0001`|否|two_org_same_sentence_and|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_024|腾讯与百度合作研发模型，两家公司将共同投入算力。|两家公司|腾讯 / `ENT_GEN_0052`；百度 / `ENT_GEN_0070`|`ENT_GEN_0052`、`ENT_GEN_0070`|否|two_tech_same_sentence_yu|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_025|国家电网及三峡集团协调水电外送，上述机构将发布方案。|上述机构|国家电网 / `ENT_ENERGY_0001`；三峡集团 / `ENT_ENERGY_0008`|`ENT_ENERGY_0001`、`ENT_ENERGY_0008`|否|two_org_same_sentence_ji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_026|华为和百度推出兼容方案，它们将同步更新文档。|它们|华为 / `ENT_GEN_0051`；百度 / `ENT_GEN_0070`|`ENT_GEN_0051`、`ENT_GEN_0070`|否|two_tech_same_sentence_and|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_027|南方电网及华能集团举行技术交流，这些机构将跟进试点。|这些机构|南方电网 / `ENT_ENERGY_0002`；华能集团 / `ENT_ENERGY_0003`|`ENT_ENERGY_0002`、`ENT_ENERGY_0003`|否|two_org_same_sentence_ji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_028|北京大学和上海交通大学共同举办竞赛，二者将联合评审。|二者|北京大学 / `ENT_GEN_0064`；上海交通大学 / `ENT_GEN_0065`|`ENT_GEN_0064`、`ENT_GEN_0065`|否|two_university_same_sentence_and|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_029|华能集团以及华为开发能源系统，两家企业将共享接口规范。|两家企业|华能集团 / `ENT_ENERGY_0003`；华为 / `ENT_GEN_0051`|`ENT_ENERGY_0003`、`ENT_GEN_0051`|否|cross_domain_same_sentence_yiji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|是|
|CORE_COL_EVAL_030|三峡集团与华为建设数字孪生平台，双方将组织验收。|双方|三峡集团 / `ENT_ENERGY_0008`；华为 / `ENT_GEN_0051`|`ENT_ENERGY_0008`、`ENT_GEN_0051`|否|cross_domain_same_sentence_yu|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|是|
|CORE_COL_EVAL_031|国家电网和南方电网在年度会议上签约，两家机构将建立联络机制。|两家机构|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`|否|two_org_with_event_insertion|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_032|华为与腾讯面向开发者发布工具，它们将持续维护社区。|它们|华为 / `ENT_GEN_0051`；腾讯 / `ENT_GEN_0052`|`ENT_GEN_0051`、`ENT_GEN_0052`|否|two_tech_same_sentence_yu|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_033|三峡集团以及华能集团联合检修机组，这些机构将共享检修记录。|这些机构|三峡集团 / `ENT_ENERGY_0008`；华能集团 / `ENT_ENERGY_0003`|`ENT_ENERGY_0008`、`ENT_ENERGY_0003`|否|two_generator_same_sentence_yiji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_034|百度及华为共同发布智能终端规范，两家公司将协商版本计划。|两家公司|百度 / `ENT_GEN_0070`；华为 / `ENT_GEN_0051`|`ENT_GEN_0070`、`ENT_GEN_0051`|否|two_tech_same_sentence_ji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_035|国家电网、南方电网以及三峡集团共同成立工作组，上述企业将轮流牵头。|上述企业|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`；三峡集团 / `ENT_ENERGY_0008`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`、`ENT_ENERGY_0008`|否|three_org_same_sentence_dunhao_yiji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_036|华为和腾讯签署数据安全协议，双方将定期开展评估。|双方|华为 / `ENT_GEN_0051`；腾讯 / `ENT_GEN_0052`|`ENT_GEN_0051`、`ENT_GEN_0052`|否|two_company_policy_style|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_037|北京大学与上海交通大学建立联合实验班，两所大学将共同制定课程。|两所大学|北京大学 / `ENT_GEN_0064`；上海交通大学 / `ENT_GEN_0065`|`ENT_GEN_0064`、`ENT_GEN_0065`|否|two_university_same_sentence_yu|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_038|国家电网及三峡集团推进抽蓄项目，这些企业将联合复盘。|这些企业|国家电网 / `ENT_ENERGY_0001`；三峡集团 / `ENT_ENERGY_0008`|`ENT_ENERGY_0001`、`ENT_ENERGY_0008`|否|two_org_same_sentence_ji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_039|南方电网和华能集团组织应急演练，二者将共享处置预案。|二者|南方电网 / `ENT_ENERGY_0002`；华能集团 / `ENT_ENERGY_0003`|`ENT_ENERGY_0002`、`ENT_ENERGY_0003`|否|two_org_same_sentence_and|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_040|腾讯、百度以及华为发布行业倡议，多家企业将协同落实。|多家企业|腾讯 / `ENT_GEN_0052`；百度 / `ENT_GEN_0070`；华为 / `ENT_GEN_0051`|`ENT_GEN_0052`、`ENT_GEN_0070`、`ENT_GEN_0051`|否|three_tech_same_sentence_dunhao_yiji|未标注（历史元数据）|acceptance_main（历史元数据）|使用运行知识库真实 ID，集合精确匹配|否|
|CORE_COL_EVAL_041|国家电网和南方电网分别发布公告。双方将继续沟通。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|跨句集合不在当前规则支持范围|是|
|CORE_COL_EVAL_042|华能集团与三峡集团完成会谈。这些机构将另行公布细节。|这些机构|华能集团 / `ENT_ENERGY_0003`；三峡集团 / `ENT_ENERGY_0008`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|跨句集合不在当前规则支持范围|是|
|CORE_COL_EVAL_043|华为和腾讯发布声明。两家公司将安排后续测试。|两家公司|华为 / `ENT_GEN_0051`；腾讯 / `ENT_GEN_0052`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|跨句集合不在当前规则支持范围|是|
|CORE_COL_EVAL_044|北京大学及上海交通大学举行会议。两所高校将继续交流。|两所高校|北京大学 / `ENT_GEN_0064`；上海交通大学 / `ENT_GEN_0065`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|跨句集合不在当前规则支持范围|是|
|CORE_COL_EVAL_045|国家电网、南方电网和华能集团公布结果。多家企业将参与复盘。|多家企业|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`；华能集团 / `ENT_ENERGY_0003`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|跨句集合不在当前规则支持范围|是|
|CORE_COL_EVAL_046|华为与广州市共同举办展会，他们随后发布公告。|他们|华为 / `ENT_GEN_0051`；广州市 / `ENT_GEN_0093`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|前件类型不兼容|是|
|CORE_COL_EVAL_047|国家电网和广州市推进试点，双方将公布安排。|双方|国家电网 / `ENT_ENERGY_0001`；广州市 / `ENT_GEN_0093`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|前件类型不兼容|是|
|CORE_COL_EVAL_048|三峡集团及广州市举办论坛，这些机构发布议程。|这些机构|三峡集团 / `ENT_ENERGY_0008`；广州市 / `ENT_GEN_0093`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|前件类型不兼容|是|
|CORE_COL_EVAL_049|百度与广州市举办招聘活动，两家机构公布流程。|两家机构|百度 / `ENT_GEN_0070`；广州市 / `ENT_GEN_0093`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|前件类型不兼容|是|
|CORE_COL_EVAL_050|甲机构和乙机构发布联合声明，这些机构将持续合作。|这些机构|甲机构 / `未链接`；乙机构 / `未链接`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|前件未链接到运行知识库|否|
|CORE_COL_EVAL_051|甲机构及乙机构召开会议，双方将签署备忘录。|双方|甲机构 / `未链接`；乙机构 / `未链接`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|前件未链接到运行知识库|否|
|CORE_COL_EVAL_052|甲机构以及乙机构完成评审，两家机构将公布结论。|两家机构|甲机构 / `未链接`；乙机构 / `未链接`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|前件未链接到运行知识库|否|
|CORE_COL_EVAL_053|国家电网和国家电网共同发布通知，双方将更新计划。|双方|国家电网 / `ENT_ENERGY_0001`；国家电网 / `ENT_ENERGY_0001`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|去重后只有一个实体 ID|是|
|CORE_COL_EVAL_054|华为与华为联合展示产品，两家公司将继续合作。|两家公司|华为 / `ENT_GEN_0051`；华为 / `ENT_GEN_0051`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|去重后只有一个实体 ID|是|
|CORE_COL_EVAL_055|国家电网发布公告，南方电网随后回应，双方继续沟通。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|前件之间不存在显式协调连接|是|
|CORE_COL_EVAL_056|华能集团发布计划，三峡集团随后跟进，这些企业共享信息。|这些企业|华能集团 / `ENT_ENERGY_0003`；三峡集团 / `ENT_ENERGY_0008`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|前件之间不存在显式协调连接|是|
|CORE_COL_EVAL_057|华为发布新品，腾讯随后评论，两家公司组织交流。|两家公司|华为 / `ENT_GEN_0051`；腾讯 / `ENT_GEN_0052`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|前件之间不存在显式协调连接|是|
|CORE_COL_EVAL_058|国家电网和南方电网公布联合计划，他将继续跟进。|他|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|单数人物代词不能回指机构集合|否|
|CORE_COL_EVAL_059|华能集团及三峡集团启动项目，她将负责协调。|她|华能集团 / `ENT_ENERGY_0003`；三峡集团 / `ENT_ENERGY_0008`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|单数人物代词不能回指机构集合|否|
|CORE_COL_EVAL_060|华为与腾讯发布声明，他将安排测试。|他|华为 / `ENT_GEN_0051`；腾讯 / `ENT_GEN_0052`|`[]`|是|未标注|未标注（历史元数据）|acceptance_main（历史元数据）|单数人物代词不能回指机构集合|否|
|CORE_COL_EVAL_061|国家电网及南方电网联合发布调度方案，双方将同步建设平台。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`|否|step2_two_org_ji|medium|acceptance_main|“双方”回指由“及”连接的两个已链接 ORG 前件。|否|
|CORE_COL_EVAL_062|华能集团以及三峡集团推进水电协同，二者将共享运行数据。|二者|华能集团 / `ENT_ENERGY_0003`；三峡集团 / `ENT_ENERGY_0008`|`ENT_ENERGY_0003`、`ENT_ENERGY_0008`|否|step2_two_org_yiji|medium|acceptance_main|“二者”回指由“以及”连接的两个已链接 ORG 前件。|否|
|CORE_COL_EVAL_063|国家电网、南方电网及华能集团共同制定保供计划，多家企业将协同落实。|多家企业|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`；华能集团 / `ENT_ENERGY_0003`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`、`ENT_ENERGY_0003`|否|step2_three_org_mixed|hard|acceptance_main|三实体通过顿号和“及”形成明确协调组。|否|
|CORE_COL_EVAL_064|国家电网、南方电网及华能集团以及三峡集团成立工作组，多家企业将轮流牵头。|多家企业|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`；华能集团 / `ENT_ENERGY_0003`；三峡集团 / `ENT_ENERGY_0008`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`、`ENT_ENERGY_0003`、`ENT_ENERGY_0008`|否|step2_four_org_mixed|hard|acceptance_main|四个已链接 ORG 由连续显式连接词构成同一集合。|否|
|CORE_COL_EVAL_065|国家电网和南方电网在历经三个月协商后于北京签署协议，双方将共同推进工程。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`|否|step2_inserted_modifier|medium|acceptance_main|时间、地点插入不改变“和”连接的两个前件。|否|
|CORE_COL_EVAL_066|国家电网和南方电网负责输电，华为与百度负责平台建设，双方将完成系统联调。|双方|华为 / `ENT_GEN_0051`；百度 / `ENT_GEN_0070`|`ENT_GEN_0051`、`ENT_GEN_0070`|否|step2_nearest_coordination_group|hard|acceptance_main|存在两个协调组时，按当前标注规范回指最近的“华为与百度”。|否|
|CORE_COL_EVAL_067|三峡集团与广州市共同举办论坛，双方公布后续安排。|双方|三峡集团 / `ENT_ENERGY_0008`；广州市 / `ENT_GEN_0093`|`[]`|是|step2_type_conflict_nil|medium|acceptance_main|ORG 与 GPE 不能组成同质集合|是|
|CORE_COL_EVAL_068|国家电网和南方电网发布联合公告，她将继续跟进。|她|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`[]`|是|step2_single_pronoun_nil|easy|acceptance_main|单数人物代词不能回指机构集合|否|
|CORE_COL_EVAL_069|国家电网和国家电网共同发布通知，双方将更新计划。|双方|国家电网 / `ENT_ENERGY_0001`；国家电网 / `ENT_ENERGY_0001`|`[]`|是|step2_duplicate_entity_id_nil|medium|acceptance_main|去重后仅剩一个实体 ID|是|
|CORE_COL_EVAL_070|甲机构及乙机构召开会议，双方将签署备忘录。|双方|甲机构 / `未链接`；乙机构 / `未链接`|`[]`|是|step2_unlinked_antecedents_nil|medium|acceptance_main|前件未链接到运行知识库|否|
|CORE_COL_EVAL_071|国家电网与南方电网召开会议。会议讨论了多个议题。双方最终签署备忘录。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`|否|blind_cross_two_sentences|hard|challenge_dev|语义上“双方”回指首句两个机构；用于检验跨两句集合能力。|是|
|CORE_COL_EVAL_072|国家电网与南方电网发布联合计划。华为随后提出技术方案。双方将共同建设调度平台。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`；华为 / `ENT_GEN_0051`|`[]`|是|blind_subject_switch_nil|hard|challenge_dev|主体切换后“双方”缺少可唯一确定的集合前件|是|
|CORE_COL_EVAL_073|国家电网同南方电网共同推进项目，双方将建立联络机制。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`|否|blind_same_as_conjunction|hard|challenge_dev|“同”在自然语义中连接两个机构；用于检验未覆盖连接方式。|是|
|CORE_COL_EVAL_074|微信和腾讯会议联合升级协作功能，它们将同步开放测试。|它们|微信 / `ENT_GEN_0061`；腾讯会议 / `ENT_GEN_0104`|`ENT_GEN_0061`、`ENT_GEN_0104`|否|blind_product_collective|hard|challenge_dev|两个运行知识库产品在语义上构成集合；用于检验非 ORG/PERSON 集合。|是|
|CORE_COL_EVAL_075|国家电网和南方电网发布联合计划，她们随后公布细则。|她们|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`[]`|是|blind_female_pronoun_type_conflict_nil|hard|challenge_dev|运行知识库无可用女性 PERSON 前件，机构集合不应由“她们”回指|是|
|CORE_COL_EVAL_076|国家电网及大唐集团联合开展保供演练，双方将共享调度方案。|双方|国家电网 / `ENT_ENERGY_0001`；大唐集团 / `ENT_ENERGY_0004`|`ENT_ENERGY_0001`、`ENT_ENERGY_0004`|否|step3_energy_ji|medium|acceptance_main|能源机构由“及”连接，双方回指两个运行 KB 前件。|否|
|CORE_COL_EVAL_077|国家电网以及国家电投共同发布储能倡议，二者将建立联络机制。|二者|国家电网 / `ENT_ENERGY_0001`；国家电投 / `ENT_ENERGY_0006`|`ENT_ENERGY_0001`、`ENT_ENERGY_0006`|否|step3_energy_yiji|medium|acceptance_main|两个能源机构由“以及”构成协调组。|否|
|CORE_COL_EVAL_078|中国移动及中国电信推进算网协同，两家公司将开放试验环境。|两家公司|中国移动 / `ENT_GEN_0102`；中国电信 / `ENT_GEN_0103`|`ENT_GEN_0102`、`ENT_GEN_0103`|否|step3_telecom_ji|medium|acceptance_main|两个通信企业形成明确同句集合。|否|
|CORE_COL_EVAL_079|新华社以及中央广电总台共同报道论坛，这些机构将共享采编资源。|这些机构|新华社 / `ENT_GEN_0115`；中央广电总台 / `ENT_GEN_0116`|`ENT_GEN_0115`、`ENT_GEN_0116`|否|step3_media_yiji|medium|acceptance_main|媒体机构由“以及”连接。|否|
|CORE_COL_EVAL_080|国铁集团及南方航空优化联运服务，双方将统一换乘指引。|双方|国铁集团 / `ENT_GEN_0113`；南方航空 / `ENT_GEN_0114`|`ENT_GEN_0113`、`ENT_GEN_0114`|否|step3_transport_ji|medium|acceptance_main|交通机构形成双主体集合。|否|
|CORE_COL_EVAL_081|工商银行及建设银行推出绿色信贷方案，两家机构将交流风控经验。|两家机构|工商银行 / `ENT_GEN_0055`；建设银行 / `ENT_GEN_0081`|`ENT_GEN_0055`、`ENT_GEN_0081`|否|step3_finance_ji|medium|acceptance_main|金融机构由“及”连接。|否|
|CORE_COL_EVAL_082|中日友好医院及瑞金医院开展远程会诊，这些机构将共享病例规范。|这些机构|中日友好医院 / `ENT_GEN_0111`；瑞金医院 / `ENT_GEN_0112`|`ENT_GEN_0111`、`ENT_GEN_0112`|否|step3_medical_ji|medium|acceptance_main|两个医疗机构是同句已链接前件。|否|
|CORE_COL_EVAL_083|清华大学及浙江大学联合举办课程，两所高校将共同组织答辩。|两所高校|清华大学 / `ENT_GEN_0060`；浙江大学 / `ENT_GEN_0066`|`ENT_GEN_0060`、`ENT_GEN_0066`|否|step3_university_ji|medium|acceptance_main|高校前件由“及”连接。|否|
|CORE_COL_EVAL_084|华为与阿里巴巴联合发布安全规范，双方将组织开发者测试。|双方|华为 / `ENT_GEN_0051`；阿里巴巴 / `ENT_GEN_0053`|`ENT_GEN_0051`、`ENT_GEN_0053`|否|step3_tech_yu|medium|acceptance_main|科技企业同句显式并列。|否|
|CORE_COL_EVAL_085|比亚迪和宁德时代签署电池合作协议，两家企业将公布兼容标准。|两家企业|比亚迪 / `ENT_ENERGY_0016`；宁德时代 / `ENT_ENERGY_0015`|`ENT_ENERGY_0016`、`ENT_ENERGY_0015`|否|step3_new_energy_and|medium|acceptance_main|新能源企业由“和”连接。|否|
|CORE_COL_EVAL_086|国家能源局与国家发展改革委召开专题会议，双方将分别推进实施细则。|双方|国家能源局 / `ENT_GEN_0059`；国家发展改革委 / `ENT_GEN_0089`|`ENT_GEN_0059`、`ENT_GEN_0089`|否|step3_government_yu|medium|acceptance_main|两个政府机构形成协调组。|否|
|CORE_COL_EVAL_087|工业和信息化部与生态环境部会商绿色制造，二者将联合发布指南。|二者|工业和信息化部 / `ENT_GEN_0090`；生态环境部 / `ENT_GEN_0091`|`ENT_GEN_0090`、`ENT_GEN_0091`|否|step3_government_yu_two|medium|acceptance_main|“二者”回指同句两个机构。|否|
|CORE_COL_EVAL_088|人民日报社和中国日报社共同策划专题报道，这些机构将共享采访线索。|这些机构|人民日报社 / `ENT_GEN_0139`；中国日报社 / `ENT_GEN_0153`|`ENT_GEN_0139`、`ENT_GEN_0153`|否|step3_media_and|medium|acceptance_main|新闻机构的集合回指。|否|
|CORE_COL_EVAL_089|国网江苏电力与广东电网开展跨省交易试点，两家机构将对接结算规则。|两家机构|国网江苏电力 / `ENT_GEN_0124`；广东电网 / `ENT_GEN_0125`|`ENT_GEN_0124`、`ENT_GEN_0125`|否|step3_regional_grid_yu|hard|acceptance_main|区域电网机构形成同质集合。|否|
|CORE_COL_EVAL_090|北京天坛医院和邵逸夫医院联合制定转诊流程，双方将共享培训材料。|双方|北京天坛医院 / `ENT_GEN_0147`；邵逸夫医院 / `ENT_GEN_0148`|`ENT_GEN_0147`、`ENT_GEN_0148`|否|step3_medical_and|medium|acceptance_main|医疗机构同句显式协调。|否|
|CORE_COL_EVAL_091|国家电网、南方电网、大唐集团及国家电投共同发布保供方案，多家企业将同步落实。|多家企业|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`；大唐集团 / `ENT_ENERGY_0004`；国家电投 / `ENT_ENERGY_0006`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`、`ENT_ENERGY_0004`、`ENT_ENERGY_0006`|否|step3_four_energy|hard|acceptance_main|四个能源机构形成连续协调组。|否|
|CORE_COL_EVAL_092|华为、腾讯及阿里巴巴联合建设开源社区，多家企业将维护基础设施。|多家企业|华为 / `ENT_GEN_0051`；腾讯 / `ENT_GEN_0052`；阿里巴巴 / `ENT_GEN_0053`|`ENT_GEN_0051`、`ENT_GEN_0052`、`ENT_GEN_0053`|否|step3_three_tech|hard|acceptance_main|三个科技企业形成集合。|否|
|CORE_COL_EVAL_093|工商银行、建设银行及中国银行共同发布报告，多家机构将完善绿色金融服务。|多家机构|工商银行 / `ENT_GEN_0055`；建设银行 / `ENT_GEN_0081`；中国银行 / `ENT_GEN_0083`|`ENT_GEN_0055`、`ENT_GEN_0081`、`ENT_GEN_0083`|否|step3_three_finance|hard|acceptance_main|三个金融机构由连续连接词组成集合。|否|
|CORE_COL_EVAL_094|清华大学、北京大学及浙江大学共建课程平台，这些机构将共享实验资源。|这些机构|清华大学 / `ENT_GEN_0060`；北京大学 / `ENT_GEN_0064`；浙江大学 / `ENT_GEN_0066`|`ENT_GEN_0060`、`ENT_GEN_0064`、`ENT_GEN_0066`|否|step3_three_university|hard|acceptance_main|三个高校实体在同句形成协调组。|否|
|CORE_COL_EVAL_095|国铁集团、南方航空及中国国航共同优化出行服务，多家机构将发布联运规则。|多家机构|国铁集团 / `ENT_GEN_0113`；南方航空 / `ENT_GEN_0114`；中国国航 / `ENT_GEN_0135`|`ENT_GEN_0113`、`ENT_GEN_0114`、`ENT_GEN_0135`|否|step3_three_transport|hard|acceptance_main|三个交通机构形成同句集合。|否|
|CORE_COL_EVAL_096|国家能源局和国家发展改革委在多轮论证后于北京签署备忘录，双方将建立项目台账。|双方|国家能源局 / `ENT_GEN_0059`；国家发展改革委 / `ENT_GEN_0089`|`ENT_GEN_0059`、`ENT_GEN_0089`|否|step3_long_insertion|hard|acceptance_main|长插入语不影响显式协调关系。|否|
|CORE_COL_EVAL_097|电力规划设计总院与中国电力科学研究院共同评审方案，上述机构将发布技术意见。|上述机构|电力规划设计总院 / `ENT_ENERGY_0049`；中国电力科学研究院 / `ENT_ENERGY_0050`|`ENT_ENERGY_0049`、`ENT_ENERGY_0050`|否|step3_research_yu|medium|acceptance_main|研究机构集合由“与”连接。|否|
|CORE_COL_EVAL_098|国家电网和南方电网负责输电，工商银行与建设银行负责融资，双方将先完成授信评审。|双方|工商银行 / `ENT_GEN_0055`；建设银行 / `ENT_GEN_0081`|`ENT_GEN_0055`、`ENT_GEN_0081`|否|step3_multi_group_finance_nearest|hard|acceptance_main|两组协调结构中，“双方”回指最近的金融机构组。|是|
|CORE_COL_EVAL_099|华为与腾讯推进平台建设，新华社和中央广电总台负责传播，双方将联合发布报道。|双方|新华社 / `ENT_GEN_0115`；中央广电总台 / `ENT_GEN_0116`|`ENT_GEN_0115`、`ENT_GEN_0116`|否|step3_multi_group_media_nearest|hard|acceptance_main|最近协调组为两个媒体机构。|是|
|CORE_COL_EVAL_100|清华大学及北京大学完成课程设计，浙江大学与复旦大学负责试点，二者将同步反馈结果。|二者|浙江大学 / `ENT_GEN_0066`；复旦大学 / `ENT_GEN_0067`|`ENT_GEN_0066`、`ENT_GEN_0067`|否|step3_multi_group_university_nearest|hard|acceptance_main|“二者”回指最近的高校协调组。|是|
|CORE_COL_EVAL_101|国家电网、南方电网及三峡集团完成联合演练，上述企业将复盘处置流程。|上述企业|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`；三峡集团 / `ENT_ENERGY_0008`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`、`ENT_ENERGY_0008`|否|step3_three_energy_above|hard|acceptance_main|三个能源机构由“上述企业”集合回指。|否|
|CORE_COL_EVAL_102|中国移动和中国电信发布协同计划，这些企业将共同开放边缘节点。|这些企业|中国移动 / `ENT_GEN_0102`；中国电信 / `ENT_GEN_0103`|`ENT_GEN_0102`、`ENT_GEN_0103`|否|step3_telecom_and|medium|acceptance_main|通信企业集合回指。|否|
|CORE_COL_EVAL_103|华能集团及大唐集团启动机组检修，两家公司将统一排期。|两家公司|华能集团 / `ENT_ENERGY_0003`；大唐集团 / `ENT_ENERGY_0004`|`ENT_ENERGY_0003`、`ENT_ENERGY_0004`|否|step3_generator_ji|medium|acceptance_main|两个能源企业由“及”连接。|否|
|CORE_COL_EVAL_104|国家电网和微信共同发布工具说明，双方将安排培训。|双方|国家电网 / `ENT_ENERGY_0001`；微信 / `ENT_GEN_0061`|`[]`|是|step3_org_product_conflict_nil|hard|acceptance_main|ORG 与产品类型不兼容|是|
|CORE_COL_EVAL_105|甲机构和乙机构分别说明进展，双方将继续沟通。|双方|甲机构 / `未链接`；乙机构 / `未链接`|`[]`|是|step3_unlinked_both_nil|medium|acceptance_main|两个前件均未链接到运行知识库|否|
|CORE_COL_EVAL_106|国家电网和南方电网签署协议。双方随后公布实施方案。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`|否|blind_cross_adjacent|hard|challenge_dev|语义上“双方”跨句回指两个电网机构。|是|
|CORE_COL_EVAL_107|华能集团与三峡集团召开会议。会议由主持人说明议程。双方最终确定调度机制。|双方|华能集团 / `ENT_ENERGY_0003`；三峡集团 / `ENT_ENERGY_0008`|`ENT_ENERGY_0003`、`ENT_ENERGY_0008`|否|blind_cross_with_intervening_entity|hard|challenge_dev|中间插入句子不应改变语义上的原协调组。|是|
|CORE_COL_EVAL_108|中国移动跟中国电信共同开展测试，双方将公布结果。|双方|中国移动 / `ENT_GEN_0102`；中国电信 / `ENT_GEN_0103`|`ENT_GEN_0102`、`ENT_GEN_0103`|否|blind_gen_conjunction|hard|challenge_dev|“跟”自然连接两个机构，但当前规则尚未覆盖。|是|
|CORE_COL_EVAL_109|国家电网连同南方电网推进改造工程，两家机构将共同验收。|两家机构|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`|否|blind_liantong_conjunction|hard|challenge_dev|“连同”表达联合参与，用于盲测连接词覆盖。|是|
|CORE_COL_EVAL_110|国家能源局会同国家发展改革委发布通知，双方将督促落实。|双方|国家能源局 / `ENT_GEN_0059`；国家发展改革委 / `ENT_GEN_0089`|`ENT_GEN_0059`、`ENT_GEN_0089`|否|blind_huitong_conjunction|hard|challenge_dev|“会同”表达联合行动，用于盲测连接词覆盖。|是|
|CORE_COL_EVAL_111|国家电网、南方电网及华能集团共同参会，各方将提交实施清单。|各方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`；华能集团 / `ENT_ENERGY_0003`|`ENT_ENERGY_0001`、`ENT_ENERGY_0002`、`ENT_ENERGY_0003`|否|blind_all_parties|hard|challenge_dev|“各方”语义上回指三个明确参与主体。|是|
|CORE_COL_EVAL_112|华为、腾讯及百度联合成立实验室，三方将共同管理成果。|三方|华为 / `ENT_GEN_0051`；腾讯 / `ENT_GEN_0052`；百度 / `ENT_GEN_0070`|`ENT_GEN_0051`、`ENT_GEN_0052`、`ENT_GEN_0070`|否|blind_three_parties|hard|challenge_dev|“三方”语义上回指三个科技企业。|是|
|CORE_COL_EVAL_113|清华大学与北京大学共同建设课程平台，两者将开放教学资源。|两者|清华大学 / `ENT_GEN_0060`；北京大学 / `ENT_GEN_0064`|`ENT_GEN_0060`、`ENT_GEN_0064`|否|blind_liangzhe|hard|challenge_dev|“两者”语义上回指两个高校。|是|
|CORE_COL_EVAL_114|新华社和中央广电总台联合采访，该二者将共享素材。|该二者|新华社 / `ENT_GEN_0115`；中央广电总台 / `ENT_GEN_0116`|`ENT_GEN_0115`、`ENT_GEN_0116`|否|blind_the_two|hard|challenge_dev|“该二者”语义上回指两个媒体机构。|是|
|CORE_COL_EVAL_115|工商银行及建设银行联合发布报告，上述单位将说明风险控制措施。|上述单位|工商银行 / `ENT_GEN_0055`；建设银行 / `ENT_GEN_0081`|`ENT_GEN_0055`、`ENT_GEN_0081`|否|blind_above_units|hard|challenge_dev|“上述单位”语义上回指两个金融机构。|是|
|CORE_COL_EVAL_116|国家电网与南方电网发布联合计划。华为随后单独提出技术方案。双方将建设平台。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`；华为 / `ENT_GEN_0051`|`[]`|是|blind_subject_switch_second_nil|hard|challenge_dev|主体切换后集合前件不唯一|是|
|CORE_COL_EVAL_117|华为和支付宝联合发布活动说明，双方将开放报名。|双方|华为 / `ENT_GEN_0051`；支付宝 / `ENT_GEN_0097`|`[]`|是|blind_org_platform_conflict_nil|hard|challenge_dev|ORG 与软件平台类型不兼容|是|
|CORE_COL_EVAL_118|甲机构及乙机构宣布合作，双方将建立协调组。|双方|甲机构 / `未链接`；乙机构 / `未链接`|`[]`|是|blind_unlinked_nil|hard|challenge_dev|前件均未链接到运行知识库|是|
|CORE_COL_EVAL_119|国家电网和国家电网联合发布通知，双方将共同实施。|双方|国家电网 / `ENT_ENERGY_0001`；国家电网 / `ENT_ENERGY_0001`|`[]`|是|blind_duplicate_id_nil|hard|challenge_dev|去重后只有一个有效实体 ID|是|
|CORE_COL_EVAL_120|国家电网发布公告，南方电网随后回应，双方将继续沟通。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`[]`|是|blind_no_coordination_nil|hard|challenge_dev|前件之间没有显式协调连接|是|
|CORE_COL_EVAL_121|国家电网和南方电网发布方案，三方将继续磋商。|三方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`[]`|是|blind_cardinality_mismatch_nil|hard|challenge_dev|集合代词数量与两个前件不匹配|是|
|CORE_COL_EVAL_122|国家电网和南方电网完成签约。双方随后公布细则。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`[]`|是|blind_cross_sentence_nil|hard|challenge_dev|跨句隐式集合不在当前规则支持范围|是|
|CORE_COL_EVAL_123|国家电网和南方电网负责输电，华为与腾讯负责平台，双方将在年内验收。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`；华为 / `ENT_GEN_0051`；腾讯 / `ENT_GEN_0052`|`[]`|是|blind_multi_group_ambiguous_nil|hard|challenge_dev|两个协调组均可能被“双方”指代，缺少语义限定|是|
|CORE_COL_EVAL_124|国家电网和南方电网发布联合计划，她们随后公布细则。|她们|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`[]`|是|blind_female_org_conflict_nil|hard|challenge_dev|机构前件与女性 PERSON 集合代词类型不兼容|是|
|CORE_COL_EVAL_125|国家电网与南方电网召开会议。会议记录已经归档。相关部门完成审查。双方将启动项目。|双方|国家电网 / `ENT_ENERGY_0001`；南方电网 / `ENT_ENERGY_0002`|`[]`|是|blind_long_distance_nil|hard|challenge_dev|跨越多个句子的隐式集合不在当前规则支持范围|是|

## 3. 复核结论与待关注边界

1. 正例均使用运行知识库实体 ID；质量审计负责验证 ID、偏移、集合去重和索引合法性。
2. 盲测中的失败或边界结果必须保留，不能为了提高总体指标调整其 gold。
3. 当前规则主要保证同句显式并列的 ORG/PERSON 集合；跨句、未覆盖连接词、非 ORG/PERSON 集合、主体切换和复杂省略是优先人工复核范围。
4. 运行知识库缺少可用 PERSON 实体，`她们`相关样本仅作为类型/知识库覆盖边界，不宣称 PERSON 集合正例能力。
