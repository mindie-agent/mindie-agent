"""Probe actual summary input selection with existing synthetic fixtures only.

No model calls, source writes, private-history reads or network operations.
This measures availability in selected input, not summary quality or retrieval.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True, type=Path)
    parser.add_argument('--fixtures', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    fixtures = json.loads(args.fixtures.read_text(encoding='utf-8'))
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError('Expected nonempty synthetic fixture list')
    for item in fixtures:
        if item.get('synthetic') is not True:
            raise ValueError('Only explicitly synthetic fixtures are allowed')
        if not all(isinstance(item.get(key), str) for key in ('id', 'body', 'key_fact')):
            raise ValueError('Invalid fixture fields')
        if not isinstance(item.get('search_terms'), list):
            raise ValueError('Invalid search terms')
    sys.path.insert(0, str(args.core.resolve()))
    selector = importlib.import_module('mindie_knowledge.loop.summary_input')
    rows = []
    for item in fixtures:
        selected, coverage = selector.select_input(item['body'])
        terms = item['search_terms']
        if not all(isinstance(term, str) and term in item['body'] for term in terms):
            raise ValueError('Fixture terms must occur in the source')
        rows.append({
            'id': item['id'],
            'source_bytes': len(item['body'].encode('utf-8')),
            'request_bytes': selector.input_bytes(selected),
            'key_fact_selected': item['key_fact'] in selected['text'],
            'terms_selected': sum(term in selected['text'] for term in terms),
            'terms_total': len(terms),
            'coverage': coverage,
        })
    source = Path(selector.__file__).resolve()
    result = {
        'scope': 'synthetic input availability only',
        'native_model_calls': 0,
        'model_quality': None,
        'model_cost': None,
        'retrieval_quality': None,
        'selector': 'knowledge/' + source.relative_to(args.core.resolve()).as_posix(),
        'selector_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'fixtures_sha256': hashlib.sha256(args.fixtures.read_bytes()).hexdigest(),
        'cases': rows,
        'key_facts_selected': sum(row['key_fact_selected'] for row in rows),
        'cases_total': len(rows),
        'terms_selected': sum(row['terms_selected'] for row in rows),
        'terms_total': sum(row['terms_total'] for row in rows),
        'limitations': [
            'Adversarial fixture prevalence is not a production estimate.',
            'Missing selected input does not prove full-body search failure.',
            'Available input does not prove a model preserves its meaning.',
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in (
        'scope', 'native_model_calls', 'key_facts_selected', 'cases_total',
        'terms_selected', 'terms_total', 'selector_sha256')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
