"""Read-only public corpus inventory; no models, network, private histories or repo edits."""
from pathlib import Path
import os
import hashlib, json, re, subprocess
from collections import defaultdict, Counter
from itertools import combinations
from difflib import SequenceMatcher

ROOT = Path(os.environ['MINDIE_EVAL_SOURCE_ROOT']).resolve()
OUT = Path(os.environ['MINDIE_EVAL_OUTPUT_DIR']).resolve()
from mindie_knowledge.materials.store import _parse_manifest, _parse_block
from mindie_knowledge.materials.provenance import citations

rows=[]
for manifest in sorted((ROOT/'content/tasks').glob('*/index.md')):
    header=_parse_manifest(manifest.read_text(encoding='utf-8'),'vllm-ascend')
    for d in header['blocks']:
        p=manifest.parent/'blocks'/(d['block_id']+'.md')
        raw=p.read_bytes(); body=_parse_block(raw.decode('utf-8'),d)
        rows.append(dict(task=header['task_id'],block=d['block_id'],title=header['entry']['title'],body=body,
                         body_bytes=len(body.encode()),file_bytes=len(raw),body_sha256=hashlib.sha256(body.encode()).hexdigest(),
                         file_sha256=hashlib.sha256(raw).hexdigest(),cites=citations(body),conditions=header['entry']['conditions']))

def dup_report(key):
    groups=defaultdict(list)
    for r in rows: groups[key(r)].append(r)
    duplicates=[g for g in groups.values() if len(g)>1]
    return dict(groups=len(duplicates),duplicate_members=sum(len(g)-1 for g in duplicates),
                recoverable_body_bytes=sum(sum(r['body_bytes'] for r in g[1:]) for g in duplicates),
                identities=[[r['task']+':'+r['block'] for r in g] for g in duplicates])

# n-gram overlap is a candidate heuristic only, not semantic equivalence.
def normalized(body): return re.sub(r'\s+',' ',body).strip()
def grams(body):
    text=normalized(body)
    return {text[i:i+5] for i in range(len(text)-4)}
for r in rows:r['grams']=grams(r['body'])
pairs=[]
for a,b in combinations(rows,2):
    union=a['grams']|b['grams']; intersection=a['grams']&b['grams']
    j=len(intersection)/len(union) if union else 1
    containment=len(intersection)/min(len(a['grams']),len(b['grams'])) if min(len(a['grams']),len(b['grams'])) else 0
    pairs.append(dict(a=a['task'],b=b['task'],a_block=a['block'],b_block=b['block'],jaccard=j,shorter_containment=containment,
                      same_task=a['task']==b['task'],a_title=a['title'],b_title=b['title']))
paragraphs=Counter()
paragraph_bytes={}
for r in rows:
    for para in re.split(r'\n\s*\n',r['body']):
        para=para.strip()
        if para:
            paragraphs[para]+=1;paragraph_bytes[para]=len(para.encode())
repeated=sorted([dict(count=n,bytes=paragraph_bytes[p],text=p[:160]) for p,n in paragraphs.items() if n>1],key=lambda x:x['bytes']*(x['count']-1),reverse=True)
report=dict(scope='public bytes and lexical overlap; neither task utility nor semantic equivalence',
            commits={d:subprocess.check_output(['git','-C',str(ROOT/d),'rev-parse','HEAD'],text=True).strip() for d in ('knowledge','content','codex','design')},
            tasks=len({r['task'] for r in rows}),blocks=len(rows),body_bytes=sum(r['body_bytes'] for r in rows),block_file_bytes=sum(r['file_bytes'] for r in rows),
            duplicate_file_bytes=dup_report(lambda r:r['file_sha256']),duplicate_body_bytes=dup_report(lambda r:r['body_sha256']),
            duplicate_whitespace_normalized_bodies=dup_report(lambda r:normalized(r['body'])),
            literal_full_citations=sum(len(r['cites']) for r in rows),citation_blocks=sum(bool(r['cites']) for r in rows),
            pair_count=len(pairs),pairs_over_0_5=sum(p['jaccard']>=.5 for p in pairs),pairs_over_0_8=sum(p['jaccard']>=.8 for p in pairs),
            top_lexical_pairs=sorted(pairs,key=lambda p:p['jaccard'],reverse=True)[:12],
            repeated_paragraph_occurrences=sum(n-1 for p,n in paragraphs.items() if n>1),
            theoretical_removed_paragraph_bytes=sum(paragraph_bytes[p]*(n-1) for p,n in paragraphs.items() if n>1),
            top_repeated_paragraphs=repeated[:12],
            blocks_inventory=[{k:v for k,v in r.items() if k not in ('body','grams')} for r in rows])
(OUT/'public-inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('blocks_inventory','top_repeated_paragraphs')},ensure_ascii=False,indent=2))
print('top_repeated_paragraphs',json.dumps(repeated[:5],ensure_ascii=False))
