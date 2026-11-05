import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from rekindra_core.projects import ProjectStore
from test_tga import fixture

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rekindra_plugin_test', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)


class PluginTests(unittest.TestCase):
    def test_registers_without_accessing_host_storage(self):
        class Context:
            def __init__(self):
                self.tools = {}

            def register_tool(self, **kwargs):
                self.tools[kwargs['name']] = kwargs
        ctx = Context()
        plugin.register(ctx)
        self.assertEqual(set(ctx.tools), {'rekindra_inspect', 'rekindra_recover', 'rekindra_status'})
        # Registration must work without Hermes installed in this interpreter.
        result = json.loads(ctx.tools['rekindra_inspect']['handler']({'folder': 17}))
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'invalid_input')

    def test_real_handler_flow_returns_persistent_recovered_artifact(self):
        base = ROOT / '.local' / 'tests'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            temp = Path(temp)
            source = temp / 'input'
            source.mkdir()
            (source / 'old.tga').write_bytes(fixture())
            store = ProjectStore(temp / 'projects')
            handlers = plugin.handlers.make_handlers(lambda: store)
            inspected = json.loads(handlers['rekindra_inspect']({'folder': str(source)}, session_id='test'))
            self.assertTrue(inspected['ok'])
            p = inspected['result']
            recovered = json.loads(handlers['rekindra_recover']({'project_id': p['project_id'], 'asset_id': p['assets'][0]['asset_id']}))
            self.assertTrue(recovered['ok'])
            self.assertTrue(Path(recovered['result']['path']).exists())
            status = json.loads(handlers['rekindra_status']({'project_id': p['project_id']}))
            self.assertEqual(status['result']['stage'], 'recovered')

    def test_invalid_arguments_never_raise(self):
        from rekindra_plugin_test.handlers import make_handlers
        def unavailable():
            raise RuntimeError('sensitive-provider-secret')
        handlers = make_handlers(unavailable)
        for name, handler in handlers.items():
            for invalid in (None, [], {'folder': 5}, {}):
                with self.subTest(name=name, invalid=invalid):
                    self.assertFalse(json.loads(handler(invalid))['ok'])
        result = handlers['rekindra_inspect']({'folder': 'D:/example'})
        self.assertFalse(json.loads(result)['ok'])
        self.assertNotIn('sensitive-provider-secret', result)


if __name__ == '__main__':
    unittest.main()
