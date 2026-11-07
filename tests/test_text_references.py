import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_worlds import world
import test_recover_evidence as recover_tests
from test_recover_evidence import NOTE
from rekindra_core.compositions import CompositionStore
from rekindra_core.revisions import revise_world
from rekindra_core.scenes import SceneError
from rekindra_core.worlds import validate_world, WORLD_SCHEMA


EV = 'ev-' + '0' * 24


class TextReferenceShapeTests(unittest.TestCase):
    def ref(self, **kw):
        base = {'asset_id': 'b' * 32, 'evidence_ids': [EV], 'interpretation': 'A green door frames the arrival.'}
        base.update(kw)
        return base

    def test_optional_and_old_worlds_still_validate(self):
        scene = world()
        self.assertNotIn('text_references', validate_world(scene, {'a' * 32}))
        self.assertNotIn('text_references', WORLD_SCHEMA['required'])
        scene['text_references'] = [self.ref()]
        self.assertEqual(validate_world(scene, {'a' * 32})['text_references'], [self.ref()])

    def test_rejects_bad_shapes(self):
        bad = [[], [self.ref()] * 2, [self.ref()] + [self.ref(asset_id=c * 32) for c in 'cdef'],
               [self.ref(evidence_ids=[])], [self.ref(evidence_ids=[EV, EV])], [self.ref(evidence_ids=['ev-xyz'])],
               [self.ref(evidence_ids=[EV] * 5)], [self.ref(interpretation='x' * 301)], [self.ref(interpretation=3)], [self.ref(interpretation='  ')],
               [dict(self.ref(), text='smuggled recovered text')], [{'asset_id': 'b' * 32}], 'nope']
        for refs in bad:
            scene = world(); scene['text_references'] = refs
            with self.subTest(refs=refs), self.assertRaises(SceneError):
                validate_world(scene, {'a' * 32})

    def test_revise_can_set_and_remove(self):
        scene = world()
        revised, changed = revise_world(scene, [{'field': 'text_references', 'value': [self.ref()]}], {'a' * 32})
        self.assertEqual(changed, ['text_references'])
        removed, changed = revise_world(revised, [{'field': 'text_references', 'value': None}], {'a' * 32})
        self.assertNotIn('text_references', removed)
        with self.assertRaises(SceneError):
            revise_world(scene, [{'field': 'title', 'value': None}], {'a' * 32})
        with self.assertRaises(SceneError):
            revise_world(scene, [{'field': 'assemblies', 'value': None}], {'a' * 32})


class TextReferenceProvenanceTests(recover_tests.RecoverEvidenceTests):
    """Runs against a real project with recovered text, ZIP, rejected JSON and TGA."""

    def world_with(self, refs):
        scene = world(self.ids['photo.tga'])
        scene['text_references'] = refs
        return scene

    def evidence_for(self, name):
        out = self.recover(name)
        self.assertTrue(out['ok'], out)
        return [e['evidence_id'] for e in out['result']['evidence']]

    def compositions(self):
        return CompositionStore(self.store)

    def test_saved_plan_separates_recovered_text_from_interpretation(self):
        ids = self.evidence_for('notes.txt')
        self.assertTrue(ids)
        refs = [{'asset_id': self.ids['notes.txt'], 'evidence_ids': ids[:1],
                 'interpretation': 'Summer light behind a green door.'}]
        pid, tga = self.project['project_id'], self.ids['photo.tga']
        saved = self.compositions().save_plan(pid, self.world_with(refs), [tga], {'origin': 'test'})
        prov = saved['text_provenance']
        self.assertEqual(set(prov), {'recovered_evidence', 'interpretations'})
        [rec] = prov['recovered_evidence']
        self.assertEqual((rec['asset_id'], rec['evidence_id'], rec['content'], rec['source_path']),
                         (self.ids['notes.txt'], ids[0], 'recovered', 'notes.txt'))
        self.assertIn(rec['text'], NOTE.decode())
        self.assertNotIn('interpretation', rec)
        [interp] = prov['interpretations']
        self.assertEqual((interp['content'], interp['origin'], interp['recovered']), ('interpretation', 'agent', False))
        self.assertEqual(interp['interpretation'], 'Summer light behind a green door.')
        self.assertNotIn('text', interp)
        self.assertNotIn(interp['interpretation'], json.dumps(prov['recovered_evidence']))
        loaded = self.compositions().load_plan(pid, saved['plan_id'])
        self.assertEqual(loaded['text_provenance'], prov)

    def test_refuses_unrecovered_foreign_and_unknown_evidence(self):
        pid, tga = self.project['project_id'], self.ids['photo.tga']
        note = self.ids['notes.txt']
        with self.assertRaisesRegex(SceneError, 'recovered evidence'):
            self.compositions().save_plan(pid, self.world_with(
                [{'asset_id': note, 'evidence_ids': [EV], 'interpretation': 'x'}]), [tga], {})
        note_ids = self.evidence_for('notes.txt')
        self.evidence_for('old.zip')
        cases = [[{'asset_id': note, 'evidence_ids': [EV], 'interpretation': 'x'}],
                 [{'asset_id': self.ids['old.zip'], 'evidence_ids': note_ids[:1], 'interpretation': 'x'}],
                 [{'asset_id': tga, 'evidence_ids': note_ids[:1], 'interpretation': 'x'}],
                 [{'asset_id': 'f' * 32, 'evidence_ids': note_ids[:1], 'interpretation': 'x'}]]
        plans = self.store._project(pid) / 'plans'
        for refs in cases:
            with self.subTest(refs=refs), self.assertRaises(SceneError):
                self.compositions().save_plan(pid, self.world_with(refs), [tga], {})
        self.assertFalse(plans.exists() and any(plans.iterdir()))

    def test_rejected_source_has_no_evidence_and_cannot_be_cited(self):
        # Regression: bad.json is rejected by intake (non-finite number). Its excerpt
        # must not come back as recovered evidence, alone or beside other sources.
        self.evidence_for('notes.txt')
        out = self.recover('bad.json')
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['result']['intake_status'], 'rejected')
        self.assertEqual((out['result']['evidence_count'], out['result']['evidence']), (0, []))
        path = Path(out['result']['dossier_path'])
        dossier = json.loads(path.read_text(encoding='utf-8'))
        bad = self.ids['bad.json']
        self.assertEqual([e for e in dossier['evidence'] if e.get('source_id') == bad], [])
        self.assertIn(bad, {s.get('source_id') for s in dossier['sources']})
        self.assertTrue(any(e.get('source_id') == self.ids['notes.txt'] for e in dossier['evidence']))
        self.assertNotIn('NaN', json.dumps(dossier['evidence']))
        # Re-recovering another source re-reads bad.json's saved intake: still dropped.
        self.evidence_for('old.zip')
        dossier = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual([e for e in dossier['evidence'] if e.get('source_id') == bad], [])
        with self.assertRaisesRegex(SceneError, 'rejected'):
            self.compositions().save_plan(self.project['project_id'], self.world_with(
                [{'asset_id': bad, 'evidence_ids': [EV], 'interpretation': 'x'}]), [self.ids['photo.tga']], {})

    def test_changed_evidence_invalidates_plan(self):
        ids = self.evidence_for('notes.txt')
        pid, tga = self.project['project_id'], self.ids['photo.tga']
        refs = [{'asset_id': self.ids['notes.txt'], 'evidence_ids': ids[:1], 'interpretation': 'x'}]
        saved = self.compositions().save_plan(pid, self.world_with(refs), [tga], {})
        path = self.store._project(pid) / 'plans' / (saved['plan_id'] + '.json')
        record = json.loads(path.read_text(encoding='utf-8'))
        record['text_provenance']['interpretations'][0]['recovered'] = True
        path.write_text(json.dumps(record), encoding='utf-8')
        with self.assertRaisesRegex(SceneError, 'text evidence provenance'):
            self.compositions().load_plan(pid, saved['plan_id'])
        record['text_provenance']['interpretations'][0]['recovered'] = False
        record['text_provenance']['recovered_evidence'][0]['text'] += ' forged'
        path.write_text(json.dumps(record), encoding='utf-8')
        with self.assertRaisesRegex(SceneError, 'text evidence provenance'):
            self.compositions().load_plan(pid, saved['plan_id'])
        # A self-consistent copy for an asset the project does not have is refused.
        from rekindra_core.compositions import _evidence_id
        ghost, item = 'f' * 32, dict(saved['text_provenance']['recovered_evidence'][0])
        item.update(asset_id=ghost, source_path=None,
                    evidence_id=_evidence_id(ghost, item['locator'], item['text']))
        ghost_refs = [{'asset_id': ghost, 'evidence_ids': [item['evidence_id']], 'interpretation': 'x'}]
        stored = {'recovered_evidence': [item],
                  'interpretations': [dict(saved['text_provenance']['interpretations'][0],
                                           asset_id=ghost, evidence_ids=[item['evidence_id']])]}
        with self.assertRaisesRegex(SceneError, 'text evidence provenance'):
            self.compositions().check_text_provenance(pid, ghost_refs, stored)

    def test_plan_survives_later_recoveries_that_rebuild_the_dossier(self):
        ids = self.evidence_for('notes.txt')
        pid, tga = self.project['project_id'], self.ids['photo.tga']
        refs = [{'asset_id': self.ids['notes.txt'], 'evidence_ids': ids, 'interpretation': 'x'}]
        saved = self.compositions().save_plan(pid, self.world_with(refs), [tga], {})
        evidence = self.store._project(pid) / 'artifacts' / 'evidence.json'
        before = evidence.read_bytes()
        self.evidence_for('old.zip'); self.recover('bad.json')
        # Simulate a rebuild that reshapes or evicts the cited items entirely.
        dossier = json.loads(evidence.read_text(encoding='utf-8'))
        self.assertNotEqual(evidence.read_bytes(), before)
        dossier['evidence'] = [e for e in dossier['evidence'] if e['source_id'] != self.ids['notes.txt']]
        blob = json.dumps(dossier, ensure_ascii=False, sort_keys=True).encode('utf-8')
        evidence.write_bytes(blob)
        manifest = self.store._project(pid) / 'project.json'
        project = json.loads(manifest.read_text(encoding='utf-8'))
        import hashlib
        project['evidence']['sha256'] = hashlib.sha256(blob).hexdigest()
        manifest.write_text(json.dumps(project), encoding='utf-8')
        loaded = self.compositions().load_plan(pid, saved['plan_id'])
        self.assertEqual(loaded['text_provenance'], saved['text_provenance'])
        self.assertTrue(self.compositions().build(pid, saved['plan_id'])['path'])
        # Edits that keep the citations carry the saved copy forward.
        out = json.loads(self.handlers['rekindra_revise_world'](
            {'project_id': pid, 'plan_id': saved['plan_id'], 'edits': [{'field': 'title', 'value': 'Kept'}]}))
        self.assertTrue(out['ok'], out)
        kept = self.compositions().load_plan(pid, out['result']['plan_id'])
        self.assertEqual(kept['text_provenance'], saved['text_provenance'])
        # Rewording an interpretation reuses the saved quotes and rebuilds the interpretation.
        changed = copy.deepcopy(refs); changed[0]['interpretation'] = 'y'
        out = json.loads(self.handlers['rekindra_revise_world'](
            {'project_id': pid, 'plan_id': saved['plan_id'], 'edits': [{'field': 'text_references', 'value': changed}]}))
        self.assertTrue(out['ok'], out)
        reworded = self.compositions().load_plan(pid, out['result']['plan_id'])['text_provenance']
        self.assertEqual(reworded['recovered_evidence'], saved['text_provenance']['recovered_evidence'])
        self.assertEqual(reworded['interpretations'][0]['interpretation'], 'y')
        # A newly cited evidence_id still needs the live dossier, where it is absent.
        added = copy.deepcopy(refs); added[0]['evidence_ids'] = (added[0]['evidence_ids'] + [EV])[-4:]
        out = json.loads(self.handlers['rekindra_revise_world'](
            {'project_id': pid, 'plan_id': saved['plan_id'], 'edits': [{'field': 'text_references', 'value': added}]}))
        self.assertFalse(out['ok'], out)
        self.assertIn('was not recovered from asset', json.dumps(out))
        out = json.loads(self.handlers['rekindra_revise_world'](
            {'project_id': pid, 'plan_id': saved['plan_id'], 'edits': [{'field': 'text_references', 'value': None}]}))
        self.assertTrue(out['ok'], out)

    def test_carried_quotes_are_refused_once_intake_rejects_the_asset(self):
        # The plan stays loadable and can drop the citation; keeping it is refused.
        ids = self.evidence_for('notes.txt')
        pid, tga = self.project['project_id'], self.ids['photo.tga']
        refs = [{'asset_id': self.ids['notes.txt'], 'evidence_ids': ids[:1], 'interpretation': 'x'}]
        saved = self.compositions().save_plan(pid, self.world_with(refs), [tga], {})
        store = self.compositions()
        real = store.projects.status

        def rejected(project_id):
            project = real(project_id)
            for a in project['artifacts']:
                if a.get('kind') == 'evidence' and a.get('asset_id') == self.ids['notes.txt']:
                    a['status'] = 'rejected'
            return project
        store.projects.status = rejected
        parent = store.load_plan(pid, saved['plan_id'])
        with self.assertRaisesRegex(SceneError, 'rejected'):
            store.build(pid, saved['plan_id'])
        with self.assertRaisesRegex(SceneError, 'rejected'):
            store.save_plan(pid, self.world_with(refs), [tga], {}, parent=parent)
        dropped = store.save_plan(pid, world(tga), [tga], {}, parent=parent)
        self.assertNotIn('text_provenance', dropped)
        self.assertTrue(store.build(pid, dropped['plan_id'])['path'])

    def test_build_refuses_plan_citing_unsupported_source(self):
        ids = self.evidence_for('notes.txt')
        pid, tga = self.project['project_id'], self.ids['photo.tga']
        refs = [{'asset_id': self.ids['notes.txt'], 'evidence_ids': ids[:1], 'interpretation': 'x'}]
        store = self.compositions()
        saved = store.save_plan(pid, self.world_with(refs), [tga], {})
        real = store.projects.status

        def unsupported(project_id):
            project = real(project_id)
            for a in project['artifacts']:
                if a.get('kind') == 'evidence' and a.get('asset_id') == self.ids['notes.txt']:
                    a['status'] = 'unsupported'
            return project
        store.projects.status = unsupported
        with self.assertRaisesRegex(SceneError, 'unsupported'):
            store.build(pid, saved['plan_id'])

    def test_revise_drops_rejected_source_and_keeps_valid_one(self):
        from unittest import mock
        note_ids, zip_ids = self.evidence_for('notes.txt'), self.evidence_for('old.zip')
        pid, tga, note, zipped = self.project['project_id'], self.ids['photo.tga'], self.ids['notes.txt'], self.ids['old.zip']
        refs = [{'asset_id': note, 'evidence_ids': note_ids[:1], 'interpretation': 'x'},
                {'asset_id': zipped, 'evidence_ids': zip_ids[:1], 'interpretation': 'y'}]
        saved = self.compositions().save_plan(pid, self.world_with(refs), [tga], {})
        real = type(self.store).status

        def rejected(store, project_id):
            project = real(store, project_id)
            for a in project['artifacts']:
                if a.get('kind') == 'evidence' and a.get('asset_id') == note:
                    a['status'] = 'rejected'
            return project
        with mock.patch.object(type(self.store), 'status', rejected):
            out = json.loads(self.handlers['rekindra_revise_world'](
                {'project_id': pid, 'plan_id': saved['plan_id'], 'edits': [{'field': 'text_references', 'value': refs[1:]}]}))
            self.assertTrue(out['ok'], out)
            kept = self.compositions().load_plan(pid, out['result']['plan_id'])['text_provenance']
            self.assertTrue(self.compositions().build(pid, out['result']['plan_id'])['path'])
            with self.assertRaisesRegex(SceneError, 'rejected'):
                self.compositions().build(pid, saved['plan_id'])
        self.assertEqual({i['asset_id'] for i in kept['recovered_evidence']}, {zipped})
        self.assertEqual(kept['recovered_evidence'], saved['text_provenance']['recovered_evidence'][1:])

    def test_malformed_parent_quotes_are_ignored_not_crashed_on(self):
        ids = self.evidence_for('notes.txt')
        pid, tga = self.project['project_id'], self.ids['photo.tga']
        refs = [{'asset_id': self.ids['notes.txt'], 'evidence_ids': ids[:1], 'interpretation': 'x'}]
        parent = {'scene': self.world_with(refs), 'text_provenance': {'recovered_evidence': [
            {'asset_id': ['not', 'hashable'], 'evidence_id': {}}, 'junk', None]}}
        saved = self.compositions().save_plan(pid, self.world_with(refs), [tga], {}, parent=parent)
        self.assertEqual(saved['text_provenance']['recovered_evidence'][0]['evidence_id'], ids[0])
        for bad in (5, True, 'text', {'a': 1}):
            parent['text_provenance']['recovered_evidence'] = bad
            saved = self.compositions().save_plan(pid, self.world_with(refs), [tga], {}, parent=parent)
            self.assertEqual(saved['text_provenance']['recovered_evidence'][0]['evidence_id'], ids[0])

    def test_carried_quotes_do_not_need_the_live_dossier(self):
        ids = self.evidence_for('notes.txt')
        pid, tga = self.project['project_id'], self.ids['photo.tga']
        refs = [{'asset_id': self.ids['notes.txt'], 'evidence_ids': ids[:1], 'interpretation': 'x'}]
        saved = self.compositions().save_plan(pid, self.world_with(refs), [tga], {})
        evidence = self.store._project(pid) / 'artifacts' / 'evidence.json'
        evidence.write_bytes(evidence.read_bytes() + b' ')  # sha256 no longer matches the manifest
        reworded = copy.deepcopy(refs); reworded[0]['interpretation'] = 'y'
        out = json.loads(self.handlers['rekindra_revise_world'](
            {'project_id': pid, 'plan_id': saved['plan_id'], 'edits': [{'field': 'text_references', 'value': reworded}]}))
        self.assertTrue(out['ok'], out)
        added = copy.deepcopy(refs); added[0]['evidence_ids'] = ids[:1] + [EV]
        out = json.loads(self.handlers['rekindra_revise_world'](
            {'project_id': pid, 'plan_id': saved['plan_id'], 'edits': [{'field': 'text_references', 'value': added}]}))
        self.assertFalse(out['ok'], out)
        self.assertIn('Saved evidence', json.dumps(out))

    def test_world_and_revise_handlers_carry_text_references(self):
        ids = self.evidence_for('notes.txt')
        pid, tga = self.project['project_id'], self.ids['photo.tga']
        refs = [{'asset_id': self.ids['notes.txt'], 'evidence_ids': ids[:1], 'interpretation': 'x'}]
        out = json.loads(self.handlers['rekindra_create_world'](
            {'project_id': pid, 'asset_ids': [tga], 'scene': self.world_with(refs)}))
        self.assertTrue(out['ok'], out)
        plan_id = out['result']['plan_id']
        bad = copy.deepcopy(refs); bad[0]['evidence_ids'] = [EV]
        out = json.loads(self.handlers['rekindra_revise_world'](
            {'project_id': pid, 'plan_id': plan_id, 'edits': [{'field': 'text_references', 'value': bad}]}))
        self.assertFalse(out['ok'], out)
        out = json.loads(self.handlers['rekindra_revise_world'](
            {'project_id': pid, 'plan_id': plan_id, 'edits': [{'field': 'text_references', 'value': None}]}))
        self.assertTrue(out['ok'], out)
        revised = self.compositions().load_plan(pid, out['result']['plan_id'])
        self.assertNotIn('text_provenance', revised)


# Only the tests defined above run for the subclass; inherited recovery tests already run once.
for _name in [n for n in dir(recover_tests.RecoverEvidenceTests) if n.startswith('test_')]:
    if _name not in TextReferenceProvenanceTests.__dict__:
        setattr(TextReferenceProvenanceTests, _name, None)


if __name__ == '__main__':
    unittest.main()
