"""Exercise corpus snapshots and exact recovery; all outputs stay in supplied D: root."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rekindra_core.projects import ProjectStore, ProjectError
from rekindra_core.compositions import CompositionStore
from rekindra_core.scenes import SceneError


def png_rgba(path):
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    offset, chunks = 8, []
    width = height = None
    while offset < len(data):
        size = struct.unpack_from('>I', data, offset)[0]
        kind = data[offset+4:offset+8]
        payload = data[offset+8:offset+8+size]
        crc = struct.unpack_from('>I', data, offset+8+size)[0]
        assert zlib.crc32(kind+payload) & 0xffffffff == crc
        if kind == b'IHDR':
            width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', payload)
            assert (depth, color, compression, filtering, interlace) == (8, 6, 0, 0, 0)
        elif kind == b'IDAT':
            chunks.append(payload)
        offset += size + 12
    raw = zlib.decompress(b''.join(chunks))
    stride = width*4+1
    assert len(raw) == height*stride
    assert all(raw[y*stride] == 0 for y in range(height))
    return b''.join(raw[y*stride+1:(y+1)*stride] for y in range(height))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('corpus', type=Path)
    args = parser.parse_args()
    root = args.corpus.resolve()
    store = ProjectStore(root/'recovery-projects')
    compositions = CompositionStore(store)
    truth = {(r['case'], r['file']): r for r in json.loads((root/'ground-truth.json').read_text()) if 'file' in r}
    rows = []
    for folder in sorted((root/'inputs').iterdir()):
        project = store.inspect(folder)
        for asset in project['assets']:
            row = {'case': folder.name, 'file': asset['source_path'], 'format': asset['format'], 'project_id': project['project_id']}
            expected = truth.get((folder.name, asset['source_path']))
            if expected:
                try:
                    result = store.recover(project['project_id'], asset['asset_id'])
                    actual = hashlib.sha256(png_rgba(Path(result['path']))).hexdigest()
                    row.update(outcome='recovered', rgba_sha256=actual, passed=actual == expected.get('rgba_sha256'))
                except ProjectError as exc:
                    row.update(outcome='rejected', error=str(exc), passed=expected['expected'] != 'recover_exact_rgba')
                if folder.name.startswith('X'):
                    try:
                        compositions.sources(project['project_id'], [asset['asset_id']])
                        row.update(source_accepted=True, passed=False)
                    except (SceneError, ProjectError) as exc:
                        row.update(source_accepted=False, source_error=str(exc))
            rows.append(row)
    report = {'cases': len({r['case'] for r in rows}), 'files': len(rows), 'checks': sum('passed' in r for r in rows), 'failed': sum(r.get('passed') is False for r in rows), 'rows': rows}
    (root/'recovery-results.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}))
    if report['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
