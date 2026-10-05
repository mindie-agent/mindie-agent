"""Public-corpus retrieval ablation in a disposable store. No product edits or models."""
from pathlib import Path
import os
import subprocess
import json,tempfile,time,statistics
from contextlib import closing
from mindie_knowledge.materials import MaterialStore,validate_package_files
from mindie_knowledge.materials.references import block_ref
from mindie_knowledge.materials.provenance import group_matches,resolve_citations
import mindie_knowledge.materials.reme_index as index_module
ROOT=Path(os.environ['MINDIE_EVAL_SOURCE_ROOT']).resolve()/'content'
OUT=Path(os.environ['MINDIE_EVAL_OUTPUT_DIR']).resolve()
packages=[]
for d in sorted((ROOT/'tasks').iterdir()):
    files={str(p.relative_to(d)):p.read_text(encoding='utf-8') for p in d.rglob('*.md')}
    packages.append(validate_package_files(files,'vllm-ascend'))

def task_only(matches,tasks,domain):
    originals={x['ref']:x['_cites'] for x in matches}
    groups=group_matches([dict(x,_cites=[]) for x in matches],tasks,domain)
    for g in groups:
        for m in [g,*g['related']]:m['cites']=resolve_citations(originals[m['ref']],tasks,domain)
    return groups

def payload_stats(groups):
    matches=[m for g in groups for m in [g,*g['related']]]
    return dict(groups=len(groups),visible_matches=len(matches),response_json_utf8_bytes=len(json.dumps(groups,ensure_ascii=False,separators=(',',':')).encode()),
                excerpt_utf8_bytes=sum(len(m['excerpt'].encode()) for m in matches),
                anchors=[g['entry_id'] for g in groups],has_more_related=any(g['related_next'] for g in groups))

report=dict(scope='same current block candidates, same-task grouping retained; experimental citation edges off vs current; resource exposure, not completed task benefit',queries={})
with tempfile.TemporaryDirectory(prefix='mindie-public-retrieval-assessment-') as td:
    with closing(MaterialStore(Path(td),'vllm-ascend')) as store:
        store.install_packages(packages,source_revision=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip())
        for query in ['Qwen3-0.6B NPU','Qwen3-0.6B token 1.201','RMSNorm FP16 BF16']:
            row={}
            for name,grouping in [('citation_edges_off',task_only),('current',group_matches)]:
                index_module.group_matches=grouping
                store.search(query,limit=20)
                times=[]
                for _ in range(9):
                    t=time.perf_counter_ns();r=store.search(query,limit=5);times.append((time.perf_counter_ns()-t)/1e6)
                row[name]=dict(payload_stats(r),warm_query_median_ms=statistics.median(times),warm_query_min_ms=min(times),warm_query_max_ms=max(times),runs=9)
                row[name]['all_group_count']=len(store.search(query,limit=20))
            report['queries'][query]=row
        index_module.group_matches=group_matches
        task=next(h for h in store.visible_tasks().values() if len(h['blocks'])==3)
        all_bytes=sum(len(store._read_block(task['task_id'],b).encode()) for b in task['blocks'])
        selected=task['blocks'][1]
        body_reads=[]
        orig=store._read_block
        def traced(task_id,descriptor):
            body_reads.append(descriptor['block_id']);return orig(task_id,descriptor)
        store._read_block=traced
        one=store.read_current(task['task_id'],source='feed',revision=task['entry']['revision'],block_id=selected['block_id'],sha256=selected['sha256'])
        report['three_block_read']=dict(task=task['task_id'],selected_block=selected['block_id'],actual_body_reads=len(body_reads),
             selected_body_utf8_bytes=len(one['content'].encode()),whole_task_body_utf8_bytes=all_bytes,
             fraction_of_task_read=len(one['content'].encode())/all_bytes,
             one_block_tasks=sum(len(t['blocks'])==1 for t in store.visible_tasks().values()))
(OUT/'retrieval-ablation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
