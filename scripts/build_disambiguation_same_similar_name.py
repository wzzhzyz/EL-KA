"""Build 500 KB-grounded same/similar-name disambiguation samples."""
from __future__ import annotations
import difflib,json
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; KB=ROOT/'data/kb/energy_entities.json'; OUT=ROOT/'data/eval/disambiguation_same_similar_name_test.json'
entities=json.loads(KB.read_text(encoding='utf-8'))['entities']; ids={e['entity_id'] for e in entities}
def names(e): return [e['entity_name'],e.get('abbreviation','')]+[a.get('name','') for a in e.get('aliases',[])]
def alias(e,variant):
    vals=[x for x in names(e) if len(x.strip())>=2]; vals=list(dict.fromkeys(vals)); return vals[min(variant,len(vals)-1)]
def sim(a,b): return max(difflib.SequenceMatcher(None,x,y).ratio() for x in names(a) for y in names(b) if x and y)
def candidates(e):
    ranked=sorted((sim(e,o),o['entity_id']) for o in entities if o['entity_id']!=e['entity_id'])
    return [e['entity_id']]+[x[1] for x in ranked[-3:][::-1]]
def text(e,m,v):
    kws=e.get('keywords') or e.get('tags') or [e.get('industry','相关领域')]; a,b=(kws+['业务'])[:2]; ind=e.get('industry','相关领域'); summ=e.get('summary','')
    forms=[f'在{ind}项目中，{m}围绕{a}提出实施方案，相关职责由该标准实体承担。',f'公开资料显示，{m}重点开展{a}与{b}工作；此处需与名称相近候选结合行业信息区分。',f'{m}的业务材料提到{a}能力和{b}场景，语境指向该知识库实体而不是相似机构。']
    return forms[v%3] if not summ else forms[v%3]+' '+summ[:42]
samples=[]; aliases=defaultdict(set)
for e in entities:
    for n in names(e):
        if n: aliases[n].add(e['entity_id'])
collision_count=sum(len(v)>1 for v in aliases.values())
for i,e in enumerate(entities):
    for v in range(3):
        m=alias(e,v); level=('easy','medium','hard')[v]
        samples.append({'id':f'DISAMB_SIM_{len(samples)+1:06d}','text':text(e,m,v),'mention':m,'gold_entity':e['entity_id'],'candidate_entities':candidates(e),'confidence_level':level,'kb_status':'in_kb','expected_bge_score_range':{'easy':[0.8,1.0],'medium':[0.65,0.9],'hard':[0.45,0.78]}[level],'expected_nil':False,'reason':f'候选中仅 {e["entity_id"]} 的行业、关键词和摘要与上下文一致；其余候选仅名称或别名相似。','scenario':'严格同名异指' if len(aliases[m])>1 else ('简称/缩写竞争' if m==e.get('abbreviation') else '相似名异指-上下文消歧')})
# Add 26 high-similarity NIL mentions derived from a real alias plus a non-KB organisational suffix.
for e in entities[:26]:
    base=alias(e,0); m=base+'创新联合体'
    samples.append({'id':f'DISAMB_SIM_{len(samples)+1:06d}','text':f'行业公告称，{m}正在筹备专项试点；该名称不对应当前知识库中的标准实体。','mention':m,'gold_entity':None,'candidate_entities':candidates(e)[1:],'confidence_level':'hard','kb_status':'nil','expected_bge_score_range':[0.0,0.46],'expected_nil':True,'nil_reason':'entity_not_in_kb','reason':f'{m} 不在知识库实体名或别名中；候选仅与 {base} 字面相近，缺少可验证实体依据。','scenario':'高相似NIL'})
assert len(samples)==500
stat={'total_cases':len(samples),'scenario_distribution':dict(Counter(x['scenario'] for x in samples)),'confidence_distribution':dict(Counter(x['confidence_level'] for x in samples)),'nil_count':sum(x['expected_nil'] for x in samples),'in_kb_count':sum(not x['expected_nil'] for x in samples),'average_candidate_count':round(sum(len(x['candidate_entities']) for x in samples)/len(samples),2),'strict_same_name_conflict_alias_count':collision_count}
data={'dataset_name':'same_similar_name_disambiguation_test','version':'1.0','purpose':'基于当前运行知识库构造的同名/相似名实体消歧验证集','nil_threshold':0.65,'bge_llm_trigger_threshold':0.65,'kb_reference':'data/kb/energy_entities.json','total_cases':len(samples),'samples':samples,'statistics':stat}
OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(stat,ensure_ascii=False))
