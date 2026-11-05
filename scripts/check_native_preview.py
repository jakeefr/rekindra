"""Real-browser regression for source-loading completion (no browser automation dependency).

Supply a saved multi-image project and plan. Before the load-event repair the
two real coastal JPEG case reproducibly exited with only one loaded source.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rekindra_core.projects import ProjectStore
from rekindra_core.compositions import CompositionStore
from rekindra_core.preview import preview_scene

parser = argparse.ArgumentParser()
parser.add_argument('store', type=Path)
parser.add_argument('project')
parser.add_argument('plan')
parser.add_argument('--repeat', type=int, default=3)
args = parser.parse_args()
store = ProjectStore(args.store)
plan = CompositionStore(store).load_plan(args.project, args.plan)
for attempt in range(args.repeat):
    result = preview_scene(store, args.project, args.plan)
    assert result['times_seconds'] == [(i+.5)*plan['scene']['duration']/6 for i in range(6)]
    assert Path(result['path']).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    print(attempt+1, result['path'], flush=True)
