"""Synthetic delivery probes. No real session, database, model or network use.

Run from the candidate knowledge checkout with that checkout and its tests on
PYTHONPATH. tests/conftest.py creates isolated HOME/config/state and disables
reporting. Output contains synthetic assertions and source hashes only.
"""
import conftest  # Isolate runtime paths before product imports.
import hashlib
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from test_shared_core import _confirmed_batch, PRODUCER
from mindie_knowledge.loop import documents
from mindie_knowledge.loop.store import Store, digest
from mindie_knowledge.loop.export import build_batch

results = []
with tempfile.TemporaryDirectory(prefix='mindie-audit-synthetic-') as td:
    p = Path(td)
    settings = conftest.write_settings(p / 'community.json', enabled=True, roots=[p])
    s = Store(p / 'store', 'test')
    try:
        doc, batch = _confirmed_batch(s, settings)
        staging = s.root / 'outbox' / 'staging' / batch
        with patch('shutil.os.scandir', side_effect=PermissionError('synthetic cleanup denied')):
            result = s.compact_confirmed(batch)
        results.append(dict(case='cleanup_denied', reported_removed_staging=result['staging'],
                            staging_still_exists=staging.is_dir()))
    finally:
        s.close()

with tempfile.TemporaryDirectory(prefix='mindie-audit-synthetic-') as td:
    p = Path(td)
    settings = conftest.write_settings(p / 'community.json', enabled=True, roots=[p])
    s = Store(p / 'store', 'test')
    try:
        doc, batch = _confirmed_batch(s, settings)
        updated, _ = s.append_observation(doc['entry_id'], 'Unsent additional observation',
            marker='c' * 32, producer=PRODUCER, generation=settings.generation)
        s.compact_confirmed(batch)
        with s._write_txn():
            s.db.execute('INSERT INTO transcript_tasks(task_key,entry_id,capture_id,body_digest,'
                'summary_status,summary_detail,updated,summary_due) VALUES(?,?,?,?,?,?,?,?)',
                ('task', doc['entry_id'], 'synthetic-capture', digest(updated['content']),
                 'complete', '', time.time(), 0))
        before = s.summary_ready(updated)
        remote = documents.make_entry(entry_id=doc['entry_id'], domain='test', kind='experience',
            title='Remote title', summary='Remote summary', content='Maintainer corrected the initial body')
        s.install_feed([remote], feed_ident='a' * 64)
        rebased = s.drafts_changed(generation=settings.generation)[0]
        results.append(dict(case='rebase_after_completed_summary', ready_before=before,
            ready_after=s.summary_ready(rebased), task_status=s.transcript_task('task')['summary_status'],
            pending_summaries=s.db.execute("SELECT count(*) FROM transcript_tasks WHERE summary_status='pending'").fetchone()[0],
            unsubmitted_observation_preserved='Unsent additional observation' in rebased['content'],
            build_batch=build_batch(s, settings=settings)))
    finally:
        s.close()

root = Path(conftest.__file__).resolve().parents[1]
paths = ['mindie_knowledge/loop/store.py', 'mindie_knowledge/loop/export.py',
         'mindie_knowledge/loop/transcript_capture.py', 'tests/test_shared_core.py']
print(json.dumps(dict(results=results, source_sha256={rel: hashlib.sha256((root / rel).read_bytes()).hexdigest()
                 for rel in paths}), indent=2))
