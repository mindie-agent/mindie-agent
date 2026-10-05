"""Run public/synthetic resource evaluations without models or repository writes."""
import argparse,json,os,platform,subprocess,sys,time
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root',type=Path,required=True,help='Sibling knowledge, content, codex and design Git checkouts')
p.add_argument('--output',type=Path,required=True,help='New evaluation output directory outside the repositories')
a=p.parse_args();source=a.source_root.resolve();output=a.output.resolve()
for repo in ('knowledge','content','codex','design'):
 if not (source/repo/'.git').exists():raise SystemExit('Missing expected Git checkout: '+repo)
 if output==source/repo or source/repo in output.parents:raise SystemExit('Output must be outside reviewed repositories')
output.mkdir(parents=True,exist_ok=False)
env=dict(os.environ,MINDIE_EVAL_SOURCE_ROOT=str(source),MINDIE_EVAL_OUTPUT_DIR=str(output),PYTHONPATH=str(source/'knowledge'))
started=time.time();runs=[]
for script in ('assess_public.py','assess_retrieval.py','assess_projection.py'):
 start=time.monotonic()
 r=subprocess.run([sys.executable,str(Path(__file__).with_name(script))],env=env,capture_output=True,text=True,timeout=120)
 (output/(script+'.stdout.txt')).write_text(r.stdout,encoding='utf-8')
 (output/(script+'.stderr.txt')).write_text(r.stderr,encoding='utf-8')
 runs.append(dict(script=script,returncode=r.returncode,elapsed_seconds=time.monotonic()-start))
 if r.returncode:
  print(r.stderr,file=sys.stderr);break
report=dict(started_unix=started,python=sys.version,platform=platform.platform(),runtime_mode='exact source import in existing environment; not native installed acceptance',
 native_model_calls=0,network_calls=0,private_transcript_reads=0,product_files_modified=0,runs=runs)
(output/'execution.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
raise SystemExit(0 if len(runs)==3 and all(x['returncode']==0 for x in runs) else 1)
