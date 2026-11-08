"""Export the last authored world after a native run; never label it artistically accepted."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from summarize_acceptance_runs import summarize

parser = argparse.ArgumentParser()
parser.add_argument('events', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
row = summarize(args.events)


def world_html(item):
    """HTML for a created world, or for the plan a preview rendered (covers revise-only runs)."""
    if item['tool'] == 'rekindra_create_world' and item.get('path'):
        return item['path']
    if item['tool'] == 'rekindra_preview' and item.get('path') and item.get('project_id') and item.get('plan_id'):
        for parent in Path(item['path']).parents:
            if parent.name == item['project_id']:
                html = parent / 'artifacts' / f"{item['plan_id']}.html"
                return str(html) if html.is_file() else None
    return None


worlds = [dict(a, path=world_html(a)) for a in row['artifacts'] if world_html(a)]
args.output.mkdir(parents=True, exist_ok=True)
record = {'selection': 'last created or previewed world, not a quality acceptance decision', 'case': row['case']}
if not worlds:
    record['outcome'] = 'no world authored in this run'
else:
    selected = worlds[-1]
    record['selected'] = selected
    env = os.environ.copy()
    env['REKINDRA_BROWSER_OUTPUT'] = str(args.output.resolve())
    env['REKINDRA_WORLD_STUDY'] = '1'
    root = Path(__file__).resolve().parents[1]
    with (args.output/'browser-check.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(['node', str(root/'scripts/browser_scene_test.cjs'), selected['path']], env=env, stdout=log, stderr=subprocess.STDOUT, timeout=240)
    record['browser_exit'] = result.returncode
    if result.returncode == 0:
        with (args.output/'decoded-review.log').open('w', encoding='utf-8') as log:
            decoded = subprocess.run(['node', str(root/'scripts/review_video.cjs'), str(args.output/'verified-scene.webm'), str(args.output/'decoded')], env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        record['decode_exit'] = decoded.returncode
        record['outcome'] = 'exported; visual review pending'
    else:
        record['outcome'] = 'browser verification failed'
(args.output/'acceptance-export.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record))
