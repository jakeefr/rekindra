"""Every rejection names what was wrong, what to pass instead and the valid values.

One test per rejection class, each through the registered handler the model actually calls.
"""
import copy
import json
import sys
import unittest

import test_recover_evidence as recover_tests
from test_worlds import world
from rekindra_core import export_gate

plugin = recover_tests.plugin


class RejectionTests(unittest.TestCase):
    def setUp(self):
        recover_tests.RecoverEvidenceTests.setUp(self)
        # Hermes loads the store from the plugin package, so its errors are the classes the handler catches.
        packaged = sys.modules[plugin.__name__ + '.rekindra_core.projects']
        self.store = packaged.ProjectStore(self.store.root)

    tearDown = recover_tests.RecoverEvidenceTests.tearDown
    recover = recover_tests.RecoverEvidenceTests.recover

    def message(self, tool, args, *expected):
        out = json.loads(self.handlers[tool](args))
        self.assertFalse(out['ok'], out)
        text = out['error']['message']
        for part in expected:
            self.assertIn(part, text)
        self.assertNotIn('\n', text)
        return text

    def scene(self):
        return world(self.ids['photo.tga'])

    def create(self, scene, *expected, **extra):
        args = {'project_id': self.project['project_id'], 'asset_ids': [self.ids['photo.tga']], 'scene': scene, **extra}
        return self.message('rekindra_create_world', args, *expected)

    def plan(self):
        out = json.loads(self.handlers['rekindra_create_world'](
            {'project_id': self.project['project_id'], 'asset_ids': [self.ids['photo.tga']], 'scene': self.scene()}))
        self.assertTrue(out['ok'], out)
        return out['result']['plan_id']

    # --- arguments ------------------------------------------------------------------------

    def test_unaccepted_argument_is_refused_with_the_accepted_list(self):
        pid = self.project['project_id']
        self.message('rekindra_status', {'project_id': pid, 'verbose': True},
                     'rekindra_status does not accept: verbose', 'Accepted arguments: project_id')
        self.message('rekindra_recover', {'project_id': pid, 'asset': self.ids['notes.txt']},
                     'does not accept: asset', 'project_id, asset_id')

    def test_scene_field_at_top_level_is_sent_inside_scene(self):
        self.create(self.scene(), 'does not accept: text_references', 'Put text_references inside scene',
                    'asset_ids', text_references=[])

    def test_missing_required_argument_names_it_and_its_source(self):
        self.message('rekindra_recover', {'project_id': self.project['project_id']},
                     'asset_id is missing', 'rekindra_inspect or rekindra_status')
        self.message('rekindra_status', {'project_id': 7}, 'project_id is int', 'rekindra_inspect')
        self.message('rekindra_status', [], 'one JSON object', 'got list')

    def test_malformed_and_unknown_ids_say_where_ids_come_from(self):
        pid = self.project['project_id']
        self.message('rekindra_status', {'project_id': 'my-folder'}, "'my-folder'", '32 lowercase hex', 'rekindra_inspect')
        self.message('rekindra_status', {'project_id': '0' * 32}, '0' * 32, 'rekindra_inspect')
        self.message('rekindra_recover', {'project_id': pid, 'asset_id': 'notes.txt'}, "'notes.txt'", 'not a file name')
        self.message('rekindra_recover', {'project_id': pid, 'asset_id': 'f' * 32}, 'f' * 32, self.ids['notes.txt'])
        self.message('rekindra_preview', {'project_id': pid, 'plan_id': 'latest'}, "'latest'", 'rekindra_create_world')
        self.message('rekindra_preview', {'project_id': pid, 'plan_id': 'e' * 32}, 'e' * 32, 'rekindra_revise_world')

    # --- sources --------------------------------------------------------------------------

    def test_asset_ids_rejections_name_the_valid_images(self):
        pid, tga, note = self.project['project_id'], self.ids['photo.tga'], self.ids['notes.txt']
        scene = self.scene()
        self.message('rekindra_create_world', {'project_id': pid, 'asset_ids': tga, 'scene': scene},
                     'JSON array', 'rekindra_inspect', tga)
        self.message('rekindra_create_world', {'project_id': pid, 'asset_ids': [note], 'scene': scene},
                     note, 'not an image', 'scene.text_references', tga)
        self.message('rekindra_create_world', {'project_id': pid, 'asset_ids': ['d' * 32], 'scene': scene},
                     'd' * 32, tga)

    def test_evidence_cited_under_the_wrong_asset_says_where_ids_come_from(self):
        evidence = self.recover('notes.txt')['result']['evidence'][0]['evidence_id']
        self.assertTrue(self.recover('old.zip')['ok'])
        scene = self.scene()
        scene['text_references'] = [{'asset_id': self.ids['old.zip'], 'evidence_ids': [evidence], 'interpretation': 'A lake.'}]
        self.create(scene, evidence, 'was not recovered from asset', self.ids['old.zip'], 'rekindra_recover')

    # --- scene ----------------------------------------------------------------------------

    def test_scene_shape_rejections(self):
        self.create(json.dumps(self.scene()), 'JSON object', 'not JSON-encoded text')
        scene = self.scene()
        scene['schema_version'] = 3
        self.create(scene, 'schema_version', '2 for rekindra_create_world', '3')
        scene = self.scene()
        scene['captions'] = ['hello']
        self.create(scene, "'captions'", 'Not accepted here', 'environment')
        scene = self.scene()
        del scene['camera']
        self.create(scene, 'Missing: camera')

    def test_value_rejections_echo_the_value_and_the_valid_range(self):
        scene = self.scene()
        scene['objects'][0]['color'] = 'red'
        self.create(scene, "'red'", '#1A2B3C')
        scene = self.scene()
        scene['objects'][0]['roughness'] = 5
        self.create(scene, 'roughness', 'between 0.04 and 1', 'got 5')
        scene = self.scene()
        scene['objects'][0]['metalness'] = '0.5'
        self.create(scene, 'metalness', 'JSON number, not text')
        scene = self.scene()
        scene['camera'][0]['fov'] = 170
        self.create(scene, 'field of view', 'between 15 and 100', 'got 170')

    def test_expression_rejections_name_the_offender_and_the_allowed_names(self):
        scene = self.scene()
        scene['objects'][0]['position']['x'] = 'u + wobble'
        self.create(scene, 'wobble', "'u + wobble'", 'u, v, t')
        scene = self.scene()
        scene['objects'][0]['position']['x'] = 'sin(u, v)'
        self.create(scene, 'sin takes 1, got 2')
        scene = self.scene()
        scene['objects'][0]['position']['x'] = 'u +'
        self.create(scene, "'u +'", 'one arithmetic expression')

    # --- revise, preview, export ----------------------------------------------------------

    def test_revise_rejections_list_the_valid_fields(self):
        pid, plan = self.project['project_id'], self.plan()
        self.message('rekindra_revise_world', {'project_id': pid, 'plan_id': plan, 'edits': [{'field': 'colour', 'value': 1}]},
                     "'colour'", 'title', 'environment')
        self.message('rekindra_revise_world', {'project_id': pid, 'plan_id': plan, 'edits': []}, 'edits')

    def test_review_camera_rejection_shows_the_shape(self):
        self.message('rekindra_preview', {'project_id': self.project['project_id'], 'plan_id': self.plan(),
                                          'review_camera': {'eye': [0, 1, 5], 'target': [0, 0, 0], 'fov': 50, 'at': 0}},
                     '"eye": [x, y, z]', "'at'")

    def test_acknowledgment_rejections_show_the_item_shape_and_current_ids(self):
        warnings = [{'warning_id': 'palette:top-band', 'kind': 'palette_drift', 'message': 'top band drifted'}]
        for bad, expected in (([{'id': 'palette:top-band'}], '{"warning_id": "...", "reason": "..."}'),
                              ([{'warning_id': 'palette:sky', 'reason': 'kept deliberately dark'}], '(current: palette:top-band)')):
            with self.assertRaises(export_gate.ExportBlocked) as caught:
                export_gate._matched(bad, warnings, 0)
            self.assertIn(expected, str(caught.exception))
            self.assertIn('palette:top-band', str(caught.exception))


class SchemaTests(unittest.TestCase):
    """What the model reads before it calls: closed argument lists, id shapes and sources."""

    def test_every_tool_is_closed_and_describes_its_ids(self):
        for name, schema in plugin.schemas.SCHEMAS.items():
            parameters = schema['parameters']
            self.assertIs(parameters.get('additionalProperties'), False, name)
            for key in ('project_id', 'asset_id', 'plan_id'):
                if key in parameters['properties']:
                    argument = parameters['properties'][key]
                    self.assertEqual(argument.get('pattern'), '^[0-9a-f]{32}$', (name, key))
                    self.assertIn('rekindra_', argument.get('description', ''), (name, key))
            for key, argument in parameters['properties'].items():
                self.assertTrue(argument.get('description') or argument.get('properties') or key == 'scene', (name, key))

    def test_handler_accepts_exactly_the_documented_arguments(self):
        handlers = plugin.handlers
        self.assertEqual(set(handlers.TOOL_NAMES.values()), set(plugin.schemas.SCHEMAS))

    def test_world_schema_states_the_ranges_the_validator_enforces(self):
        scene = plugin.schemas.SCHEMAS['rekindra_create_world']['parameters']['properties']['scene']['properties']
        surface = scene['objects']['items']['properties']
        self.assertEqual((surface['roughness']['minimum'], surface['roughness']['maximum']), (.04, 1))
        self.assertEqual(surface['color']['pattern'], '^#[0-9a-fA-F]{6}$')
        self.assertEqual(scene['camera']['items']['properties']['fov'], {'type': 'number', 'minimum': 15, 'maximum': 100})
        self.assertEqual(scene['environment']['properties']['fog_density']['maximum'], .15)
        description = plugin.schemas.SCHEMAS['rekindra_create_world']['description']
        self.assertNotIn('and12', description)
        self.assertNotIn('within12', description)

    def test_valid_fixture_world_still_passes_the_tightened_ranges(self):
        scene = world('a' * 32)
        limits = plugin.schemas.SCHEMAS['rekindra_create_world']['parameters']['properties']['scene']['properties']
        for surface in scene['objects']:
            for key in ('roughness', 'metalness', 'emission'):
                rule = limits['objects']['items']['properties'][key]
                self.assertTrue(rule['minimum'] <= surface[key] <= rule['maximum'], key)
        self.assertIsNot(copy.deepcopy(scene), scene)


if __name__ == '__main__':
    unittest.main()
