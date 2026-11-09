"""Worlds built from text evidence alone, with no image in the folder."""
import json
from pathlib import Path
import unittest

from test_worlds import world
import test_recover_evidence as recover_tests
from rekindra_core.compositions import CompositionStore
from rekindra_core.revisions import revise_world
from rekindra_core.scenes import SceneError
from rekindra_core.worlds import validate_world, WORLD_SCHEMA

SCHEMAS = recover_tests.plugin.schemas.SCHEMAS


EV = 'ev-' + '0' * 24
TEXT_REF = {'asset_id': 'b' * 32, 'evidence_ids': [EV], 'interpretation': 'A green door frames the arrival.'}


def text_only(refs=None, keep_key=True):
    scene = world()
    if keep_key:
        scene['references'] = []
    else:
        del scene['references']
    if refs is not None:
        scene['text_references'] = refs
    return scene


class ShapeTests(unittest.TestCase):
    def test_image_worlds_are_unchanged(self):
        checked = validate_world(world(), {'a' * 32})
        self.assertEqual(len(checked['references']), 1)
        self.assertNotIn('text_references', checked)

    def test_empty_or_absent_references_are_allowed_with_text_evidence(self):
        for keep_key in (True, False):
            with self.subTest(keep_key=keep_key):
                checked = validate_world(text_only([TEXT_REF], keep_key), set())
                self.assertEqual(checked['references'], [])
                self.assertEqual(checked['text_references'], [TEXT_REF])

    def test_a_world_with_no_source_at_all_is_refused(self):
        for keep_key in (True, False):
            with self.subTest(keep_key=keep_key), self.assertRaises(SceneError):
                validate_world(text_only(None, keep_key), set())

    def test_reference_bounds_still_hold(self):
        ref = world()['references'][0]
        scene = world(); scene['references'] = 'nope'; scene['text_references'] = [TEXT_REF]
        with self.assertRaises(SceneError):
            validate_world(scene, {'a' * 32})
        scene = world(); scene['references'] = [dict(ref, asset_id=c * 32) for c in 'abcdef0']
        with self.assertRaises(SceneError):
            validate_world(scene, {c * 32 for c in 'abcdef0'})
        # An image reference still has to be one of the selected images.
        with self.assertRaises(SceneError):
            validate_world(world(), set())

    def test_revision_cannot_remove_the_only_source(self):
        scene = validate_world(text_only([TEXT_REF]), set())
        with self.assertRaises(SceneError):
            revise_world(scene, [{'field': 'text_references', 'value': None}], set())
        revised, changed = revise_world(scene, [{'field': 'title', 'value': 'Second'}], set())
        self.assertEqual((changed, revised['references']), (['title'], []))

    def test_tool_schemas_make_the_image_optional_for_worlds_only(self):
        self.assertNotIn('references', WORLD_SCHEMA['required'])
        self.assertEqual(WORLD_SCHEMA['properties']['references']['minItems'], 0)
        create = SCHEMAS['rekindra_create_world']
        self.assertEqual(create['parameters']['required'], ['project_id', 'scene'])
        self.assertEqual(create['parameters']['properties']['asset_ids']['minItems'], 0)
        self.assertIn('text_references', create['description'])
        self.assertIn('no image', create['description'].lower())
        for name in ('rekindra_compose', 'rekindra_plan'):
            self.assertIn('asset_ids', SCHEMAS[name]['parameters']['required'])
            self.assertEqual(SCHEMAS[name]['parameters']['properties']['asset_ids']['minItems'], 1)


class NoImageProjectTests(recover_tests.RecoverEvidenceTests):
    """Runs against a real project with recovered text; the world selects no image."""

    def cited(self):
        out = self.recover('notes.txt')
        self.assertTrue(out['ok'], out)
        ids = [e['evidence_id'] for e in out['result']['evidence']]
        return [{'asset_id': self.ids['notes.txt'], 'evidence_ids': ids[:2], 'interpretation': 'Agent reading of the note.'}]

    def create(self, scene, **extra):
        return json.loads(self.handlers['rekindra_create_world'](
            {'project_id': self.project['project_id'], 'scene': scene, **extra}))

    def compositions(self):
        return CompositionStore(self.store)

    def test_world_from_text_alone_saves_builds_and_resolves_its_evidence(self):
        refs = self.cited()
        for extra in ({}, {'asset_ids': []}):
            with self.subTest(extra=extra):
                out = self.create(text_only(refs), **extra)
                self.assertTrue(out['ok'], out)
                result = out['result']
                self.assertEqual(result['source_ids'], [])
                plan = self.compositions().load_plan(self.project['project_id'], result['plan_id'])
                self.assertEqual((plan['source_ids'], plan['sources'], plan['scene']['references']), ([], [], []))
                quotes = plan['text_provenance']['recovered_evidence']
                self.assertEqual({q['evidence_id'] for q in quotes}, set(refs[0]['evidence_ids']))
                self.assertTrue(all(q['text'] and q['content'] == 'recovered' for q in quotes))
                self.assertEqual([i['interpretation'] for i in plan['text_provenance']['interpretations']],
                                 ['Agent reading of the note.'])
                document = Path(result['path']).read_text(encoding='utf-8')
                self.assertIn('Agent reading of the note.', document)
                self.assertIn('"sources": []', document)

    def test_image_worlds_can_still_cite_text(self):
        refs = self.cited()
        scene = world(self.ids['photo.tga']); scene['text_references'] = refs
        out = self.create(scene, asset_ids=[self.ids['photo.tga']])
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['result']['source_ids'], [self.ids['photo.tga']])

    def test_no_image_and_no_text_is_refused(self):
        out = self.create(text_only())
        self.assertFalse(out['ok'], out)
        self.assertIn('text_references', out['error']['message'])

    def test_evidence_must_be_real(self):
        self.cited()
        refs = [{'asset_id': self.ids['notes.txt'], 'evidence_ids': [EV], 'interpretation': 'Invented.'}]
        self.assertFalse(self.create(text_only(refs))['ok'])

    def test_text_world_needs_recovered_evidence(self):
        refs = [{'asset_id': self.ids['notes.txt'], 'evidence_ids': [EV], 'interpretation': 'Too early.'}]
        out = self.create(text_only(refs))
        self.assertFalse(out['ok'], out)
        self.assertIn('rekindra_recover', out['error']['message'])

    def test_revise_keeps_a_text_world_text_only(self):
        out = self.create(text_only(self.cited()))
        self.assertTrue(out['ok'], out)
        pid, plan_id = self.project['project_id'], out['result']['plan_id']
        revised = json.loads(self.handlers['rekindra_revise_world'](
            {'project_id': pid, 'plan_id': plan_id, 'edits': [{'field': 'title', 'value': 'Second'}]}))
        self.assertTrue(revised['ok'], revised)
        self.assertEqual(self.compositions().load_plan(pid, revised['result']['plan_id'])['source_ids'], [])
        dropped = json.loads(self.handlers['rekindra_revise_world'](
            {'project_id': pid, 'plan_id': plan_id, 'edits': [{'field': 'text_references', 'value': None}]}))
        self.assertFalse(dropped['ok'], dropped)

    def test_other_operations_still_need_an_image(self):
        pid = self.project['project_id']
        self.assertFalse(json.loads(self.handlers['rekindra_compose'](
            {'project_id': pid, 'asset_ids': [], 'scene': {}}))['ok'])
        self.assertFalse(json.loads(self.handlers['rekindra_plan'](
            {'project_id': pid, 'asset_ids': [], 'intent': 'x', 'send_images': True}))['ok'])
        with self.assertRaises(SceneError):
            self.compositions().sources(pid, [])

    def test_player_shows_the_text_interpretation(self):
        player = (Path(__file__).resolve().parents[1] / 'runtime' / 'player.js').read_text(encoding='utf-8')
        self.assertIn('scene.text_references', player)


# Only the tests defined above run for the subclass; inherited recovery tests already run once.
for _name in [n for n in dir(recover_tests.RecoverEvidenceTests) if n.startswith('test_')]:
    if _name not in NoImageProjectTests.__dict__:
        setattr(NoImageProjectTests, _name, None)


if __name__ == '__main__':
    unittest.main()
