"""Private artifact oracle. Never include this file in the consumer workspace."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys


def module(workspace, name):
    sys.path.insert(0, str(workspace))
    spec = importlib.util.spec_from_file_location(name, workspace / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def half(x):
    return struct.unpack('e', struct.pack('e', x))[0]


def grade(case, workspace):
    if case == 'dtype_reference':
        fn = module(workspace, 'numeric').apply
        for x in (.15, -.15, .125, .99, 1.125, 2.75, -3.25):
            for inv in (.121, .3, .71, 1.003):
                for w in (.333, .7, 1.3, 3.14):
                    expected = half(half(half(x) * inv) * half(w))
                    assert fn(x, inv, w) == expected, 'mismatched FP16 observable result'
    elif case == 'device_mapping':
        assert json.loads((workspace / 'placement.json').read_text()) == dict(physical_id=8, logical_id=2)
    elif case == 'withdrawn_speedup':
        result = json.loads((workspace / 'assessment.json').read_text())
        assert result['comparable'] is False
        assert result['speedup'] is None
        assert result['hardware_verified'] is False
        assert isinstance(result['reason'], str) and result['reason'].strip()
    elif case == 'fork_runtime':
        result = module(workspace, 'worker').run_jobs([1, 0, -2, 7])
        assert [r['value'] for r in result] == [2, 0, -4, 14]
        assert all(r['pid'] != os.getpid() and r['init_pid'] == r['pid'] for r in result)
        assert all(r['start_method'] == 'spawn' for r in result)
    elif case == 'obsolete_workaround':
        result = json.loads((workspace / 'config.json').read_text())
        assert result['runtime_version'] == '2.1' and result['legacy_workaround'] is False
    elif case == 'no_hit_slug':
        fn = module(workspace, 'slug').slug
        pairs = [('', ''), (' Hello,  WORLD! ', 'hello-world'), ('A__B---C', 'a-b-c'),
                 ('42 / Examples', '42-examples'), ('中文 Task', 'task')]
        assert all(fn(x) == expected for x, expected in pairs)
    else:
        raise ValueError('unknown case')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True)
    parser.add_argument('--workspace', required=True, type=Path)
    args = parser.parse_args()
    try:
        grade(args.case, args.workspace.resolve())
    except Exception as exc:
        print(json.dumps(dict(case=args.case, artifact_pass=False, error=type(exc).__name__, detail=str(exc))))
        raise SystemExit(1)
    print(json.dumps(dict(case=args.case, artifact_pass=True)))
