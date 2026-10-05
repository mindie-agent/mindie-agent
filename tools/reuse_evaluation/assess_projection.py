"""Evaluate response projections only. Does not change product or remove material."""
from pathlib import Path
import os
import subprocess
import json,tempfile,base64,hashlib
from contextlib import closing
from mindie_knowledge.materials import MaterialStore,validate_package_files
from mindie_knowledge.materials.provenance import group_matches, _encode_continuation
import mindie_knowledge.materials.reme_index as index_module
from copy import deepcopy
ROOT=Path(os.environ['MINDIE_EVAL_SOURCE_ROOT']).resolve()/'content'
OUT=Path(os.environ['MINDIE_EVAL_OUTPUT_DIR']).resolve()

def size(obj): return len(json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode())
def cursor(query,anchor,offset,after=None):
    if offset:
        return _encode_continuation(query,{},"0"*64,anchor,after)
    obj=dict(schema='evaluation-projection/1',query=query,conditions={},corpus='0'*64,anchor=anchor,offset=offset)
    return base64.urlsafe_b64encode(json.dumps(obj,separators=(',',':')).encode()).decode().rstrip('=')
def project(groups,query,mode):
    out=[]
    for g in groups:
        row={k:v for k,v in g.items() if k not in ('related','related_count','related_next')}
        members=g['related'];row['related_count']=len(members)
        if mode=='current_full_2':
            row['related']=members[:2];consumed=min(2,len(members))
        elif mode=='anchor_only':
            consumed=0
        elif mode=='compact_excerpt_2':
            fields=('entry_id','ref','feedback_ref','excerpt','cites','conditions','match_basis','score')
            row['related']=[{key:m[key] for key in fields} for m in members[:2]]
            consumed=min(2,len(members)) # continuation skips seen previews; refs read their full blocks
        else: raise ValueError(mode)
        row['related_next']=cursor(query,g['ref'],consumed,members[consumed-1]['ref'] if consumed else None) if consumed<len(members) else None
        out.append(row)
    return out

def expansion(groups,query,mode):
    pages=[]
    for g in groups:
        start=2 if mode in ('current_full_2','compact_excerpt_2') else 0
        if len(g['related'])>start:
            # Use the existing continuation envelope, which repeats anchor metadata.
            pages.append(dict(g,related_count=len(g['related']),related=g['related'][start:],related_next=None))
    return pages

def collect(store,query):
    captured=[]
    original=index_module.group_matches
    def trace(matches,tasks,domain):
        groups=original(matches,tasks,domain)
        captured.extend(deepcopy(groups))
        return groups
    index_module.group_matches=trace
    try:
        response=store.search(query,limit=5)
    finally:
        index_module.group_matches=original
    full={group['ref']:group for group in captured}
    return [full[group['ref']] for group in response]

public={}
with tempfile.TemporaryDirectory(prefix='mindie-public-projection-') as td:
    with closing(MaterialStore(Path(td),'vllm-ascend')) as store:
        packages=[]
        for d in sorted((ROOT/'tasks').iterdir()):
            packages.append(validate_package_files({str(p.relative_to(d)):p.read_text(encoding='utf-8') for p in d.rglob('*.md')},'vllm-ascend'))
        store.install_packages(packages,source_revision=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip())
        for q in ['Qwen3-0.6B NPU','Qwen3-0.6B token 1.201','RMSNorm FP16 BF16']:
            groups=collect(store,q);row={}
            for mode in ('current_full_2','anchor_only','compact_excerpt_2'):
                p=project(groups,q,mode);e=expansion(groups,q,mode)
                row[mode]=dict(initial_json_bytes=size(p),all_expansions_json_bytes=sum(size(page) for page in e),
                               expand_calls=len(e),total_bytes_if_all_related_expanded=size(p)+sum(size(page) for page in e))
            public[q]=row

# Valid result-shaped synthetic groups isolate the projection from ranking.
# Known ranks are fixture inputs; these are not measured ranking performance.
def ident(s):return hashlib.sha256(s.encode()).hexdigest()
def hit(name,body,score=1):
    t=ident(name)
    return dict(entry_id=t,revision='a'*64,source='feed',kind='experience',title='Synthetic observation',summary='A fallible index.',
                conditions={},score=score,excerpt=body[:1200],block_id=ident(name+'block'),block_title='Synthetic block',block_summary='A fallible index.',
                navigation='Reference material.',source_range={'synthetic':True},ref='mindie://demo/'+t+'/blocks/'+ident(name+'block')+'@'+'b'*64,
                task_ref='mindie://demo/'+t,feedback_ref='mindie://demo/'+t+'@'+'a'*64,match_basis='body',cites=[])

def case(name,fact,position=0,tail=False,independent=False):
    source=hit(name+'source','RMSNorm float16 contiguous matched the reference.',10)
    correction_body=('Routine progress. '*100 if tail else '')+fact
    correction=hit(name+'correction',correction_body,9-position)
    echoes=[hit(name+'echo'+str(i),'RMSNorm float16 contiguous quoted the same original result; no new execution.',9-i) for i in range(3)]
    related=echoes[:];related.insert(position,correction)
    g=dict(source,related=related,group_score=10,group_basis='citation')
    groups=[g]
    if independent:
        g['related']=echoes
        groups.append(dict(correction,related=[],group_score=correction['score'],group_basis='task'))
    return dict(name=name,query='RMSNorm disjoint-stride' if independent else 'RMSNorm float16 contiguous',fact=fact,groups=groups,correction_ref=correction['ref'],full_bodies={correction['ref']:correction_body},independent=independent)

cases=[
 case('same_terms_failed_reuse_first','Correction: the contiguous float16 reuse failed; the proposed fix did not work.',0),
 case('same_terms_failed_reuse_fourth','Correction: the contiguous float16 reuse failed; the proposed fix did not work.',3),
 case('limited_validation_first','Only mock tests passed; hardware execution remains unverified.',0),
 case('retracted_speedup_fourth','The speedup claim was withdrawn after unequal request counts were found.',3),
 case('same_terms_tail_correction','Late correction: the earlier success claim was false.',0,tail=True),
 case('new_condition_independent','RMSNorm disjoint-stride failed on a new shape; the old result does not cover it.',0,independent=True),
]
synthetic=[]
for c in cases:
    row=dict(case=c['name'],fact=c['fact'],ranking_fixture=True,modes={})
    for mode in ('current_full_2','anchor_only','compact_excerpt_2'):
        p=project(c['groups'],c['query'],mode)
        visible=json.dumps(p,ensure_ascii=False)
        e=expansion(c['groups'],c['query'],mode)
        after=visible+json.dumps(e,ensure_ascii=False)
        row['modes'][mode]=dict(initial_fact_visible=c['fact'] in visible,
                               after_all_related_metadata_fact_visible=c['fact'] in after,
                               correction_ref_initially_visible=c['correction_ref'] in visible,
                               correction_ref_reachable_after_expand=c['correction_ref'] in after,
                               full_block_fact_available=c['fact'] in c['full_bodies'][c['correction_ref']],
                               initial_json_bytes=size(p))
    synthetic.append(row)
summary={mode:{key:sum(r['modes'][mode][key] for r in synthetic) for key in (
    'initial_fact_visible','after_all_related_metadata_fact_visible','correction_ref_initially_visible',
    'correction_ref_reachable_after_expand','full_block_fact_available')} for mode in ('current_full_2','anchor_only','compact_excerpt_2')}
report=dict(scope='Response projection byte and evidence-availability evaluation only; zero consumer agents or model calls',public=public,
            synthetic_case_count=len(cases),synthetic_summary=summary,synthetic_cases=synthetic,
            limitations=['Synthetic result ranks are chosen fixtures, not frequency estimates.',
                         'UTF-8 bytes are not model tokens or billable cost.',
                         'Compact excerpts do not certify truth and cannot expose facts outside the excerpt.',
                         'Cursor reachability is not initial visibility or successful consumer reuse.',
                         'Full and compact projections use production cursor shape with a normalized corpus digest; anchor-only uses an evaluation-only offset=0 cursor.',
                         'Continuation returns remaining metadata; full bodies for already previewed matches are read using their preserved refs.'])
(OUT/'projection-fixtures.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
(OUT/'projection-evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='synthetic_cases'},ensure_ascii=False,indent=2))
