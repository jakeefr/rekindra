"""Summarize native Hermes evidence without printing image payloads."""
import argparse
import json
from pathlib import Path


def summarize(path):
    row = {'case': path.name.removesuffix('-events.jsonl'), 'tools': [], 'artifacts': [], 'results': []}
    for line in path.read_text(encoding='utf-8-sig', errors='replace').splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue  # A live writer can leave a partial last event.
        if event.get('type') == 'tool_use':
            row['tools'].append(event.get('name'))
        elif event.get('type') == 'tool_result' and event.get('name', '').startswith('rekindra_'):
            value = event.get('output')
            try:
                result = json.JSONDecoder().raw_decode(value.lstrip())[0] if isinstance(value, str) else value
            except ValueError:
                result = {'error': 'Non-JSON tool result'}
            if isinstance(result, dict):
                if isinstance(result.get('result'), dict):
                    result = result['result']
                row['artifacts'].append({'tool': event['name'], **{k: v for k, v in result.items() if k in ('project_id', 'plan_id', 'path', 'plan_path', 'preview_path', 'error', 'success')}})
        elif event.get('type') == 'result':
            row['results'].append({k: event.get(k) for k in ('session_id', 'exit_code', 'duration_ms', 'error', 'text')})
    return row


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('runs', type=Path)
    parser.add_argument('--compact', action='store_true')
    args = parser.parse_args()
    rows = [summarize(p) for p in sorted(args.runs.glob('*-events.jsonl')) if 'budget-rejection' not in p.name]
    (args.runs/'summary.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    for row in rows:
        if args.compact:
            print(row['case'], 'calls:', len(row['tools']), 'worlds:', sum(a['tool']=='rekindra_create_world' and 'path' in a for a in row['artifacts']), 'previews:', sum(a['tool']=='rekindra_preview' and 'path' in a for a in row['artifacts']), 'last:', row['tools'][-1:] or ['none'], 'finished:', bool(row['results']))
        else:
            print(row['case'], 'tools:', ', '.join(row['tools']), 'finished:', bool(row['results']))
        for item in ([] if args.compact else row['artifacts']):
            if item['tool'] != 'rekindra_inspect':
                print(json.dumps(item))
        for result in ([] if args.compact else row['results']):
            print(json.dumps(result))
