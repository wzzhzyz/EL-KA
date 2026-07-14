"""Validate the standalone same/similar-name disambiguation set."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data/eval/disambiguation_same_similar_name_test.json'; K=ROOT/'data/kb/energy_entities.json'
d=json.loads(D.read_text(encoding='utf-8')); ss=d['samples']; ids={e['entity_id'] for e in json.loads(K.read_text(encoding='utf-8'))['entities']}; required={'id','text','mention','gold_entity','candidate_entities','confidence_level','kb_status','expected_bge_score_range','expected_nil','reason','scenario'}
errors=[]; seen=set()
for x in ss:
    key=(x['mention'],x['text']);
    if not required<=set(x): errors.append((x.get('id'),'missing_fields'))
    if key in seen: errors.append((x['id'],'duplicate')); seen.add(key)
    if len(x.get('candidate_entities',[]))<2 or any(i not in ids for i in x.get('candidate_entities',[])): errors.append((x['id'],'invalid_candidates'))
    if x['expected_nil']:
        if x['gold_entity'] is not None or not x.get('nil_reason'): errors.append((x['id'],'invalid_nil'))
    elif x['gold_entity'] not in ids or x['gold_entity'] not in x['candidate_entities']: errors.append((x['id'],'invalid_gold'))
report={'samples':len(ss),'scenario_distribution':dict(Counter(x['scenario'] for x in ss)),'confidence_distribution':dict(Counter(x['confidence_level'] for x in ss)),'nil_count':sum(x['expected_nil'] for x in ss),'average_candidate_count':round(sum(len(x['candidate_entities']) for x in ss)/len(ss),2),'errors':errors}
statistics=d.get('statistics', {})
for field in ('total_cases','scenario_distribution','confidence_distribution','nil_count','in_kb_count','average_candidate_count'):
    if statistics.get(field) != ({
        'total_cases': len(ss),
        'scenario_distribution': report['scenario_distribution'],
        'confidence_distribution': report['confidence_distribution'],
        'nil_count': report['nil_count'],
        'in_kb_count': len(ss)-report['nil_count'],
        'average_candidate_count': report['average_candidate_count'],
    })[field]:
        errors.append(('statistics', f'mismatch:{field}'))
print(json.dumps(report,ensure_ascii=False,indent=2)); raise SystemExit(1 if errors or d['total_cases']!=len(ss) else 0)
