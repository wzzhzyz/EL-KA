"""One-time frozen OFF/ON evaluation for Blind Holdout v2."""
from __future__ import annotations
import hashlib,json,subprocess,sys
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(R)); D=R/'data/eval/coreference_blind_holdout_v2.json'
from entity_linker.coreference import RuleBasedCoreferenceResolver
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def ok(x,e): return x['is_nil']==e['is_nil'] and (x['is_nil'] or set(x['entity_ids'])==set(e['entity_ids']))
def metric(rows,k):
 p=[x for x in rows if not x['gold_is_nil']];n=[x for x in rows if x['gold_is_nil']]
 return {'correct':sum(x[k]['correct'] for x in rows),'total':len(rows),'positive_correct':sum(x[k]['correct'] for x in p),'positive_total':len(p),'nil_correct':sum(x[k]['correct'] for x in n),'nil_total':len(n),'false_positive':sum(x['gold_is_nil'] and not x[k]['is_nil'] for x in rows),'false_nil':sum(not x['gold_is_nil'] and x[k]['is_nil'] for x in rows),'wrong_entity_set':sum(not x['gold_is_nil'] and not x[k]['is_nil'] and not x[k]['correct'] for x in rows)}
d=json.loads(D.read_text(encoding='utf-8')); freeze={'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'time_utc':datetime.now(timezone.utc).isoformat(),'dataset_sha256':sha(D),'collective_ambiguity_sha256':sha(R/'entity_linker/collective_ambiguity.py'),'coreference_sha256':sha(R/'entity_linker/coreference.py'),'default_enabled':False,'frozen_evidence_max':2}
rows=[]
for s in d['samples']:
 e=s['expected_coreferences'][0];i=e['mention_index']; off=RuleBasedCoreferenceResolver().resolve(s['mentions'],text=s['text'])[i].to_dict();on=RuleBasedCoreferenceResolver(enable_collective_ambiguity_rejection=True).resolve(s['mentions'],text=s['text'])[i].to_dict()
 def f(x): return {'entity_ids':x['entity_ids'],'is_nil':x['is_nil'],'rule':x['rule'],'correct':ok(x,e),'trace':x.get('debug_metadata',{})}
 rows.append({'sample_id':s['id'],'domain':s['domain'],'scenario':s['scenario'],'gold_entity_ids':e['entity_ids'],'gold_is_nil':e['is_nil'],'off':f(off),'on':f(on)})
report={'freeze':freeze,'discipline':'one_time_off_on_evaluation_no_post_run_changes','single_review_limitation':True,'metrics':{'off':metric(rows,'off'),'on':metric(rows,'on')},'rows':rows}
for group in ('domain','scenario'):
 g=defaultdict(list)
 for x in rows:g[x[group]].append(x)
 report[group+'_metrics']={a:{'off':metric(b,'off'),'on':metric(b,'on')} for a,b in g.items()}
bad=[]
for x in rows:
 for mode in ('off','on'):
  if not x[mode]['correct']:
   typ='false_rejection' if not x['gold_is_nil'] and x[mode]['is_nil'] else 'missed_ambiguity' if x['gold_is_nil'] else 'wrong_entity_set'
   bad.append({**x,'mode':mode,'error_type':typ})
(R/'reports/coreference_blind_holdout_v2_result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(R/'reports/coreference_blind_holdout_v2_badcases.json').write_text(json.dumps(bad,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
m=report['metrics']; lines=['# Blind Holdout v2 一次性 OFF / ON 结果','',f"冻结：`{freeze['git_head']}`；数据未参与规则开发，运行后未修改数据、gold、算法或阈值。",'', '|模式|总体|正例|NIL|FP|FN|','|-|-:|-:|-:|-:|-:|']
for k in ('off','on'):
 x=m[k];lines.append(f"|{k.upper()}|{x['correct']}/{x['total']}|{x['positive_correct']}/{x['positive_total']}|{x['nil_correct']}/{x['nil_total']}|{x['false_positive']}|{x['false_nil']}|")
lines+=['','single-review limitation；本次为一次性评测。']
(R/'reports/coreference_blind_holdout_v2_result.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
delta=m['on']['correct']-m['off']['correct']; conclusion='CONSIDER_DEFAULT_ENABLE_AFTER_REVIEW' if m['on']['correct']/m['on']['total']>=.8 and delta>=5 and m['on']['positive_correct']==m['off']['positive_correct'] else 'KEEP_EXPERIMENTAL_BRANCH_DISABLED_BY_DEFAULT' if delta>=4 and m['on']['nil_correct']>=m['off']['nil_correct'] else 'ROLL_BACK_EXPERIMENTAL_BRANCH'
(R/'reports/coreference_blind_holdout_v2_off_on_comparison.md').write_text(f'# OFF / ON 对比\n\n- ON 相对 OFF：{delta:+d}。\n- 结论：**{conclusion}**。\n- 不自动修改默认配置。\n',encoding='utf-8')
print(json.dumps({'off':m['off'],'on':m['on'],'conclusion':conclusion},ensure_ascii=False))
