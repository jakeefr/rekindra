"""Verify local evidence for shared assembly/lighting milestone, not aesthetics."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rekindra_core.projects import ProjectStore
from rekindra_core.compositions import CompositionStore
from summarize_acceptance_runs import summarize

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'.local/assembly-loop'
DOC=ROOT/'docs/acceptance/assembly-loop'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    receipt=read(DOC/'verification.json')
    assert (LOCAL/'forest-browser-exit.txt').read_text(encoding='utf-8-sig').strip()=='0', (
        'UNIT E failed: strict same-time pixel check. Diagnostic video does not satisfy this gate.')
    assert receipt['python_tests']==63 and receipt['node_tests']==7
    assert receipt['python_exit']==receipt['node_exit']==0
    for relative,sha in receipt['source_hashes'].items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==sha,relative
    gpu=read(LOCAL/'gpu/result.json');ambient=read(LOCAL/'ambient/result.json')
    expected=[[2,1,0,4,1,0,2,1,0],[2,1,0,2,3,0,2,1,0]]
    assert all(abs(a-b)<1e-5 for x,y in zip(gpu['samples'],expected) for a,b in zip(x,y))
    assert gpu['shadow']['open']>gpu['shadow']['closed']+40
    assert gpu['finalClamp'][0]>gpu['finalClamp'][2]+40
    assert ambient['differences']==0
    assert ambient['ground']['bottom'][0]-ambient['ground']['bottom'][1]>ambient['ground']['top'][0]-ambient['ground']['top'][1]+20
    smoke=summarize(LOCAL/'smoke-events.jsonl');forest=summarize(LOCAL/'forest-events.jsonl')
    assert all(r['results'] and r['results'][-1]['exit_code']==0 for r in (smoke,forest))
    for row in (smoke,forest):
        assert 'rekindra_preview' in row['tools'] and 'vision_analyze' in row['tools']
        assert 'rekindra_revise_world' in row['tools']
    count=sum(t in ('rekindra_create_world','rekindra_revise_world') for t in forest['tools'])
    assert count<=3,'Native candidate submission limit exceeded'
    selected=receipt['native_retained']
    store=CompositionStore(ProjectStore(Path(receipt['project_store'])))
    plan=store.load_plan(selected['project_id'],selected['plan_id'])
    assert plan['scene']['assemblies'] and any(o.get('assembly') for o in plan['scene']['objects'])
    assert any(a.get('plan_id')==selected['plan_id'] and a['tool']=='rekindra_preview' for a in forest['artifacts'])
    export=read(LOCAL/'forest-export/result.json')
    assert export['width']==1280 and export['height']==720
    assert (LOCAL/'forest-export/verified-scene.webm').stat().st_size>10000
    assert list((LOCAL/'forest-export/decoded').glob('*.png'))
    assert receipt['reviewed_samples']==24 and receipt['private_repo'] is True
    records=[json.loads(line) for line in (DOC/'attempts.jsonl').read_text().splitlines() if line.strip()]
    groups={}
    for record in records:groups.setdefault(record['unit'],[]).append(record)
    for unit,attempts in groups.items():
        attempts.sort(key=lambda a:a['attempt'])
        assert [a['attempt'] for a in attempts]==list(range(1,len(attempts)+1)) and len(attempts)<=3,unit
        assert attempts[-1]['outcome']=='pass',unit
    print(json.dumps({'pass':True,'python_tests':63,'node_tests':7,'native_candidates':count,
                      'retained':selected,'reviewed_decoded_samples':24,
                      'caveat':'Engineering gates passed; aesthetics and broader GPU repeatability remain separate.'}))


if __name__=='__main__':main()
