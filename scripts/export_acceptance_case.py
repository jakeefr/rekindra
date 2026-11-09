"""Export the last authored world after a native run; never label it artistically accepted."""
import argparse
import json
import os
from pathlib import Path
import subprocess



def world_html(item):
    """HTML for a created world, or for the plan a preview rendered (covers revise-only runs)."""
    if item['tool'] in ('rekindra_create_world', 'rekindra_export') and item.get('path'):
        return item['path']
    if item['tool'] == 'rekindra_preview' and item.get('path') and item.get('project_id') and item.get('plan_id'):
        for parent in Path(item['path']).parents:
            if parent.name == item['project_id']:
                html = parent / 'artifacts' / f"{item['plan_id']}.html"
                plan = Path(item['plan_path']) if item.get('plan_path') else parent / 'plans' / f"{item['plan_id']}.json"
                if not (html.is_file() and plan.is_file()):
                    return None  # e.g. a review_camera preview of a plan that was never built
                try:
                    data = json.loads(plan.read_text(encoding='utf-8'))
                except (ValueError, OSError):
                    return None  # unreadable plan is not a world to export
                scene = data.get('scene') if isinstance(data, dict) else None
                return str(html) if isinstance(scene, dict) and scene.get('schema_version') == 2 else None
    return None


def cleared_exports(artifacts):
    """Only rekindra_export writes HTML that can save video; a refused call has no path."""
    return [a for a in artifacts if a['tool'] == 'rekindra_export' and a.get('path')]


def main():
    from summarize_acceptance_runs import summarize
    parser = argparse.ArgumentParser()
    parser.add_argument('events', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    row = summarize(args.events)
    worlds = cleared_exports(row['artifacts'])
    args.output.mkdir(parents=True, exist_ok=True)
    record = {'selection': 'last rekindra_export result, not a quality acceptance decision', 'case': row['case']}
    if not worlds:
        record['outcome'] = 'no cleared export in this run'
    else:
        selected = worlds[-1]
        record['selected'] = selected
        record['selected_reason'] = f"last {selected['tool']} result with a built world HTML (plan {selected.get('plan_id')})"
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


if __name__ == '__main__':
    main()
