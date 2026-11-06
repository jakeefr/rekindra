"""Emit actual compiler output for the development GPU regression."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rekindra_core.assemblies import compile_assemblies


def group(identifier,**changes):
    value=dict(id=identifier,translation=dict(x='0',y='0',z='0'),rotation=dict(x='0',y='0',z='0'),pivot=[0,0,0],scale=[1,1,1])
    value.update(changes)
    return value


if __name__=='__main__':
    chain=compile_assemblies([group('root',translation=dict(x='2',y='0',z='0')),
        group('child',parent='root',pivot=[0,1,0],scale=[2,1,.5],rotation=dict(x='0',y='0',z='t'))])['child']['glsl']
    move=compile_assemblies([group('move',translation=dict(x='t',y='0',z='0'))])['move']['glsl']
    bounded=compile_assemblies([group('scaled',scale=[.05,1,1])])['scaled']['glsl']
    output=Path(__file__).resolve().parents[1]/'.local/assembly-loop/gpu-input.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(chain=chain,move=move,bounded=bounded)))
