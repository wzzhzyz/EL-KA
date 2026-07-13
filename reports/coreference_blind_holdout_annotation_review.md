# Blind Holdout 标注复核清单

## 复核口径

- 数据集在 P0 规则冻结后建立，`used_for_rule_development=false`。
- 全部 25 条已完成单人初审：字段、偏移、运行 KB ID、gold 与场景说明均已核对。
- **single-review limitation**：当前无法取得独立第二位标注者复核；所有 `hard` 样本标为“待独立二次复核”，不得伪称双人复核。

|Sample ID|文本|目标指代|Gold `entity_ids`|Gold NIL|场景|难度|标注依据|复核状态|复核备注|
|-|-|-|-|-|-|-|-|-|-|
|CORE_BLIND_HOLDOUT_001|国家能源局、国家发展改革委及工业和信息化部联合印发行动方案，三方将分别跟进落实。|三方|`ENT_GEN_0059`、`ENT_GEN_0089`、`ENT_GEN_0090`|否|holdout_three_government_group|hard|三个已链接政府机构由顿号和“及”组成唯一协调组。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_002|中国移动、华为和阿里巴巴共建云服务中心，这些企业将共享运维经验。|这些企业|`ENT_GEN_0102`、`ENT_GEN_0051`、`ENT_GEN_0053`|否|holdout_three_tech_group|hard|三个已链接企业通过连续显式连接词组成唯一协调组。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_003|国网江苏电力、广东电网及南方电网成立调度专班，各方将提交值守安排。|各方|`ENT_GEN_0124`、`ENT_GEN_0125`、`ENT_ENERGY_0002`|否|holdout_three_grid_group|hard|三个电网机构由顿号和“及”构成唯一同句协调组。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_004|人民日报社、新华社及中国日报社开设专题栏目，上述单位将统一发布稿件。|上述单位|`ENT_GEN_0139`、`ENT_GEN_0115`、`ENT_GEN_0153`|否|holdout_three_media_group|hard|三个媒体机构构成唯一明确协调组。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_005|比亚迪、宁德时代及华为举办技术论坛，三方将共同发布倡议。|三方|`ENT_ENERGY_0016`、`ENT_ENERGY_0015`、`ENT_GEN_0051`|否|holdout_three_industry_group|hard|三个已链接机构满足“三方”的精确数量约束。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_006|清华大学、浙江大学和上海交通大学共同编制课程标准，这些机构将互认学分。|这些机构|`ENT_GEN_0060`、`ENT_GEN_0066`、`ENT_GEN_0065`|否|holdout_three_university_group|medium|三个高校形成唯一同句协调组。|单人初审完成|已核对运行 KB 实体引用与字符偏移。|
|CORE_BLIND_HOLDOUT_007|国铁集团和南方航空先完成线路衔接。双方随后公布联运细则。|双方|`ENT_GEN_0113`、`ENT_GEN_0114`|否|holdout_cross_one_positive|hard|语义上后句“双方”回指前句唯一协调组。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_008|工商银行与建设银行达成服务协议。二者将在下月上线新流程。|二者|`ENT_GEN_0055`、`ENT_GEN_0081`|否|holdout_cross_one_pair_positive|hard|语义上后句“二者”回指前句唯一协调组。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_009|华能集团及三峡集团启动联合演练。会议纪要随后归档。双方将复盘演练结果。|双方|`ENT_ENERGY_0003`、`ENT_ENERGY_0008`|否|holdout_cross_two_positive|hard|中间事件说明不改变首句唯一协调组的语义连续性。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_010|人民日报社与新华社召开选题会。会议记录由秘书整理。双方将确认发布节奏。|双方|`ENT_GEN_0139`、`ENT_GEN_0115`|否|holdout_cross_two_media_positive|hard|中间无新的已链接主体，语义上保持首句协调组。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_011|华能集团与三峡集团在多轮技术论证和现场勘察后签署备忘录，双方将建立联合台账。|双方|`ENT_ENERGY_0003`、`ENT_ENERGY_0008`|否|holdout_non_adjacent_modifier|medium|长修饰成分不切断两个前件之间的显式“与”连接。|单人初审完成|已核对运行 KB 实体引用与字符偏移。|
|CORE_BLIND_HOLDOUT_012|国家电投会同大唐集团开展安全检查，双方将交换排查结果。|双方|`ENT_ENERGY_0006`、`ENT_ENERGY_0004`|否|holdout_huitong_group|medium|“会同”位于两个相邻已链接机构之间。|单人初审完成|已核对运行 KB 实体引用与字符偏移。|
|CORE_BLIND_HOLDOUT_013|中国移动跟中国电信联合测试新网络，两家公司将同步开放体验。|两家公司|`ENT_GEN_0102`、`ENT_GEN_0103`|否|holdout_gen_group|medium|“跟”连接两个同类已链接企业。|单人初审完成|已核对运行 KB 实体引用与字符偏移。|
|CORE_BLIND_HOLDOUT_014|工商银行连同建设银行推进支付互联，上述单位将公布服务说明。|上述单位|`ENT_GEN_0055`、`ENT_GEN_0081`|否|holdout_liantong_group|medium|“连同”连接两个同类已链接机构。|单人初审完成|已核对运行 KB 实体引用与字符偏移。|
|CORE_BLIND_HOLDOUT_015|微信和腾讯会议完善协同能力，它们将开放新版功能。|它们|`ENT_GEN_0061`、`ENT_GEN_0104`|否|holdout_product_collective_positive|hard|两个产品在语义上构成集合，用于检验非 ORG/PERSON 范围。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_016|国家能源局和国家发展改革委在项目评审中形成共识，双方将共同督办。|双方|`ENT_GEN_0059`、`ENT_GEN_0089`|否|holdout_government_pair|medium|两个政府机构构成唯一同句协调组。|单人初审完成|已核对运行 KB 实体引用与字符偏移。|
|CORE_BLIND_HOLDOUT_017|人民日报社和新华社发布联合通报，她们将于下午说明情况。|她们|`[]`|是|holdout_female_org_nil|hard|女性 PERSON 集合词不能安全回指 ORG 前件。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_018|微信与支付宝共同推出服务，双方将进行培训。|双方|`[]`|是|holdout_product_platform_mismatch_nil|hard|产品与软件平台混合，当前规则不应形成同质集合。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_019|国家电投和大唐集团负责设备，华为与阿里巴巴负责平台，双方将在季度末验收。|双方|`[]`|是|holdout_multi_group_ambiguous_nil|hard|两个合法协调组均可能被“双方”指代，缺少可靠语义限定。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_020|中国移动和中国移动共同发布公告，双方将安排说明会。|双方|`[]`|是|holdout_duplicate_entity_nil|medium|去重后仅有一个唯一实体 ID，不能构成集合。|单人初审完成|已核对运行 KB 实体引用与字符偏移。|
|CORE_BLIND_HOLDOUT_021|甲机构与乙机构联合举办活动，双方将发布安排。|双方|`[]`|是|holdout_unlinked_antecedents_nil|medium|两个前件未链接运行知识库，不能输出正式实体集合。|单人初审完成|已核对运行 KB 实体引用与字符偏移。|
|CORE_BLIND_HOLDOUT_022|国家能源局发布通知，国家发展改革委随后回应，双方将召开座谈会。|双方|`[]`|是|holdout_no_coordination_nil|hard|两个实体间没有显式协调连接，不能安全组成集合。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_023|国铁集团和南方航空启动联运项目，三方将持续跟进。|三方|`[]`|是|holdout_cardinality_nil|hard|仅有两个唯一实体，不满足“三方”的精确数量约束。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_024|国家电投与大唐集团先完成试运。项目随后由华为监督。双方将更新计划。|双方|`[]`|是|holdout_subject_switch_nil|hard|中间出现新的已链接主体，集合前件不再唯一。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
|CORE_BLIND_HOLDOUT_025|广东电网与国网江苏电力完成调度协商。双方将在下一阶段推进实施。|双方|`[]`|是|holdout_cross_sentence_nil|hard|跨句集合缺乏可验证的话语连续性信号，按保守策略返回 NIL。|单人初审完成；待独立二次复核|困难样本保留，不以规则预期改写 gold。|
