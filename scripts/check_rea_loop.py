"""Check retained research, bounded attempts, scope and verification freshness.

This checks the local evidence bundle; it does not label an image impressive.
Run from the repository. Raw REA artifacts remain local and are not in Git.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/research/rea-loop'
LOCAL = ROOT / '.local/rea-loop'
ALLOWED = {'RULES.md','handlers.py','schemas.py','plugin.yaml',
           'rekindra_core/revisions.py','tests/test_revisions.py','tests/test_plugin.py',
           'scripts/check_rea_loop.py'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    repos=read(DOC/'github.json')
    assert len(repos)>=5 and len({r['repo'] for r in repos})==len(repos)
    for r in repos:
        assert type(r['stars']) is int and r['stars']>=10000
        assert re.fullmatch('[0-9a-f]{40}',r['commit'])
        for key in ('checked_at','license','source_paths','observed_mechanism','original_application','limitations'):
            assert r[key],(r['repo'],key)
        assert all(r['commit'] in p for p in r['source_paths'])
    searches=read(DOC/'x.json')
    assert len({r['query'] for r in searches})>=2
    assert all(all(r[k] for k in ('query','url','status','evidence','relevance')) for r in searches)
    attempts=[]
    for file in sorted(DOC.glob('*attempts.jsonl')):
        attempts.extend(json.loads(line) for line in file.read_text(encoding='utf-8-sig').splitlines() if line.strip())
    keys=[(a['unit'],a['attempt']) for a in attempts]
    assert len(keys)==len(set(keys)), 'Duplicate attempts'
    assert {a['unit'] for a in attempts}=={'R','G','X','I','P','V'}
    for unit in sorted({a['unit'] for a in attempts}):
        records=sorted((a for a in attempts if a['unit']==unit),key=lambda a:a['attempt'])
        assert [a['attempt'] for a in records]==list(range(1,len(records)+1))
        assert len(records)<=3 and records[-1]['outcome'].startswith('pass'),unit
        assert all(a['change'] and a['fixed_check'] and a['outcome'] for a in records)
    # Code merges/sorts the independent ledgers; no manual deduplication.
    (LOCAL/'merged-attempts.json').write_text(json.dumps(sorted(attempts,key=lambda a:(a['unit'],a['attempt'])),indent=2))
    manifest=read(LOCAL/'r-manifest.json')
    for name,expected in manifest['files'].items():
        assert digest(LOCAL/name)==expected,name
    assert (LOCAL/'theatre-rea.exit.txt').read_text(encoding='utf-8-sig').strip()=='0'
    assert read(LOCAL/'theatre-rea.json')
    assert digest(Path(manifest['archive_path']))==manifest['archive_sha256']
    receipt=read(DOC/'verification.json')
    assert receipt['python']=={'exit_code':0,'tests':59}
    assert receipt['node']=={'exit_code':0,'tests':7}
    for path,expected in receipt['source_hashes'].items():
        assert digest(ROOT/path)==expected,'Stale verification: '+path
    integration=read(LOCAL/'revision-integration.json')
    assert integration['unchanged_objects'] and integration['unchanged_sources']
    assert integration['changed_fields']==['camera']
    assert integration['edit_request_bytes']<integration['full_scene_bytes']/10
    assert (LOCAL/'revised-preview/preview.png').read_bytes()[:8]==b'\x89PNG\r\n\x1a\n'
    changed=subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT,text=True).splitlines()
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    for path in set(changed+untracked):
        assert path in ALLOWED or path.startswith('docs/research/rea-loop/'), 'Out of scope: '+path
    assert 'numeric equality' in (ROOT/'RULES.md').read_text()
    print(json.dumps({'pass':True,'repositories':len(repos),'x_records':len(searches),
                      'attempts':len(attempts),'python_tests':59,'node_tests':7,
                      'limits':['static REA coverage partial','no live Hermes test of new tool',
                                'no aesthetic acceptance','existing pixel-repeatability defect unresolved']}))


if __name__=='__main__':
    check()
