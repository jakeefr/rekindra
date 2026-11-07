"""Build the original rain fixture for the GPU highlight-quality regression."""
import json
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from rekindra_core.worlds import compile_world
scene=json.loads((root/'examples/worlds/rain-switch-finished.json').read_text())
scene['width']=640;scene['height']=360
out=Path(sys.argv[1] if len(sys.argv)>1 else root/'.local/highlight-aa/fixture.json')
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(dict(scene=scene,programs=compile_world(scene))))
print(out)
