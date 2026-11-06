"""Read official GitHub tag provenance for a pinned release dependency.

[Role] Compare a remote tag's dereferenced commit with the requested source.
[Invariants] Release names and local tags cannot substitute for remote source identity.
[Timeouts & Locks] One 15s budget covers at most five read-only gh API requests.
[Side-Effect Policy] Reads public GitHub Git objects; no release or ref writes.
"""
import json
import subprocess
import time
from urllib.parse import quote


def verify_tag_commit(gh, repository, tag, expected, *, timeout=15.0):
    deadline = time.monotonic() + timeout
    path = f'repos/{repository}/git/ref/tags/{quote(tag, safe="")}'
    for _ in range(5):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return [f'{repository}: remote tag verification timed out for {tag}']
        result = subprocess.run([gh, 'api', path], capture_output=True, text=True,
            encoding='utf-8', check=False, timeout=remaining,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            return [f'{repository}: cannot resolve remote tag {tag}: {result.stderr.strip()[:300]}']
        target = json.loads(result.stdout)['object']
        if target['type'] == 'commit':
            return ([] if target['sha'] == expected else [
                f'{repository}: remote tag {tag} resolves to {target["sha"]}, expected pinned source {expected}'])
        if target['type'] != 'tag':
            return [f'{repository}: remote tag {tag} does not identify a commit']
        path = f'repos/{repository}/git/tags/{target["sha"]}'
    return [f'{repository}: remote tag {tag} exceeds the dereference limit']
