"""Real Hermes structured-model acceptance using only our synthetic image fixture."""
import json
from pathlib import Path
from hermes_cli.plugins import get_plugin_manager
from tools.registry import registry


def main():
    root = Path(__file__).resolve().parents[1]
    get_plugin_manager().discover_and_load()

    def call(name, args):
        raw = registry.dispatch(name, args)
        result = json.loads(raw) if isinstance(raw, str) else raw
        if not result.get('ok'):
            raise RuntimeError(f'{name} failed: {result}')
        return result['result']

    project = call('rekindra_inspect', {'folder': str(root / '.local/scene-fixture/inputs')})
    plan = call('rekindra_plan', {'project_id': project['project_id'],
                'asset_ids': [project['assets'][0]['asset_id']], 'send_images': True,
                'intent': 'Make a beautiful dreamy nocturnal green scene lasting 6 seconds. Let the moonlit forest inspire sparse poetic text and subtle movement.'})
    artifact = call('rekindra_build', {'project_id': project['project_id'], 'plan_id': plan['plan_id']})
    result = {'ok': True, 'dispatch': 'real Hermes registry', 'model_called': True,
              'plan': plan, 'artifact': artifact}
    (root / '.local/live-creative.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
