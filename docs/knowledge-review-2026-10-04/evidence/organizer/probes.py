"""Synthetic, local-only audit probes. Never invokes an external model or reads history.

Run from the knowledge candidate repository with its tests and source on PYTHONPATH.
The repository test fixture creates an isolated HOME, state, and diagnostic policy.
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import test_public_transcript as capture_cases
import test_history_import as import_cases
from mindie_knowledge.loop import transcript_capture
from mindie_knowledge.loop.export import build_batch
from mindie_knowledge.loop.summary_input import select_input
from mindie_knowledge.loop.transcript_redaction import ScannerUnavailable, redact
from mindie_knowledge.redact import scan_text

audit_candidate_root = Path.cwd().resolve().parent
SCANNER = '/opt/homebrew/bin/gitleaks'
results = {}
first = '-----BEGIN PRIVATE KEY-----\nSYNTHETICFIRSTBLOCK'
last = 'SYNTHETICTAILCANARY\n-----END PRIVATE KEY-----'
with tempfile.TemporaryDirectory(prefix='mindie-audit-boundary-') as root:
    fixture = capture_cases.pipeline.__wrapped__(Path(root), SCANNER)
    engine, store, source = next(fixture)
    try:
        engine.summary_command = ['synthetic-worker-never-spawned']
        capture_cases.append(source, first)
        capture_cases.process(engine, source, 'fragment-a')
        capture_cases.append(source, last)
        capture_cases.process(engine, source, 'fragment-b')
        body = store.drafts_changed()[0]['content']
        together, _ = redact(first + '\n\n' + last, executable=SCANNER, key=b'a' * 32)
        sent = []
        def native(command, payload, **kwargs):
            sent.append(json.loads(payload))
            return json.dumps(dict(title='Synthetic fragments', summary='Synthetic public boundary test.'))
        with patch.object(transcript_capture, 'bounded_run', native):
            capture_cases.run_summary(engine)
        results['cross_capture'] = dict(tail_saved='SYNTHETICTAILCANARY' in body,
            tail_in_whole_redaction='SYNTHETICTAILCANARY' in together,
            tail_in_worker_input='SYNTHETICTAILCANARY' in sent[0]['text'],
            export_batch_created=bool(build_batch(store, settings=engine._settings())))
    finally:
        fixture.close()

masked, _ = redact(first, executable=SCANNER, key=b'a' * 32)
results['placeholder_rescan'] = dict(placeholder=masked,
    rules=[finding.rule for finding in scan_text(masked)])

with tempfile.TemporaryDirectory(prefix='mindie-audit-repair-') as root:
    fixture = import_cases.case.__wrapped__(Path(root), SCANNER)
    case = next(fixture)
    engine, source = case
    try:
        import_cases.append(source, import_cases.message('Synthetic public result.'))
        engine.summary_command = [sys.executable, '-c', 'raise SystemExit(124)']
        import_cases.contribute(case)
        import_cases.summary_due(engine)
        engine.summary_command = [sys.executable, '-c', 'print(\'{"title":"Repaired","summary":"Synthetic result."}\')']
        repeated = import_cases.contribute(case)
        import_cases.summary_due(engine)
        results['explicit_repair'] = dict(reimport_status=repeated['status'],
            summary_status=engine.store.db.execute('SELECT summary_status FROM transcript_tasks').fetchone()[0],
            export_batch_created=bool(build_batch(engine.store, settings=engine._settings())))
    finally:
        fixture.close()

with tempfile.TemporaryDirectory(prefix='mindie-audit-postmodel-') as root:
    fixture = capture_cases.pipeline.__wrapped__(Path(root), SCANNER)
    engine, store, source = next(fixture)
    try:
        engine.summary_command = ['synthetic-worker-never-spawned']
        capture_cases.append(source, 'Synthetic public result.')
        capture_cases.process(engine, source, 'postmodel')
        calls = []
        invoked = [False]
        original = transcript_capture.redact
        def worker(*args, **kwargs):
            calls.append(1)
            invoked[0] = True
            return json.dumps(dict(title='Synthetic', summary='Synthetic result.'))
        def failed_scanner(*args, **kwargs):
            if invoked[0]:
                raise ScannerUnavailable('synthetic post-model scanner failure')
            return original(*args, **kwargs)
        states = []
        with patch.object(transcript_capture, 'bounded_run', worker):
            for _ in range(3):
                invoked[0] = False
                with patch.object(transcript_capture, 'redact', failed_scanner):
                    capture_cases.run_summary(engine)
                states.append(store.db.execute('SELECT summary_status FROM transcript_tasks').fetchone()[0])
            capture_cases.run_summary(engine)
        task = dict(store.db.execute('SELECT * FROM transcript_tasks').fetchone())
        results['postmodel_scanner_retry'] = dict(worker_calls=len(calls), interim_states=states,
            final_status=task['summary_status'], receipt_model_calls=json.loads(task['summary_detail'])['model_calls'],
            maintenance_attempts=store.db.execute('SELECT COUNT(*) FROM maintenance_attempts').fetchone()[0])
    finally:
        fixture.close()

body = ('Initial generic goal.\n' + 'waiting and plan\n' * 1500 +
        '\nOnly diagnosis: SYNTHETICMIDERROR kernel v2 failed.\n' +
        'waiting and plan\n' * 1500 + '\nDone for today.')
selected, coverage = select_input(body)
results['middle_selection'] = dict(middle_marker_selected='SYNTHETICMIDERROR' in selected['text'],
    source_chars=len(body), selected_chars=coverage['selected_chars'])
root = audit_candidate_root
files = ['knowledge/mindie_knowledge/loop/' + name + '.py' for name in
         ('transcript_capture', 'summary_input', 'history_import', 'engine', 'store', 'export', 'transcript_redaction')]
files += ['knowledge/mindie_knowledge/redact.py', 'codex/plugins/mindie-agent/scripts/agent_worker.py',
          'codex/plugins/mindie-agent/scripts/process_guard.py']
results['candidate_sha256'] = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
print(json.dumps(results, ensure_ascii=False, indent=2))
