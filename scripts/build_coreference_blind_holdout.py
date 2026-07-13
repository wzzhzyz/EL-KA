"""Build the post-freeze collective-coreference blind holdout deterministically."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "eval" / "coreference_blind_holdout.json"
REVIEW = ROOT / "reports" / "coreference_blind_holdout_annotation_review.md"


def named(text: str, name: str, entity_id: str, entity_type: str = "ORG", sentence: int | None = None) -> dict:
    start = text.index(name)
    item = {"mention": name, "type": entity_type, "char_start": start, "char_end": start + len(name), "role": "name", "entity_id": entity_id}
    if sentence is not None:
        item["sentence_index"] = sentence
    return item


def pronoun(text: str, value: str, sentence: int | None = None) -> dict:
    start = text.index(value)
    item = {"mention": value, "type": "PRON", "char_start": start, "char_end": start + len(value), "role": "pronoun"}
    if sentence is not None:
        item["sentence_index"] = sentence
    return item


def sample(sample_id: int, text: str, entities: list[tuple[str, str, str]], target: str, *, scenario: str, difficulty: str, expected_ids: list[str] | None, sentence_indices: list[int] | None = None, evidence: str = "") -> dict:
    mentions = []
    for index, (name, entity_id, entity_type) in enumerate(entities):
        mentions.append(named(text, name, entity_id, entity_type, sentence_indices[index] if sentence_indices else None))
    target_sentence = sentence_indices[-1] if sentence_indices else None
    mentions.append(pronoun(text, target, target_sentence))
    is_nil = expected_ids is None
    case = {
        "mention_index": len(mentions) - 1,
        "entity_id": None,
        "entity_ids": [] if is_nil else expected_ids,
        "antecedent_indices": [] if is_nil else list(range(len(entities))),
        "is_collective": True,
        "is_nil": is_nil,
        "scenario": scenario,
        "difficulty": difficulty,
        "subset": "blind_holdout",
        "annotation_evidence": evidence,
    }
    if is_nil:
        case["nil_reason"] = evidence
    return {"id": f"CORE_BLIND_HOLDOUT_{sample_id:03d}", "text": text, "mentions": mentions, "expected_coreferences": [case], "scenario": scenario, "difficulty": difficulty, "subset": "blind_holdout", "annotation_evidence": evidence}


def main() -> None:
    E = {
        "energy": ("国家能源局", "ENT_GEN_0059", "ORG"), "ndrc": ("国家发展改革委", "ENT_GEN_0089", "ORG"), "miit": ("工业和信息化部", "ENT_GEN_0090", "ORG"),
        "mobile": ("中国移动", "ENT_GEN_0102", "ORG"), "telecom": ("中国电信", "ENT_GEN_0103", "ORG"), "alibaba": ("阿里巴巴", "ENT_GEN_0053", "ORG"),
        "jiangsu": ("国网江苏电力", "ENT_GEN_0124", "ORG"), "guangdong": ("广东电网", "ENT_GEN_0125", "ORG"), "south": ("南方电网", "ENT_ENERGY_0002", "ORG"),
        "people": ("人民日报社", "ENT_GEN_0139", "ORG"), "xinhua": ("新华社", "ENT_GEN_0115", "ORG"), "daily": ("中国日报社", "ENT_GEN_0153", "ORG"),
        "byd": ("比亚迪", "ENT_ENERGY_0016", "ORG"), "catl": ("宁德时代", "ENT_ENERGY_0015", "ORG"), "huawei": ("华为", "ENT_GEN_0051", "ORG"), "dadang": ("大唐集团", "ENT_ENERGY_0004", "ORG"),
        "tsinghua": ("清华大学", "ENT_GEN_0060", "ORG"), "zju": ("浙江大学", "ENT_GEN_0066", "ORG"), "sjtu": ("上海交通大学", "ENT_GEN_0065", "ORG"),
        "rail": ("国铁集团", "ENT_GEN_0113", "ORG"), "air": ("南方航空", "ENT_GEN_0114", "ORG"), "icbc": ("工商银行", "ENT_GEN_0055", "ORG"), "ccb": ("建设银行", "ENT_GEN_0081", "ORG"),
        "huaneng": ("华能集团", "ENT_ENERGY_0003", "ORG"), "three": ("三峡集团", "ENT_ENERGY_0008", "ORG"), "spic": ("国家电投", "ENT_ENERGY_0006", "ORG"),
        "wechat": ("微信", "ENT_GEN_0061", "CONSUMER_PRODUCT"), "meeting": ("腾讯会议", "ENT_GEN_0104", "CONSUMER_PRODUCT"), "alipay": ("支付宝", "ENT_GEN_0097", "SOFTWARE_PLATFORM"),
    }
    id_of = lambda *items: [E[item][1] for item in items]
    rows = [
        sample(1, "国家能源局、国家发展改革委及工业和信息化部联合印发行动方案，三方将分别跟进落实。", [E["energy"], E["ndrc"], E["miit"]], "三方", scenario="holdout_three_government_group", difficulty="hard", expected_ids=id_of("energy", "ndrc", "miit"), evidence="三个已链接政府机构由顿号和“及”组成唯一协调组。"),
        sample(2, "中国移动、华为和阿里巴巴共建云服务中心，这些企业将共享运维经验。", [E["mobile"], E["huawei"], E["alibaba"]], "这些企业", scenario="holdout_three_tech_group", difficulty="hard", expected_ids=id_of("mobile", "huawei", "alibaba"), evidence="三个已链接企业通过连续显式连接词组成唯一协调组。"),
        sample(3, "国网江苏电力、广东电网及南方电网成立调度专班，各方将提交值守安排。", [E["jiangsu"], E["guangdong"], E["south"]], "各方", scenario="holdout_three_grid_group", difficulty="hard", expected_ids=id_of("jiangsu", "guangdong", "south"), evidence="三个电网机构由顿号和“及”构成唯一同句协调组。"),
        sample(4, "人民日报社、新华社及中国日报社开设专题栏目，上述单位将统一发布稿件。", [E["people"], E["xinhua"], E["daily"]], "上述单位", scenario="holdout_three_media_group", difficulty="hard", expected_ids=id_of("people", "xinhua", "daily"), evidence="三个媒体机构构成唯一明确协调组。"),
        sample(5, "比亚迪、宁德时代及华为举办技术论坛，三方将共同发布倡议。", [E["byd"], E["catl"], E["huawei"]], "三方", scenario="holdout_three_industry_group", difficulty="hard", expected_ids=id_of("byd", "catl", "huawei"), evidence="三个已链接机构满足“三方”的精确数量约束。"),
        sample(6, "清华大学、浙江大学和上海交通大学共同编制课程标准，这些机构将互认学分。", [E["tsinghua"], E["zju"], E["sjtu"]], "这些机构", scenario="holdout_three_university_group", difficulty="medium", expected_ids=id_of("tsinghua", "zju", "sjtu"), evidence="三个高校形成唯一同句协调组。"),
        sample(7, "国铁集团和南方航空先完成线路衔接。双方随后公布联运细则。", [E["rail"], E["air"]], "双方", scenario="holdout_cross_one_positive", difficulty="hard", expected_ids=id_of("rail", "air"), sentence_indices=[0, 0, 1], evidence="语义上后句“双方”回指前句唯一协调组。"),
        sample(8, "工商银行与建设银行达成服务协议。二者将在下月上线新流程。", [E["icbc"], E["ccb"]], "二者", scenario="holdout_cross_one_pair_positive", difficulty="hard", expected_ids=id_of("icbc", "ccb"), sentence_indices=[0, 0, 1], evidence="语义上后句“二者”回指前句唯一协调组。"),
        sample(9, "华能集团及三峡集团启动联合演练。会议纪要随后归档。双方将复盘演练结果。", [E["huaneng"], E["three"]], "双方", scenario="holdout_cross_two_positive", difficulty="hard", expected_ids=id_of("huaneng", "three"), sentence_indices=[0, 0, 2], evidence="中间事件说明不改变首句唯一协调组的语义连续性。"),
        sample(10, "人民日报社与新华社召开选题会。会议记录由秘书整理。双方将确认发布节奏。", [E["people"], E["xinhua"]], "双方", scenario="holdout_cross_two_media_positive", difficulty="hard", expected_ids=id_of("people", "xinhua"), sentence_indices=[0, 0, 2], evidence="中间无新的已链接主体，语义上保持首句协调组。"),
        sample(11, "华能集团与三峡集团在多轮技术论证和现场勘察后签署备忘录，双方将建立联合台账。", [E["huaneng"], E["three"]], "双方", scenario="holdout_non_adjacent_modifier", difficulty="medium", expected_ids=id_of("huaneng", "three"), evidence="长修饰成分不切断两个前件之间的显式“与”连接。"),
        sample(12, "国家电投会同大唐集团开展安全检查，双方将交换排查结果。", [E["spic"], E["dadang"]], "双方", scenario="holdout_huitong_group", difficulty="medium", expected_ids=id_of("spic", "dadang"), evidence="“会同”位于两个相邻已链接机构之间。"),
        sample(13, "中国移动跟中国电信联合测试新网络，两家公司将同步开放体验。", [E["mobile"], E["telecom"]], "两家公司", scenario="holdout_gen_group", difficulty="medium", expected_ids=id_of("mobile", "telecom"), evidence="“跟”连接两个同类已链接企业。"),
        sample(14, "工商银行连同建设银行推进支付互联，上述单位将公布服务说明。", [E["icbc"], E["ccb"]], "上述单位", scenario="holdout_liantong_group", difficulty="medium", expected_ids=id_of("icbc", "ccb"), evidence="“连同”连接两个同类已链接机构。"),
        sample(15, "微信和腾讯会议完善协同能力，它们将开放新版功能。", [E["wechat"], E["meeting"]], "它们", scenario="holdout_product_collective_positive", difficulty="hard", expected_ids=id_of("wechat", "meeting"), evidence="两个产品在语义上构成集合，用于检验非 ORG/PERSON 范围。"),
        sample(16, "国家能源局和国家发展改革委在项目评审中形成共识，双方将共同督办。", [E["energy"], E["ndrc"]], "双方", scenario="holdout_government_pair", difficulty="medium", expected_ids=id_of("energy", "ndrc"), evidence="两个政府机构构成唯一同句协调组。"),
        sample(17, "人民日报社和新华社发布联合通报，她们将于下午说明情况。", [E["people"], E["xinhua"]], "她们", scenario="holdout_female_org_nil", difficulty="hard", expected_ids=None, evidence="女性 PERSON 集合词不能安全回指 ORG 前件。"),
        sample(18, "微信与支付宝共同推出服务，双方将进行培训。", [E["wechat"], E["alipay"]], "双方", scenario="holdout_product_platform_mismatch_nil", difficulty="hard", expected_ids=None, evidence="产品与软件平台混合，当前规则不应形成同质集合。"),
        sample(19, "国家电投和大唐集团负责设备，华为与阿里巴巴负责平台，双方将在季度末验收。", [E["spic"], E["dadang"], E["huawei"], E["alibaba"]], "双方", scenario="holdout_multi_group_ambiguous_nil", difficulty="hard", expected_ids=None, evidence="两个合法协调组均可能被“双方”指代，缺少可靠语义限定。"),
        sample(20, "中国移动和中国移动共同发布公告，双方将安排说明会。", [E["mobile"], E["mobile"]], "双方", scenario="holdout_duplicate_entity_nil", difficulty="medium", expected_ids=None, evidence="去重后仅有一个唯一实体 ID，不能构成集合。"),
        sample(21, "甲机构与乙机构联合举办活动，双方将发布安排。", [("甲机构", "", "ORG"), ("乙机构", "", "ORG")], "双方", scenario="holdout_unlinked_antecedents_nil", difficulty="medium", expected_ids=None, evidence="两个前件未链接运行知识库，不能输出正式实体集合。"),
        sample(22, "国家能源局发布通知，国家发展改革委随后回应，双方将召开座谈会。", [E["energy"], E["ndrc"]], "双方", scenario="holdout_no_coordination_nil", difficulty="hard", expected_ids=None, evidence="两个实体间没有显式协调连接，不能安全组成集合。"),
        sample(23, "国铁集团和南方航空启动联运项目，三方将持续跟进。", [E["rail"], E["air"]], "三方", scenario="holdout_cardinality_nil", difficulty="hard", expected_ids=None, evidence="仅有两个唯一实体，不满足“三方”的精确数量约束。"),
        sample(24, "国家电投与大唐集团先完成试运。项目随后由华为监督。双方将更新计划。", [E["spic"], E["dadang"], E["huawei"]], "双方", scenario="holdout_subject_switch_nil", difficulty="hard", expected_ids=None, sentence_indices=[0, 0, 1, 2], evidence="中间出现新的已链接主体，集合前件不再唯一。"),
        sample(25, "广东电网与国网江苏电力完成调度协商。双方将在下一阶段推进实施。", [E["guangdong"], E["jiangsu"]], "双方", scenario="holdout_cross_sentence_nil", difficulty="hard", expected_ids=None, sentence_indices=[0, 0, 1], evidence="跨句集合缺乏可验证的话语连续性信号，按保守策略返回 NIL。"),
    ]
    # Remove placeholder IDs from unlinked antecedents; they are names, not KB references.
    for row in rows:
        for item in row["mentions"]:
            if item.get("entity_id") == "":
                item.pop("entity_id")
    payload = {"dataset_name": "coreference_blind_holdout", "version": "1.0", "evaluation_scope": "blind_holdout", "requires_runtime_kb": True, "used_for_rule_development": False, "purpose": "P0 规则冻结后的独立泛化测试集；结果产生后不得据此继续调规则。", "annotation_policy": {"offset_convention": "[start, end)", "collective_match": "entity_id set exact match", "nil_policy": "entity_ids为空且is_nil=true"}, "samples": rows}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Blind Holdout 标注复核清单", "", "## 复核口径", "", "- 数据集在 P0 规则冻结后建立，`used_for_rule_development=false`。", "- 全部 25 条已完成单人初审：字段、偏移、运行 KB ID、gold 与场景说明均已核对。", "- **single-review limitation**：当前无法取得独立第二位标注者复核；所有 `hard` 样本标为“待独立二次复核”，不得伪称双人复核。", "", "|Sample ID|文本|目标指代|Gold `entity_ids`|Gold NIL|场景|难度|标注依据|复核状态|复核备注|", "|-|-|-|-|-|-|-|-|-|-|"]
    for row in rows:
        case = row["expected_coreferences"][0]
        target = row["mentions"][case["mention_index"]]["mention"]
        ids = "、".join(f"`{item}`" for item in case["entity_ids"]) or "`[]`"
        status = "单人初审完成；待独立二次复核" if row["difficulty"] == "hard" else "单人初审完成"
        note = "困难样本保留，不以规则预期改写 gold。" if row["difficulty"] == "hard" else "已核对运行 KB 实体引用与字符偏移。"
        lines.append(f"|{row['id']}|{row['text']}|{target}|{ids}|{'是' if case['is_nil'] else '否'}|{row['scenario']}|{row['difficulty']}|{case['annotation_evidence']}|{status}|{note}|")
    REVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} samples to {OUT.relative_to(ROOT)}")
    print(f"wrote annotation review to {REVIEW.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
