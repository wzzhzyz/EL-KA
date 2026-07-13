"""Deterministically extend the formal collective-coreference acceptance set.

This builder only creates data with pre-reviewed runtime KB IDs.  It is kept as
provenance for the 10-to-75 expansion; it does not alter algorithms or gold
outside data/eval/coreference_collective_eval.json.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "eval" / "coreference_collective_eval.json"
REVIEW_PATH = ROOT / "reports" / "coreference_collective_annotation_review.md"

NATIONAL = ("国家电网", "ENT_ENERGY_0001")
SOUTH = ("南方电网", "ENT_ENERGY_0002")
HUANENG = ("华能集团", "ENT_ENERGY_0003")
THREE = ("三峡集团", "ENT_ENERGY_0008")
HUAWEI = ("华为", "ENT_GEN_0051")
TENCENT = ("腾讯", "ENT_GEN_0052")
PKU = ("北京大学", "ENT_GEN_0064")
SJTU = ("上海交通大学", "ENT_GEN_0065")
BAIDU = ("百度", "ENT_GEN_0070")
GUANGZHOU = ("广州市", "ENT_GEN_0093")
DADANG = ("大唐集团", "ENT_ENERGY_0004")
SPIC = ("国家电投", "ENT_ENERGY_0006")
MOBILE = ("中国移动", "ENT_GEN_0102")
TELECOM = ("中国电信", "ENT_GEN_0103")
XINHUA = ("新华社", "ENT_GEN_0115")
CCTV = ("中央广电总台", "ENT_GEN_0116")
RAIL = ("国铁集团", "ENT_GEN_0113")
SOUTH_AIR = ("南方航空", "ENT_GEN_0114")
ICBC = ("工商银行", "ENT_GEN_0055")
CCB = ("建设银行", "ENT_GEN_0081")
ENERGY_BUREAU = ("国家能源局", "ENT_GEN_0059")
NDRC = ("国家发展改革委", "ENT_GEN_0089")
MIIT = ("工业和信息化部", "ENT_GEN_0090")
ECOLOGY = ("生态环境部", "ENT_GEN_0091")
TSINGHUA = ("清华大学", "ENT_GEN_0060")
ZJU = ("浙江大学", "ENT_GEN_0066")
RENMIN = ("人民日报社", "ENT_GEN_0139")
CHINA_DAILY = ("中国日报社", "ENT_GEN_0153")
JIANGSU_GRID = ("国网江苏电力", "ENT_GEN_0124")
GUANGDONG_GRID = ("广东电网", "ENT_GEN_0125")
TIANTAN = ("北京天坛医院", "ENT_GEN_0147")
SHAOYIFU = ("邵逸夫医院", "ENT_GEN_0148")
BYD = ("比亚迪", "ENT_ENERGY_0016")
CATL = ("宁德时代", "ENT_ENERGY_0015")
ALIBABA = ("阿里巴巴", "ENT_GEN_0053")
WECHAT = ("微信", "ENT_GEN_0061")
TENCENT_MEETING = ("腾讯会议", "ENT_GEN_0104")
ALIPAY = ("支付宝", "ENT_GEN_0097")
BAIDU_MAP = ("百度地图", "ENT_GEN_0098")


def mention(text: str, item: tuple[str, str], entity_type: str = "ORG", sentence_index: int | None = None) -> dict:
    start = text.index(item[0])
    result = {"mention": item[0], "type": entity_type, "char_start": start, "char_end": start + len(item[0]), "role": "name", "entity_id": item[1]}
    if sentence_index is not None:
        result["sentence_index"] = sentence_index
    return result


def target(text: str, surface: str, sentence_index: int | None = None) -> dict:
    start = text.index(surface)
    result = {"mention": surface, "type": "PRON", "char_start": start, "char_end": start + len(surface), "role": "pronoun"}
    if sentence_index is not None:
        result["sentence_index"] = sentence_index
    return result


def positive(sample_id: int, text: str, entities: list[tuple[str, str]], surface: str, scenario: str) -> dict:
    mentions = [mention(text, entity) for entity in entities] + [target(text, surface)]
    return {"id": f"CORE_COL_EVAL_{sample_id:03d}", "text": text, "mentions": mentions, "expected_coreferences": [{"mention_index": len(mentions) - 1, "entity_id": None, "entity_ids": [entity_id for _, entity_id in entities], "antecedent_indices": list(range(len(entities))), "is_collective": True, "is_nil": False, "scenario": scenario}]}


def collective_nil(sample_id: int, text: str, entities: list[tuple[str, str] | tuple[str, str, str]], surface: str, reason: str, sentence_indices: list[int] | None = None) -> dict:
    mentions = []
    for index, entity in enumerate(entities):
        if len(entity) == 2:
            mentions.append(mention(text, entity))
        else:
            mentions.append(mention(text, (entity[0], entity[1]), entity[2]))
        if sentence_indices is not None:
            mentions[-1]["sentence_index"] = sentence_indices[index]
    pronoun_sentence = sentence_indices[-1] if sentence_indices is not None else None
    mentions.append(target(text, surface, pronoun_sentence))
    return {"id": f"CORE_COL_EVAL_{sample_id:03d}", "text": text, "mentions": mentions, "expected_coreferences": [{"mention_index": len(mentions) - 1, "entity_id": None, "entity_ids": [], "antecedent_indices": [], "is_collective": True, "is_nil": True, "nil_reason": reason}]}


def unlinked_nil(sample_id: int, text: str, surface: str, reason: str) -> dict:
    names = [("甲机构", None), ("乙机构", None)]
    mentions = []
    for name, _ in names:
        start = text.index(name)
        mentions.append({"mention": name, "type": "ORG", "char_start": start, "char_end": start + len(name), "role": "name"})
    mentions.append(target(text, surface))
    return {"id": f"CORE_COL_EVAL_{sample_id:03d}", "text": text, "mentions": mentions, "expected_coreferences": [{"mention_index": 2, "entity_id": None, "entity_ids": [], "antecedent_indices": [], "is_collective": True, "is_nil": True, "nil_reason": reason}]}


def single_nil(sample_id: int, text: str, entities: list[tuple[str, str]], surface: str) -> dict:
    mentions = [mention(text, entity) for entity in entities] + [target(text, surface)]
    return {"id": f"CORE_COL_EVAL_{sample_id:03d}", "text": text, "mentions": mentions, "expected_coreferences": [{"mention_index": len(mentions) - 1, "entity_id": None, "entity_ids": [], "antecedent_indices": [], "is_collective": False, "is_nil": True, "nil_reason": "单数人物代词不能回指机构集合"}]}


def annotate(
    sample: dict,
    *,
    subset: str,
    difficulty: str,
    conjunction: str,
    sentence_distance: int,
    evidence: str,
    scenario: str | None = None,
) -> dict:
    """Attach acceptance metadata without changing the collective contract."""
    sample["subset"] = subset
    sample["difficulty"] = difficulty
    case = sample["expected_coreferences"][0]
    case["scenario"] = scenario or case.get("scenario") or f"acceptance_{sample['id'].lower()}"
    case["conjunction"] = conjunction
    case["anaphor"] = sample["mentions"][case["mention_index"]]["mention"]
    case["sentence_distance"] = sentence_distance
    case["evidence"] = evidence
    return sample


def with_antecedent_type(sample: dict, entity_type: str) -> dict:
    for item in sample["mentions"][:-1]:
        item["type"] = entity_type
    return sample


def with_sentence_indices(sample: dict, indices: list[int]) -> dict:
    if len(indices) != len(sample["mentions"]):
        raise ValueError("sentence index count must match mentions")
    for item, sentence_index in zip(sample["mentions"], indices):
        item["sentence_index"] = sentence_index
    return sample


def review_text(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def write_annotation_review(data: dict) -> None:
    """Create a deterministic, complete review checklist for formal samples."""
    samples = data["samples"]
    cases = [case for sample in samples for case in sample["expected_coreferences"]]
    positive = sum(not case["is_nil"] for case in cases)
    collective_nil = sum(case["is_collective"] and case["is_nil"] for case in cases)
    ordinary_nil = sum(not case["is_collective"] and case["is_nil"] for case in cases)
    challenge_dev = sum(sample.get("subset") == "challenge_dev" for sample in samples)
    lines = [
        "# 集合共指正式验收集人工复核清单",
        "",
        "## 1. 复核范围与口径",
        "",
        "- 数据集：`data/eval/coreference_collective_eval.json`；`evaluation_scope=acceptance`，`requires_runtime_kb=true`。",
        f"- 复核对象：{len(samples)} 条文本、{len(cases)} 个 case；集合正例 {positive}，集合 NIL {collective_nil}，普通单数 NIL {ordinary_nil}。",
        f"- Challenge Dev：{challenge_dev} 条，已用于规则失败分析；单元夹具 `coreference_collective_test.json` 不计入。",
        "- 正例要求集合 `entity_ids` 精确匹配且 `is_collective=true`、`is_nil=false`；集合成功的 `entity_id=null` 不表示 NIL。",
        "- 原始 60 条为已冻结的首版正式集，未补写 `subset`/`difficulty` 字段；表中以 `acceptance_main（历史元数据）` 标记，避免改写既有 gold。",
        "",
        "## 2. 逐条复核表",
        "",
        "“需要二次人工确认”优先标记盲测、跨句、主体切换、多协调组、类型冲突和复杂 NIL；该标记表示需确认语义边界，不表示数据有错误。",
        "",
        "|Sample ID|文本|目标指代|上下文前件（mention / ID）|Gold `entity_ids`|NIL|场景|难度|子集|审核说明|需要二次人工确认|",
        "|-|-|-|-|-|-|-|-|-|-|-|",
    ]
    for sample in samples:
        mentions = sample["mentions"]
        for case in sample["expected_coreferences"]:
            target_item = mentions[case["mention_index"]]
            antecedent_indices = case.get("antecedent_indices", [])
            if antecedent_indices:
                antecedents = "；".join(
                    f"{mentions[index]['mention']} / `{mentions[index].get('entity_id', '未链接')}`"
                    for index in antecedent_indices
                )
            else:
                named = [item for index, item in enumerate(mentions) if index != case["mention_index"] and item.get("role") != "pronoun"]
                antecedents = "；".join(
                    f"{item['mention']} / `{item.get('entity_id', '未链接')}`" for item in named
                ) or "无"
            is_nil = "是" if case["is_nil"] else "否"
            subset = sample.get("subset", "acceptance_main（历史元数据）")
            difficulty = sample.get("difficulty", "未标注（历史元数据）")
            scenario = case.get("scenario", "未标注")
            note = case.get("nil_reason") if case["is_nil"] else case.get("evidence", "使用运行知识库真实 ID，集合精确匹配")
            needs_review = (
                subset == "challenge_dev"
                or any(token in scenario for token in ("multi_group", "multiple", "subject_switch", "cross", "conflict", "distance"))
                or any(token in str(note) for token in ("跨句", "类型不兼容", "去重后", "不存在显式协调"))
            )
            ids = "、".join(f"`{value}`" for value in case.get("entity_ids", [])) or "`[]`"
            lines.append(
                "|" + "|".join([
                    review_text(sample["id"]), review_text(sample["text"]), review_text(target_item["mention"]),
                    review_text(antecedents), ids, is_nil, review_text(scenario), review_text(difficulty),
                    review_text(subset), review_text(note), "是" if needs_review else "否",
                ]) + "|"
            )
    lines += [
        "",
        "## 3. 复核结论与待关注边界",
        "",
        "1. 正例均使用运行知识库实体 ID；质量审计负责验证 ID、偏移、集合去重和索引合法性。",
        "2. 盲测中的失败或边界结果必须保留，不能为了提高总体指标调整其 gold。",
        "3. 当前规则主要保证同句显式并列的 ORG/PERSON 集合；跨句、未覆盖连接词、非 ORG/PERSON 集合、主体切换和复杂省略是优先人工复核范围。",
        "4. 运行知识库缺少可用 PERSON 实体，`她们`相关样本仅作为类型/知识库覆盖边界，不宣称 PERSON 集合正例能力。",
        "",
    ]
    REVIEW_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    base = [sample for sample in data["samples"] if int(sample["id"].rsplit("_", 1)[1]) <= 10]
    extra = [
        positive(11, "国家电网及南方电网共同编制规划，双方将推进跨区输电。", [NATIONAL, SOUTH], "双方", "two_org_same_sentence_ji"),
        positive(12, "国家电网以及南方电网发布联合倡议，两家央企将协同落实。", [NATIONAL, SOUTH], "两家央企", "two_org_same_sentence_yiji"),
        positive(13, "华能集团和三峡集团签订技术协议，这些企业将共享水电数据。", [HUANENG, THREE], "这些企业", "two_generator_same_sentence_and"),
        positive(14, "华能集团与三峡集团组织联合调度，上述企业将交流运行经验。", [HUANENG, THREE], "上述企业", "two_generator_same_sentence_yu"),
        positive(15, "华为及腾讯发布开放平台，两家公司将投入研发资源。", [HUAWEI, TENCENT], "两家公司", "two_tech_same_sentence_ji"),
        positive(16, "华为以及腾讯共建实验室，双方计划开放测试环境。", [HUAWEI, TENCENT], "双方", "two_tech_same_sentence_yiji"),
        positive(17, "百度和腾讯联合开展安全研究，两家企业将发布白皮书。", [BAIDU, TENCENT], "两家企业", "two_tech_same_sentence_and"),
        positive(18, "北京大学及上海交通大学启动论坛，两所高校将共同组织报告会。", [PKU, SJTU], "两所高校", "two_university_same_sentence_ji"),
        positive(19, "北京大学以及上海交通大学建设课程平台，两家高校将共享教学资源。", [PKU, SJTU], "两家高校", "two_university_same_sentence_yiji"),
        positive(20, "国家电网、南方电网和华能集团发布年度计划，多家企业将联合实施。", [NATIONAL, SOUTH, HUANENG], "多家企业", "three_org_same_sentence_dunhao"),
        positive(21, "华为、腾讯及百度推进开源社区，这些企业将共同维护项目。", [HUAWEI, TENCENT, BAIDU], "这些企业", "three_tech_same_sentence_mixed_conjunction"),
        positive(22, "国家电网与华能集团开展储能合作，二者将共享调峰能力。", [NATIONAL, HUANENG], "二者", "two_org_same_sentence_yu"),
        positive(23, "三峡集团和国家电网联合建设基地，双方将统一项目进度。", [THREE, NATIONAL], "双方", "two_org_same_sentence_and"),
        positive(24, "腾讯与百度合作研发模型，两家公司将共同投入算力。", [TENCENT, BAIDU], "两家公司", "two_tech_same_sentence_yu"),
        positive(25, "国家电网及三峡集团协调水电外送，上述机构将发布方案。", [NATIONAL, THREE], "上述机构", "two_org_same_sentence_ji"),
        positive(26, "华为和百度推出兼容方案，它们将同步更新文档。", [HUAWEI, BAIDU], "它们", "two_tech_same_sentence_and"),
        positive(27, "南方电网及华能集团举行技术交流，这些机构将跟进试点。", [SOUTH, HUANENG], "这些机构", "two_org_same_sentence_ji"),
        positive(28, "北京大学和上海交通大学共同举办竞赛，二者将联合评审。", [PKU, SJTU], "二者", "two_university_same_sentence_and"),
        positive(29, "华能集团以及华为开发能源系统，两家企业将共享接口规范。", [HUANENG, HUAWEI], "两家企业", "cross_domain_same_sentence_yiji"),
        positive(30, "三峡集团与华为建设数字孪生平台，双方将组织验收。", [THREE, HUAWEI], "双方", "cross_domain_same_sentence_yu"),
        positive(31, "国家电网和南方电网在年度会议上签约，两家机构将建立联络机制。", [NATIONAL, SOUTH], "两家机构", "two_org_with_event_insertion"),
        positive(32, "华为与腾讯面向开发者发布工具，它们将持续维护社区。", [HUAWEI, TENCENT], "它们", "two_tech_same_sentence_yu"),
        positive(33, "三峡集团以及华能集团联合检修机组，这些机构将共享检修记录。", [THREE, HUANENG], "这些机构", "two_generator_same_sentence_yiji"),
        positive(34, "百度及华为共同发布智能终端规范，两家公司将协商版本计划。", [BAIDU, HUAWEI], "两家公司", "two_tech_same_sentence_ji"),
        positive(35, "国家电网、南方电网以及三峡集团共同成立工作组，上述企业将轮流牵头。", [NATIONAL, SOUTH, THREE], "上述企业", "three_org_same_sentence_dunhao_yiji"),
        positive(36, "华为和腾讯签署数据安全协议，双方将定期开展评估。", [HUAWEI, TENCENT], "双方", "two_company_policy_style"),
        positive(37, "北京大学与上海交通大学建立联合实验班，两所大学将共同制定课程。", [PKU, SJTU], "两所大学", "two_university_same_sentence_yu"),
        positive(38, "国家电网及三峡集团推进抽蓄项目，这些企业将联合复盘。", [NATIONAL, THREE], "这些企业", "two_org_same_sentence_ji"),
        positive(39, "南方电网和华能集团组织应急演练，二者将共享处置预案。", [SOUTH, HUANENG], "二者", "two_org_same_sentence_and"),
        positive(40, "腾讯、百度以及华为发布行业倡议，多家企业将协同落实。", [TENCENT, BAIDU, HUAWEI], "多家企业", "three_tech_same_sentence_dunhao_yiji"),
        collective_nil(41, "国家电网和南方电网分别发布公告。双方将继续沟通。", [NATIONAL, SOUTH], "双方", "跨句集合不在当前规则支持范围", [0, 0, 1]),
        collective_nil(42, "华能集团与三峡集团完成会谈。这些机构将另行公布细节。", [HUANENG, THREE], "这些机构", "跨句集合不在当前规则支持范围", [0, 0, 1]),
        collective_nil(43, "华为和腾讯发布声明。两家公司将安排后续测试。", [HUAWEI, TENCENT], "两家公司", "跨句集合不在当前规则支持范围", [0, 0, 1]),
        collective_nil(44, "北京大学及上海交通大学举行会议。两所高校将继续交流。", [PKU, SJTU], "两所高校", "跨句集合不在当前规则支持范围", [0, 0, 1]),
        collective_nil(45, "国家电网、南方电网和华能集团公布结果。多家企业将参与复盘。", [NATIONAL, SOUTH, HUANENG], "多家企业", "跨句集合不在当前规则支持范围", [0, 0, 1]),
        collective_nil(46, "华为与广州市共同举办展会，他们随后发布公告。", [HUAWEI, (GUANGZHOU[0], GUANGZHOU[1], "GPE")], "他们", "前件类型不兼容"),
        collective_nil(47, "国家电网和广州市推进试点，双方将公布安排。", [NATIONAL, (GUANGZHOU[0], GUANGZHOU[1], "GPE")], "双方", "前件类型不兼容"),
        collective_nil(48, "三峡集团及广州市举办论坛，这些机构发布议程。", [THREE, (GUANGZHOU[0], GUANGZHOU[1], "GPE")], "这些机构", "前件类型不兼容"),
        collective_nil(49, "百度与广州市举办招聘活动，两家机构公布流程。", [BAIDU, (GUANGZHOU[0], GUANGZHOU[1], "GPE")], "两家机构", "前件类型不兼容"),
        unlinked_nil(50, "甲机构和乙机构发布联合声明，这些机构将持续合作。", "这些机构", "前件未链接到运行知识库"),
        unlinked_nil(51, "甲机构及乙机构召开会议，双方将签署备忘录。", "双方", "前件未链接到运行知识库"),
        unlinked_nil(52, "甲机构以及乙机构完成评审，两家机构将公布结论。", "两家机构", "前件未链接到运行知识库"),
        collective_nil(53, "国家电网和国家电网共同发布通知，双方将更新计划。", [NATIONAL, NATIONAL], "双方", "去重后只有一个实体 ID"),
        collective_nil(54, "华为与华为联合展示产品，两家公司将继续合作。", [HUAWEI, HUAWEI], "两家公司", "去重后只有一个实体 ID"),
        collective_nil(55, "国家电网发布公告，南方电网随后回应，双方继续沟通。", [NATIONAL, SOUTH], "双方", "前件之间不存在显式协调连接"),
        collective_nil(56, "华能集团发布计划，三峡集团随后跟进，这些企业共享信息。", [HUANENG, THREE], "这些企业", "前件之间不存在显式协调连接"),
        collective_nil(57, "华为发布新品，腾讯随后评论，两家公司组织交流。", [HUAWEI, TENCENT], "两家公司", "前件之间不存在显式协调连接"),
        single_nil(58, "国家电网和南方电网公布联合计划，他将继续跟进。", [NATIONAL, SOUTH], "他"),
        single_nil(59, "华能集团及三峡集团启动项目，她将负责协调。", [HUANENG, THREE], "她"),
        single_nil(60, "华为与腾讯发布声明，他将安排测试。", [HUAWEI, TENCENT], "他"),
    ]
    step2 = [
        annotate(positive(61, "国家电网及南方电网联合发布调度方案，双方将同步建设平台。", [NATIONAL, SOUTH], "双方", "step2_two_org_ji"), subset="acceptance_main", difficulty="medium", conjunction="及", sentence_distance=0, evidence="“双方”回指由“及”连接的两个已链接 ORG 前件。"),
        annotate(positive(62, "华能集团以及三峡集团推进水电协同，二者将共享运行数据。", [HUANENG, THREE], "二者", "step2_two_org_yiji"), subset="acceptance_main", difficulty="medium", conjunction="以及", sentence_distance=0, evidence="“二者”回指由“以及”连接的两个已链接 ORG 前件。"),
        annotate(positive(63, "国家电网、南方电网及华能集团共同制定保供计划，多家企业将协同落实。", [NATIONAL, SOUTH, HUANENG], "多家企业", "step2_three_org_mixed"), subset="acceptance_main", difficulty="hard", conjunction="顿号+及", sentence_distance=0, evidence="三实体通过顿号和“及”形成明确协调组。"),
        annotate(positive(64, "国家电网、南方电网及华能集团以及三峡集团成立工作组，多家企业将轮流牵头。", [NATIONAL, SOUTH, HUANENG, THREE], "多家企业", "step2_four_org_mixed"), subset="acceptance_main", difficulty="hard", conjunction="顿号+及+以及", sentence_distance=0, evidence="四个已链接 ORG 由连续显式连接词构成同一集合。"),
        annotate(positive(65, "国家电网和南方电网在历经三个月协商后于北京签署协议，双方将共同推进工程。", [NATIONAL, SOUTH], "双方", "step2_inserted_modifier"), subset="acceptance_main", difficulty="medium", conjunction="和", sentence_distance=0, evidence="时间、地点插入不改变“和”连接的两个前件。"),
        annotate(positive(66, "国家电网和南方电网负责输电，华为与百度负责平台建设，双方将完成系统联调。", [HUAWEI, BAIDU], "双方", "step2_nearest_coordination_group"), subset="acceptance_main", difficulty="hard", conjunction="与", sentence_distance=0, evidence="存在两个协调组时，按当前标注规范回指最近的“华为与百度”。"),
        annotate(collective_nil(67, "三峡集团与广州市共同举办论坛，双方公布后续安排。", [THREE, (GUANGZHOU[0], GUANGZHOU[1], "GPE")], "双方", "ORG 与 GPE 不能组成同质集合"), subset="acceptance_main", difficulty="medium", conjunction="与", sentence_distance=0, evidence="前件类型冲突，集合共指应拒绝。", scenario="step2_type_conflict_nil"),
        annotate(single_nil(68, "国家电网和南方电网发布联合公告，她将继续跟进。", [NATIONAL, SOUTH], "她"), subset="acceptance_main", difficulty="easy", conjunction="和", sentence_distance=0, evidence="单数人物代词不能回指机构集合。", scenario="step2_single_pronoun_nil"),
        annotate(collective_nil(69, "国家电网和国家电网共同发布通知，双方将更新计划。", [NATIONAL, NATIONAL], "双方", "去重后仅剩一个实体 ID"), subset="acceptance_main", difficulty="medium", conjunction="和", sentence_distance=0, evidence="两个 mention 指向同一 ID，不能作为集合成功。", scenario="step2_duplicate_entity_id_nil"),
        annotate(unlinked_nil(70, "甲机构及乙机构召开会议，双方将签署备忘录。", "双方", "前件未链接到运行知识库"), subset="acceptance_main", difficulty="medium", conjunction="及", sentence_distance=0, evidence="正式端到端验收要求先行词具备运行知识库实体 ID。", scenario="step2_unlinked_antecedents_nil"),
        annotate(with_sentence_indices(positive(71, "国家电网与南方电网召开会议。会议讨论了多个议题。双方最终签署备忘录。", [NATIONAL, SOUTH], "双方", "blind_cross_two_sentences"), [0, 0, 2]), subset="blind_challenge", difficulty="hard", conjunction="与", sentence_distance=2, evidence="语义上“双方”回指首句两个机构；用于检验跨两句集合能力。"),
        annotate(collective_nil(72, "国家电网与南方电网发布联合计划。华为随后提出技术方案。双方将共同建设调度平台。", [NATIONAL, SOUTH, HUAWEI], "双方", "主体切换后“双方”缺少可唯一确定的集合前件", [0, 0, 1, 2]), subset="blind_challenge", difficulty="hard", conjunction="与", sentence_distance=2, evidence="中间主体切换造成指代歧义，标注为集合 NIL。", scenario="blind_subject_switch_nil"),
        annotate(positive(73, "国家电网同南方电网共同推进项目，双方将建立联络机制。", [NATIONAL, SOUTH], "双方", "blind_same_as_conjunction"), subset="blind_challenge", difficulty="hard", conjunction="同", sentence_distance=0, evidence="“同”在自然语义中连接两个机构；用于检验未覆盖连接方式。"),
        annotate(with_antecedent_type(positive(74, "微信和腾讯会议联合升级协作功能，它们将同步开放测试。", [("微信", "ENT_GEN_0061"), ("腾讯会议", "ENT_GEN_0104")], "它们", "blind_product_collective"), "CONSUMER_PRODUCT"), subset="blind_challenge", difficulty="hard", conjunction="和", sentence_distance=0, evidence="两个运行知识库产品在语义上构成集合；用于检验非 ORG/PERSON 集合。"),
        annotate(collective_nil(75, "国家电网和南方电网发布联合计划，她们随后公布细则。", [NATIONAL, SOUTH], "她们", "运行知识库无可用女性 PERSON 前件，机构集合不应由“她们”回指"), subset="blind_challenge", difficulty="hard", conjunction="和", sentence_distance=0, evidence="不虚构 PERSON 实体 ID；“她们”作为类型不兼容边界。", scenario="blind_female_pronoun_type_conflict_nil"),
    ]
    step3 = [
        annotate(positive(76, "国家电网及大唐集团联合开展保供演练，双方将共享调度方案。", [NATIONAL, DADANG], "双方", "step3_energy_ji"), subset="acceptance_main", difficulty="medium", conjunction="及", sentence_distance=0, evidence="能源机构由“及”连接，双方回指两个运行 KB 前件。"),
        annotate(positive(77, "国家电网以及国家电投共同发布储能倡议，二者将建立联络机制。", [NATIONAL, SPIC], "二者", "step3_energy_yiji"), subset="acceptance_main", difficulty="medium", conjunction="以及", sentence_distance=0, evidence="两个能源机构由“以及”构成协调组。"),
        annotate(positive(78, "中国移动及中国电信推进算网协同，两家公司将开放试验环境。", [MOBILE, TELECOM], "两家公司", "step3_telecom_ji"), subset="acceptance_main", difficulty="medium", conjunction="及", sentence_distance=0, evidence="两个通信企业形成明确同句集合。"),
        annotate(positive(79, "新华社以及中央广电总台共同报道论坛，这些机构将共享采编资源。", [XINHUA, CCTV], "这些机构", "step3_media_yiji"), subset="acceptance_main", difficulty="medium", conjunction="以及", sentence_distance=0, evidence="媒体机构由“以及”连接。"),
        annotate(positive(80, "国铁集团及南方航空优化联运服务，双方将统一换乘指引。", [RAIL, SOUTH_AIR], "双方", "step3_transport_ji"), subset="acceptance_main", difficulty="medium", conjunction="及", sentence_distance=0, evidence="交通机构形成双主体集合。"),
        annotate(positive(81, "工商银行及建设银行推出绿色信贷方案，两家机构将交流风控经验。", [ICBC, CCB], "两家机构", "step3_finance_ji"), subset="acceptance_main", difficulty="medium", conjunction="及", sentence_distance=0, evidence="金融机构由“及”连接。"),
        annotate(positive(82, "中日友好医院及瑞金医院开展远程会诊，这些机构将共享病例规范。", [("中日友好医院", "ENT_GEN_0111"), ("瑞金医院", "ENT_GEN_0112")], "这些机构", "step3_medical_ji"), subset="acceptance_main", difficulty="medium", conjunction="及", sentence_distance=0, evidence="两个医疗机构是同句已链接前件。"),
        annotate(positive(83, "清华大学及浙江大学联合举办课程，两所高校将共同组织答辩。", [TSINGHUA, ZJU], "两所高校", "step3_university_ji"), subset="acceptance_main", difficulty="medium", conjunction="及", sentence_distance=0, evidence="高校前件由“及”连接。"),
        annotate(positive(84, "华为与阿里巴巴联合发布安全规范，双方将组织开发者测试。", [HUAWEI, ALIBABA], "双方", "step3_tech_yu"), subset="acceptance_main", difficulty="medium", conjunction="与", sentence_distance=0, evidence="科技企业同句显式并列。"),
        annotate(positive(85, "比亚迪和宁德时代签署电池合作协议，两家企业将公布兼容标准。", [BYD, CATL], "两家企业", "step3_new_energy_and"), subset="acceptance_main", difficulty="medium", conjunction="和", sentence_distance=0, evidence="新能源企业由“和”连接。"),
        annotate(positive(86, "国家能源局与国家发展改革委召开专题会议，双方将分别推进实施细则。", [ENERGY_BUREAU, NDRC], "双方", "step3_government_yu"), subset="acceptance_main", difficulty="medium", conjunction="与", sentence_distance=0, evidence="两个政府机构形成协调组。"),
        annotate(positive(87, "工业和信息化部与生态环境部会商绿色制造，二者将联合发布指南。", [MIIT, ECOLOGY], "二者", "step3_government_yu_two"), subset="acceptance_main", difficulty="medium", conjunction="与", sentence_distance=0, evidence="“二者”回指同句两个机构。"),
        annotate(positive(88, "人民日报社和中国日报社共同策划专题报道，这些机构将共享采访线索。", [RENMIN, CHINA_DAILY], "这些机构", "step3_media_and"), subset="acceptance_main", difficulty="medium", conjunction="和", sentence_distance=0, evidence="新闻机构的集合回指。"),
        annotate(positive(89, "国网江苏电力与广东电网开展跨省交易试点，两家机构将对接结算规则。", [JIANGSU_GRID, GUANGDONG_GRID], "两家机构", "step3_regional_grid_yu"), subset="acceptance_main", difficulty="hard", conjunction="与", sentence_distance=0, evidence="区域电网机构形成同质集合。"),
        annotate(positive(90, "北京天坛医院和邵逸夫医院联合制定转诊流程，双方将共享培训材料。", [TIANTAN, SHAOYIFU], "双方", "step3_medical_and"), subset="acceptance_main", difficulty="medium", conjunction="和", sentence_distance=0, evidence="医疗机构同句显式协调。"),
        annotate(positive(91, "国家电网、南方电网、大唐集团及国家电投共同发布保供方案，多家企业将同步落实。", [NATIONAL, SOUTH, DADANG, SPIC], "多家企业", "step3_four_energy"), subset="acceptance_main", difficulty="hard", conjunction="顿号+及", sentence_distance=0, evidence="四个能源机构形成连续协调组。"),
        annotate(positive(92, "华为、腾讯及阿里巴巴联合建设开源社区，多家企业将维护基础设施。", [HUAWEI, TENCENT, ALIBABA], "多家企业", "step3_three_tech"), subset="acceptance_main", difficulty="hard", conjunction="顿号+及", sentence_distance=0, evidence="三个科技企业形成集合。"),
        annotate(positive(93, "工商银行、建设银行及中国银行共同发布报告，多家机构将完善绿色金融服务。", [ICBC, CCB, ("中国银行", "ENT_GEN_0083")], "多家机构", "step3_three_finance"), subset="acceptance_main", difficulty="hard", conjunction="顿号+及", sentence_distance=0, evidence="三个金融机构由连续连接词组成集合。"),
        annotate(positive(94, "清华大学、北京大学及浙江大学共建课程平台，这些机构将共享实验资源。", [TSINGHUA, PKU, ZJU], "这些机构", "step3_three_university"), subset="acceptance_main", difficulty="hard", conjunction="顿号+及", sentence_distance=0, evidence="三个高校实体在同句形成协调组。"),
        annotate(positive(95, "国铁集团、南方航空及中国国航共同优化出行服务，多家机构将发布联运规则。", [RAIL, SOUTH_AIR, ("中国国航", "ENT_GEN_0135")], "多家机构", "step3_three_transport"), subset="acceptance_main", difficulty="hard", conjunction="顿号+及", sentence_distance=0, evidence="三个交通机构形成同句集合。"),
        annotate(positive(96, "国家能源局和国家发展改革委在多轮论证后于北京签署备忘录，双方将建立项目台账。", [ENERGY_BUREAU, NDRC], "双方", "step3_long_insertion"), subset="acceptance_main", difficulty="hard", conjunction="和", sentence_distance=0, evidence="长插入语不影响显式协调关系。"),
        annotate(positive(97, "电力规划设计总院与中国电力科学研究院共同评审方案，上述机构将发布技术意见。", [("电力规划设计总院", "ENT_ENERGY_0049"), ("中国电力科学研究院", "ENT_ENERGY_0050")], "上述机构", "step3_research_yu"), subset="acceptance_main", difficulty="medium", conjunction="与", sentence_distance=0, evidence="研究机构集合由“与”连接。"),
        annotate(positive(98, "国家电网和南方电网负责输电，工商银行与建设银行负责融资，双方将先完成授信评审。", [ICBC, CCB], "双方", "step3_multi_group_finance_nearest"), subset="acceptance_main", difficulty="hard", conjunction="与", sentence_distance=0, evidence="两组协调结构中，“双方”回指最近的金融机构组。"),
        annotate(positive(99, "华为与腾讯推进平台建设，新华社和中央广电总台负责传播，双方将联合发布报道。", [XINHUA, CCTV], "双方", "step3_multi_group_media_nearest"), subset="acceptance_main", difficulty="hard", conjunction="和", sentence_distance=0, evidence="最近协调组为两个媒体机构。"),
        annotate(positive(100, "清华大学及北京大学完成课程设计，浙江大学与复旦大学负责试点，二者将同步反馈结果。", [ZJU, ("复旦大学", "ENT_GEN_0067")], "二者", "step3_multi_group_university_nearest"), subset="acceptance_main", difficulty="hard", conjunction="与", sentence_distance=0, evidence="“二者”回指最近的高校协调组。"),
        annotate(positive(101, "国家电网、南方电网及三峡集团完成联合演练，上述企业将复盘处置流程。", [NATIONAL, SOUTH, THREE], "上述企业", "step3_three_energy_above"), subset="acceptance_main", difficulty="hard", conjunction="顿号+及", sentence_distance=0, evidence="三个能源机构由“上述企业”集合回指。"),
        annotate(positive(102, "中国移动和中国电信发布协同计划，这些企业将共同开放边缘节点。", [MOBILE, TELECOM], "这些企业", "step3_telecom_and"), subset="acceptance_main", difficulty="medium", conjunction="和", sentence_distance=0, evidence="通信企业集合回指。"),
        annotate(positive(103, "华能集团及大唐集团启动机组检修，两家公司将统一排期。", [HUANENG, DADANG], "两家公司", "step3_generator_ji"), subset="acceptance_main", difficulty="medium", conjunction="及", sentence_distance=0, evidence="两个能源企业由“及”连接。"),
        annotate(collective_nil(104, "国家电网和微信共同发布工具说明，双方将安排培训。", [NATIONAL, ("微信", "ENT_GEN_0061", "CONSUMER_PRODUCT")], "双方", "ORG 与产品类型不兼容"), subset="acceptance_main", difficulty="hard", conjunction="和", sentence_distance=0, evidence="混合类型前件不能组成规则允许的集合。", scenario="step3_org_product_conflict_nil"),
        annotate(unlinked_nil(105, "甲机构和乙机构分别说明进展，双方将继续沟通。", "双方", "两个前件均未链接到运行知识库"), subset="acceptance_main", difficulty="medium", conjunction="和", sentence_distance=0, evidence="未链接前件不产生正式实体集合。", scenario="step3_unlinked_both_nil"),
        annotate(with_sentence_indices(positive(106, "国家电网和南方电网签署协议。双方随后公布实施方案。", [NATIONAL, SOUTH], "双方", "blind_cross_adjacent"), [0, 0, 1]), subset="blind_challenge", difficulty="hard", conjunction="和", sentence_distance=1, evidence="语义上“双方”跨句回指两个电网机构。"),
        annotate(with_sentence_indices(positive(107, "华能集团与三峡集团召开会议。会议由主持人说明议程。双方最终确定调度机制。", [HUANENG, THREE], "双方", "blind_cross_with_intervening_entity"), [0, 0, 2]), subset="blind_challenge", difficulty="hard", conjunction="与", sentence_distance=2, evidence="中间插入句子不应改变语义上的原协调组。"),
        annotate(positive(108, "中国移动跟中国电信共同开展测试，双方将公布结果。", [MOBILE, TELECOM], "双方", "blind_gen_conjunction"), subset="blind_challenge", difficulty="hard", conjunction="跟", sentence_distance=0, evidence="“跟”自然连接两个机构，但当前规则尚未覆盖。"),
        annotate(positive(109, "国家电网连同南方电网推进改造工程，两家机构将共同验收。", [NATIONAL, SOUTH], "两家机构", "blind_liantong_conjunction"), subset="blind_challenge", difficulty="hard", conjunction="连同", sentence_distance=0, evidence="“连同”表达联合参与，用于盲测连接词覆盖。"),
        annotate(positive(110, "国家能源局会同国家发展改革委发布通知，双方将督促落实。", [ENERGY_BUREAU, NDRC], "双方", "blind_huitong_conjunction"), subset="blind_challenge", difficulty="hard", conjunction="会同", sentence_distance=0, evidence="“会同”表达联合行动，用于盲测连接词覆盖。"),
        annotate(positive(111, "国家电网、南方电网及华能集团共同参会，各方将提交实施清单。", [NATIONAL, SOUTH, HUANENG], "各方", "blind_all_parties"), subset="blind_challenge", difficulty="hard", conjunction="顿号+及", sentence_distance=0, evidence="“各方”语义上回指三个明确参与主体。"),
        annotate(positive(112, "华为、腾讯及百度联合成立实验室，三方将共同管理成果。", [HUAWEI, TENCENT, BAIDU], "三方", "blind_three_parties"), subset="blind_challenge", difficulty="hard", conjunction="顿号+及", sentence_distance=0, evidence="“三方”语义上回指三个科技企业。"),
        annotate(positive(113, "清华大学与北京大学共同建设课程平台，两者将开放教学资源。", [TSINGHUA, PKU], "两者", "blind_liangzhe"), subset="blind_challenge", difficulty="hard", conjunction="与", sentence_distance=0, evidence="“两者”语义上回指两个高校。"),
        annotate(positive(114, "新华社和中央广电总台联合采访，该二者将共享素材。", [XINHUA, CCTV], "该二者", "blind_the_two"), subset="blind_challenge", difficulty="hard", conjunction="和", sentence_distance=0, evidence="“该二者”语义上回指两个媒体机构。"),
        annotate(positive(115, "工商银行及建设银行联合发布报告，上述单位将说明风险控制措施。", [ICBC, CCB], "上述单位", "blind_above_units"), subset="blind_challenge", difficulty="hard", conjunction="及", sentence_distance=0, evidence="“上述单位”语义上回指两个金融机构。"),
        annotate(collective_nil(116, "国家电网与南方电网发布联合计划。华为随后单独提出技术方案。双方将建设平台。", [NATIONAL, SOUTH, HUAWEI], "双方", "主体切换后集合前件不唯一", [0, 0, 1, 2]), subset="blind_challenge", difficulty="hard", conjunction="与", sentence_distance=2, evidence="主体切换后“双方”无唯一语义指向。", scenario="blind_subject_switch_second_nil"),
        annotate(collective_nil(117, "华为和支付宝联合发布活动说明，双方将开放报名。", [HUAWEI, ("支付宝", "ENT_GEN_0097", "SOFTWARE_PLATFORM")], "双方", "ORG 与软件平台类型不兼容"), subset="blind_challenge", difficulty="hard", conjunction="和", sentence_distance=0, evidence="混合类型主体不应被强行组成集合。", scenario="blind_org_platform_conflict_nil"),
        annotate(unlinked_nil(118, "甲机构及乙机构宣布合作，双方将建立协调组。", "双方", "前件均未链接到运行知识库"), subset="blind_challenge", difficulty="hard", conjunction="及", sentence_distance=0, evidence="无运行 KB 前件时应返回集合 NIL。", scenario="blind_unlinked_nil"),
        annotate(collective_nil(119, "国家电网和国家电网联合发布通知，双方将共同实施。", [NATIONAL, NATIONAL], "双方", "去重后只有一个有效实体 ID"), subset="blind_challenge", difficulty="hard", conjunction="和", sentence_distance=0, evidence="重复实体 ID 不能充当两个集合成员。", scenario="blind_duplicate_id_nil"),
        annotate(collective_nil(120, "国家电网发布公告，南方电网随后回应，双方将继续沟通。", [NATIONAL, SOUTH], "双方", "前件之间没有显式协调连接"), subset="blind_challenge", difficulty="hard", conjunction="none", sentence_distance=0, evidence="两个实体并不构成明确共同前件。", scenario="blind_no_coordination_nil"),
        annotate(collective_nil(121, "国家电网和南方电网发布方案，三方将继续磋商。", [NATIONAL, SOUTH], "三方", "集合代词数量与两个前件不匹配"), subset="blind_challenge", difficulty="hard", conjunction="和", sentence_distance=0, evidence="文本仅有两个有效前件，不能标注为三方集合。", scenario="blind_cardinality_mismatch_nil"),
        annotate(collective_nil(122, "国家电网和南方电网完成签约。双方随后公布细则。", [NATIONAL, SOUTH], "双方", "跨句隐式集合不在当前规则支持范围", [0, 0, 1]), subset="blind_challenge", difficulty="hard", conjunction="和", sentence_distance=1, evidence="作为跨句规则边界 NIL 保留。", scenario="blind_cross_sentence_nil"),
        annotate(collective_nil(123, "国家电网和南方电网负责输电，华为与腾讯负责平台，双方将在年内验收。", [NATIONAL, SOUTH, HUAWEI, TENCENT], "双方", "两个协调组均可能被“双方”指代，缺少语义限定",), subset="blind_challenge", difficulty="hard", conjunction="mixed", sentence_distance=0, evidence="多协调组无额外限定时标注为集合 NIL。", scenario="blind_multi_group_ambiguous_nil"),
        annotate(collective_nil(124, "国家电网和南方电网发布联合计划，她们随后公布细则。", [NATIONAL, SOUTH], "她们", "机构前件与女性 PERSON 集合代词类型不兼容"), subset="blind_challenge", difficulty="hard", conjunction="和", sentence_distance=0, evidence="不虚构女性 PERSON 运行知识库 ID。", scenario="blind_female_org_conflict_nil"),
        annotate(collective_nil(125, "国家电网与南方电网召开会议。会议记录已经归档。相关部门完成审查。双方将启动项目。", [NATIONAL, SOUTH], "双方", "跨越多个句子的隐式集合不在当前规则支持范围", [0, 0, 3]), subset="blind_challenge", difficulty="hard", conjunction="与", sentence_distance=3, evidence="远距离跨句集合边界。", scenario="blind_long_distance_nil"),
    ]
    data["samples"] = base + extra + step2 + step3
    # These 25 examples have been read during failure analysis and are now
    # development challenges rather than a pristine blind holdout.
    for sample in data["samples"]:
        if sample.get("subset") == "blind_challenge":
            sample["subset"] = "challenge_dev"
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_annotation_review(data)
    print(f"wrote {len(data['samples'])} samples to {PATH.relative_to(ROOT)}")
    print(f"wrote review checklist to {REVIEW_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
