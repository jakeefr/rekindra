"""Developer integration harness: dispatch installed tools through real Hermes.

Run with the selected Hermes interpreter and its configured HERMES_HOME.
This harness does not contact a model or claim a conversational acceptance pass.
"""
import json
import os
from pathlib import Path
import struct
import uuid

from hermes_cli.plugins import get_plugin_manager
from tools.registry import registry


def main():
    home = Path(os.environ['HERMES_HOME'])
    fixture_dir = home / 'rekindra-smoke-inputs' / uuid.uuid4().hex
    fixture_dir.mkdir(parents=True)
    # Hand-defined red, green / blue, white raster; no other recovery engine.
    source = struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0, 2, 2, 24, 32)
    source += bytes.fromhex('0000ff00ff00ff0000ffffff')
    (fixture_dir / 'forgotten.tga').write_bytes(source)
    manager = get_plugin_manager()
    manager.discover_and_load()

    def call(name, args):
        raw = registry.dispatch(name, args)
        result = json.loads(raw) if isinstance(raw, str) else raw
        if not result.get('ok'):
            raise RuntimeError(f'{name} failed: {result}')
        return result['result']

    p = call('rekindra_inspect', {'folder': str(fixture_dir)})
    artifact = call('rekindra_recover', {'project_id': p['project_id'], 'asset_id': p['assets'][0]['asset_id']})
    status = call('rekindra_status', {'project_id': p['project_id']})
    assert (fixture_dir / 'forgotten.tga').read_bytes() == source
    assert Path(artifact['path']).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert status['stage'] == 'recovered'
    print(json.dumps({'ok': True, 'dispatch': 'real Hermes registry', 'model_called': False,
                      'project_id': p['project_id'], 'artifact': artifact}, indent=2))


if __name__ == '__main__':
    main()
