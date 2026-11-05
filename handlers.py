"""Thin JSON boundary; failures never escape into the Hermes tool loop."""
import json
from pathlib import Path
from .rekindra_core.projects import ProjectStore, ProjectError


def host_store():
    # Lazy public host API: registration must not create state or require auth.
    from plugins.plugin_storage import plugin_data_dir
    return ProjectStore(plugin_data_dir('rekindra') / 'projects')


def make_handlers(store_factory=host_store):
    def invoke(operation, args):
        try:
            if not isinstance(args, dict):
                raise ValueError('Tool arguments must be an object')
            required = ('folder',) if operation == 'inspect' else ('project_id', 'asset_id') if operation == 'recover' else ('project_id',)
            if any(not isinstance(args.get(k), str) or not args[k].strip() for k in required):
                raise ValueError('Provide nonempty string values for: ' + ', '.join(required))
            if operation == 'inspect' and not Path(args['folder']).is_absolute():
                raise ValueError('Folder must be an absolute local path')
            store = store_factory()
            if operation == 'inspect':
                result = store.inspect(Path(args['folder']))
            elif operation == 'recover':
                result = store.recover(args['project_id'], args['asset_id'])
            else:
                result = store.status(args['project_id'])
            return json.dumps({'ok': True, 'result': result}, ensure_ascii=False)
        except (ProjectError, ValueError) as exc:
            return json.dumps({'ok': False, 'error': {'code': 'invalid_input', 'message': str(exc)}})
        except OSError:
            return json.dumps({'ok': False, 'error': {'code': 'filesystem_error', 'message': 'Cannot read or write the local project. Check paths and permissions.'}})
        except Exception:
            return json.dumps({'ok': False, 'error': {'code': 'operation_failed', 'message': 'Rekindra could not complete this operation. Check the Hermes plugin installation and project integrity.'}})

    def inspect(args, **kwargs):
        return invoke('inspect', args)

    def recover(args, **kwargs):
        return invoke('recover', args)

    def status(args, **kwargs):
        return invoke('status', args)

    return {'rekindra_inspect': inspect, 'rekindra_recover': recover, 'rekindra_status': status}
