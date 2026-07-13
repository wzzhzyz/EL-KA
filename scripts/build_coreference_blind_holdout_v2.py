"""One-shot builder for the frozen, non-development Blind Holdout v2."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/eval/coreference_blind_holdout_v2.json'
# (domain, scenario, text, mentions, target, gold, nil)
ROWS=[
('Energy','same_sentence_recent_positive','调度演练中，国家电网与南方电网核对方案，华能集团及大唐集团负责保供，双方随后签收任务单。',[('国家电网','ENT_ENERGY_0001'),('南方电网','ENT_ENERGY_0002'),('华能集团','ENT_ENERGY_0003'),('大唐集团','ENT_ENERGY_0004')],'双方',['ENT_ENERGY_0003','ENT_ENERGY_0004'],False),
('Finance','same_sentence_recent_positive','结算论坛讨论后，工商银行和建设银行介绍接口，农业银行与中国银行确认清分职责，双方开始联测。',[('工商银行','ENT_GEN_0055'),('建设银行','ENT_GEN_0081'),('农业银行','ENT_GEN_0082'),('中国银行','ENT_GEN_0083')],'双方',['ENT_GEN_0082','ENT_GEN_0083'],False),
('Internet','same_sentence_recent_positive','产品评审会上，华为同腾讯交流协议，阿里巴巴和小米公布兼容计划，他们同步开放申请。',[('华为','ENT_GEN_0051'),('腾讯','ENT_GEN_0052'),('阿里巴巴','ENT_GEN_0053'),('小米','ENT_GEN_0073')],'他们',['ENT_GEN_0053','ENT_GEN_0073'],False),
('Transportation','same_sentence_recent_positive','枢纽协调会议中，中国国航与东方航空提交时刻表，海南航空和深圳地铁确认换乘窗口，双方安排值守。',[('中国国航','ENT_GEN_0135'),('东方航空','ENT_GEN_0136'),('海南航空','ENT_GEN_0152'),('深圳地铁','ENT_GEN_0151')],'双方',['ENT_GEN_0152','ENT_GEN_0151'],False),
('Healthcare','same_sentence_recent_positive','远程会诊开始前，中日友好医院与北京天坛医院分享病例，华西医院和湘雅医院制定路径，双方跟进随访。',[('中日友好医院','ENT_GEN_0111'),('北京天坛医院','ENT_GEN_0147'),('华西医院','ENT_GEN_0131'),('湘雅医院','ENT_GEN_0132')],'双方',['ENT_GEN_0131','ENT_GEN_0132'],False),
('Media','same_sentence_recent_positive','专题策划会上，新华社与中国日报社确定采访线，人民日报社和经济日报社分配版面，双方进入采编。',[('新华社','ENT_GEN_0115'),('中国日报社','ENT_GEN_0153'),('人民日报社','ENT_GEN_0139'),('经济日报社','ENT_GEN_0154')],'双方',['ENT_GEN_0139','ENT_GEN_0154'],False),
]
# Add independent NIL and cardinality contexts; all retain fully linked inputs.
ROWS += [
('Energy','subject_switch_nil','电网企业交流储能经验，华能集团与大唐集团商定检修，国家能源局改由专项组发布检查清单，双方提交回执。',[('华能集团','ENT_ENERGY_0003'),('大唐集团','ENT_ENERGY_0004'),('国家能源局','ENT_GEN_0059')],'双方',[],True),
('Finance','event_switch_nil','工商银行与建设银行讨论授信，农业银行和中国银行完成对账，中信证券转而说明市场风险，双方启动培训。',[('工商银行','ENT_GEN_0055'),('建设银行','ENT_GEN_0081'),('农业银行','ENT_GEN_0082'),('中国银行','ENT_GEN_0083'),('中信证券','ENT_GEN_0085')],'双方',[],True),
('Internet','event_switch_nil','华为和腾讯研究开放平台，阿里巴巴与小米拟定适配表，字节跳动随后发布内容治理通知，双方确认排期。',[('华为','ENT_GEN_0051'),('腾讯','ENT_GEN_0052'),('阿里巴巴','ENT_GEN_0053'),('小米','ENT_GEN_0073'),('字节跳动','ENT_GEN_0075')],'双方',[],True),
('Transportation','event_switch_nil','中国国航与东方航空讨论联票，海南航空和深圳地铁交换客流预测，国家统计局转而披露年度数据，双方核验资料。',[('中国国航','ENT_GEN_0135'),('东方航空','ENT_GEN_0136'),('海南航空','ENT_GEN_0152'),('深圳地铁','ENT_GEN_0151'),('国家统计局','ENT_GEN_0117')],'双方',[],True),
('Healthcare','event_switch_nil','中日友好医院和北京天坛医院安排转诊，华西医院与湘雅医院进行会诊，国家统计局随后公布卫生统计，双方继续服务。',[('中日友好医院','ENT_GEN_0111'),('北京天坛医院','ENT_GEN_0147'),('华西医院','ENT_GEN_0131'),('湘雅医院','ENT_GEN_0132'),('国家统计局','ENT_GEN_0117')],'双方',[],True),
('Media','event_switch_nil','新华社和中国日报社制作专栏，人民日报社与经济日报社审核稿件，央视新闻改由直播团队预告活动，双方协调采编。',[('新华社','ENT_GEN_0115'),('中国日报社','ENT_GEN_0153'),('人民日报社','ENT_GEN_0139'),('经济日报社','ENT_GEN_0154'),('央视新闻','ENT_GEN_0141')],'双方',[],True),
]
# Diverse three/four-member and cross-sentence cases.
EXTRA=[
('Energy','three_entity_positive','面向区域减排任务，国家能源局、国家发展改革委和生态环境部建立联络机制，三方分别确认督办节点。',[('国家能源局','ENT_GEN_0059'),('国家发展改革委','ENT_GEN_0089'),('生态环境部','ENT_GEN_0091')],'三方',['ENT_GEN_0059','ENT_GEN_0089','ENT_GEN_0091'],False),
('Finance','four_entity_positive','支付清算工作组由工商银行、建设银行、农业银行和中国银行共同组成，他们分工维护故障处置名册。',[('工商银行','ENT_GEN_0055'),('建设银行','ENT_GEN_0081'),('农业银行','ENT_GEN_0082'),('中国银行','ENT_GEN_0083')],'他们',['ENT_GEN_0055','ENT_GEN_0081','ENT_GEN_0082','ENT_GEN_0083'],False),
('Healthcare','quantity_mismatch_nil','中日友好医院、北京天坛医院和华西医院联合讨论方案，双方宣布执行。',[('中日友好医院','ENT_GEN_0111'),('北京天坛医院','ENT_GEN_0147'),('华西医院','ENT_GEN_0131')],'双方',[],True),
('Internet','quantity_mismatch_nil','华为、腾讯、阿里巴巴和小米举行产品会议，三方继续提交材料。',[('华为','ENT_GEN_0051'),('腾讯','ENT_GEN_0052'),('阿里巴巴','ENT_GEN_0053'),('小米','ENT_GEN_0073')],'三方',[],True),
]
ROWS += EXTRA
# Batch C: deliberately different discourse structures, domains and anaphors.
ROWS += [
('Manufacturing','institution_collective_positive','在设备改造验收现场，国家电网和南方电网说明供能条件，华能集团与大唐集团作为这些企业提交安全承诺。',[('国家电网','ENT_ENERGY_0001'),('南方电网','ENT_ENERGY_0002'),('华能集团','ENT_ENERGY_0003'),('大唐集团','ENT_ENERGY_0004')],'这些企业',['ENT_ENERGY_0003','ENT_ENERGY_0004'],False),
('PublicService','institution_collective_positive','政策听证资料显示，国家能源局和国家发展改革委先后陈述意见，生态环境部与国家统计局补充附件，上述单位将联合答复。',[('国家能源局','ENT_GEN_0059'),('国家发展改革委','ENT_GEN_0089'),('生态环境部','ENT_GEN_0091'),('国家统计局','ENT_GEN_0117')],'上述单位',['ENT_GEN_0091','ENT_GEN_0117'],False),
('Media','cross_sentence_positive','新华社与中国日报社完成采访。人民日报社和经济日报社随后校订版面。二者安排终审。',[('新华社','ENT_GEN_0115'),('中国日报社','ENT_GEN_0153'),('人民日报社','ENT_GEN_0139'),('经济日报社','ENT_GEN_0154')],'二者',['ENT_GEN_0139','ENT_GEN_0154'],False),
('Finance','cross_sentence_positive','工商银行和建设银行先完成接口登记。农业银行与中国银行随后建立清算清单。他们负责第二轮核验。',[('工商银行','ENT_GEN_0055'),('建设银行','ENT_GEN_0081'),('农业银行','ENT_GEN_0082'),('中国银行','ENT_GEN_0083')],'他们',['ENT_GEN_0082','ENT_GEN_0083'],False),
('Internet','product_system_positive','华为与腾讯展示基础服务，阿里巴巴和小米演示终端适配。它们将在发布窗口内维护该系统。',[('华为','ENT_GEN_0051'),('腾讯','ENT_GEN_0052'),('阿里巴巴','ENT_GEN_0053'),('小米','ENT_GEN_0073')],'它们',['ENT_GEN_0053','ENT_GEN_0073'],False),
('Transportation','cross_sentence_positive','中国国航和东方航空提交换季计划。海南航空与深圳地铁共同核准接驳安排。双方保留夜间服务。',[('中国国航','ENT_GEN_0135'),('东方航空','ENT_GEN_0136'),('海南航空','ENT_GEN_0152'),('深圳地铁','ENT_GEN_0151')],'双方',['ENT_GEN_0152','ENT_GEN_0151'],False),
('Healthcare','type_mismatch_nil','中日友好医院和北京天坛医院联合义诊。她们公布门诊安排。',[('中日友好医院','ENT_GEN_0111'),('北京天坛医院','ENT_GEN_0147')],'她们',[],True),
('PublicService','institution_collective_positive','国家能源局和生态环境部发布通告。这些机构解释执行细则。',[('国家能源局','ENT_GEN_0059'),('生态环境部','ENT_GEN_0091')],'这些机构',['ENT_GEN_0059','ENT_GEN_0091'],False),
('Manufacturing','duplicate_id_nil','华能集团与华能集团讨论设备升级，双方随后备案。',[('华能集团','ENT_ENERGY_0003'),('华能集团','ENT_ENERGY_0003')],'双方',[],True),
('Media','complex_nil','新华社和人民日报社先讨论栏目，中国日报社与央视新闻另行安排直播，双方发布说明。',[('新华社','ENT_GEN_0115'),('人民日报社','ENT_GEN_0139'),('中国日报社','ENT_GEN_0153'),('央视新闻','ENT_GEN_0141')],'双方',[],True),
('Energy','three_entity_positive','国家电网、南方电网与华能集团部署演练，大唐集团另设保障专班，他们提交报告。',[('国家电网','ENT_ENERGY_0001'),('南方电网','ENT_ENERGY_0002'),('华能集团','ENT_ENERGY_0003'),('大唐集团','ENT_ENERGY_0004')],'他们',['ENT_ENERGY_0001','ENT_ENERGY_0002','ENT_ENERGY_0003'],False),
('Healthcare','three_entity_positive','中日友好医院、北京天坛医院和华西医院形成转诊联盟，三方轮流值班。',[('中日友好医院','ENT_GEN_0111'),('北京天坛医院','ENT_GEN_0147'),('华西医院','ENT_GEN_0131')],'三方',['ENT_GEN_0111','ENT_GEN_0147','ENT_GEN_0131'],False),
('Finance','four_entity_positive','工商银行、建设银行、农业银行和中国银行共同签署服务公约，他们在季度末复盘。',[('工商银行','ENT_GEN_0055'),('建设银行','ENT_GEN_0081'),('农业银行','ENT_GEN_0082'),('中国银行','ENT_GEN_0083')],'他们',['ENT_GEN_0055','ENT_GEN_0081','ENT_GEN_0082','ENT_GEN_0083'],False),
('Internet','new_entity_no_switch_positive','华为和腾讯制定接口原则，阿里巴巴与小米负责终端适配；监管公告进入背景材料后，阿里巴巴与小米仍继续联调，双方提交日志。',[('华为','ENT_GEN_0051'),('腾讯','ENT_GEN_0052'),('阿里巴巴','ENT_GEN_0053'),('小米','ENT_GEN_0073')],'双方',['ENT_GEN_0053','ENT_GEN_0073'],False),
('Transportation','event_switch_nil','中国国航和东方航空完成票务协商，海南航空与深圳地铁签下接驳协议；随后国家统计局启动客流普查，双方保留原方案。',[('中国国航','ENT_GEN_0135'),('东方航空','ENT_GEN_0136'),('海南航空','ENT_GEN_0152'),('深圳地铁','ENT_GEN_0151'),('国家统计局','ENT_GEN_0117')],'双方',[],True),
('Manufacturing','institution_collective_positive','华能集团同大唐集团建立备件库，国家电网与南方电网提供检验标准。这些机构按月共享风险清单。',[('华能集团','ENT_ENERGY_0003'),('大唐集团','ENT_ENERGY_0004'),('国家电网','ENT_ENERGY_0001'),('南方电网','ENT_ENERGY_0002')],'这些机构',['ENT_ENERGY_0001','ENT_ENERGY_0002'],False),
]

def make(row,i):
 d,sc,text,ents,target,gold,nil=row; ms=[]
 for name,eid in ents:
  st=text.find(name); ms.append({'mention':name,'type':'ORG','char_start':st,'char_end':st+len(name),'entity_id':eid,'role':'name'})
 st=text.rfind(target); ms.append({'mention':target,'type':'PRON','char_start':st,'char_end':st+len(target),'role':'pronoun'})
 return {'id':f'CORE_HOLDOUT_V2_{i:03d}','subset':'blind_holdout_v2','domain':d,'scenario':sc,'difficulty':'hard','requires_discourse_reasoning':True,'expected_resolution_basis':'independent frozen holdout annotation','annotation_evidence':'single-review limitation; all offsets verified before first run','text':text,'mentions':ms,'expected_coreferences':[{'mention_index':len(ms)-1,'entity_ids':gold,'antecedent_indices':[],'is_collective':True,'is_nil':nil,**({'nil_reason':'ambiguous or cardinality-incompatible collective reference'} if nil else {})}]}

data={'dataset_name':'coreference_blind_holdout_v2','evaluation_scope':'blind_holdout','used_for_rule_development':False,'samples':[make(x,i+1) for i,x in enumerate(ROWS)]}
OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(len(data['samples']))
