"""Save a private integration fixture with a nonblack video sample background."""
import json,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'scripts')]
from rekindra_core.projects import ProjectStore
from rekindra_core.compositions import CompositionStore
from rekindra_core.preview import preview_scene
from make_motion_study import source_image

out=root/'.local/planar-reflection';inputs=out/'inputs';inputs.mkdir(exist_ok=True)
(inputs/'source.png').write_bytes(source_image())
store=ProjectStore(out/'projects');project=store.inspect(inputs)
pid=project['project_id'];aid=project['assets'][0]['asset_id'];comps=CompositionStore(store)
scene=json.loads((out/'fixtures.json').read_text())['combinedCaps']['scene']
scene['references'][0]['asset_id']=aid
scene['environment'].update(sky_top='#18354B',sky_bottom='#29495A')
plan=comps.save_plan(pid,scene,[aid],dict(provider='local',model='reflection-integration-control'))
artifact=comps.build(pid,plan['plan_id']);start=time.monotonic()
preview=preview_scene(store,pid,plan['plan_id']);elapsed=time.monotonic()-start
assert elapsed<45
(out/'export-control.json').write_text(json.dumps(dict(artifact=artifact,preview=preview,preview_seconds=elapsed),indent=2))
print(artifact['path'])
