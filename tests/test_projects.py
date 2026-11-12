import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from rekindra_core.projects import ProjectStore, Limits, ProjectError
from test_tga import fixture


class ProjectTests(unittest.TestCase):
    def setUp(self):
        # Keep test inputs and transient files on the same drive as the repo.
        base = Path(__file__).resolve().parents[1] / '.local' / 'tests'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        self.store = ProjectStore(self.base / 'store')

    def test_snapshot_and_recovery_preserve_original_and_provenance(self):
        raw = fixture()
        source = self.source / 'vieille image émeraude.bin'
        source.write_bytes(raw)
        project = self.store.inspect(self.source)
        asset = project['assets'][0]
        self.assertEqual(asset['format'], 'tga')
        self.assertEqual(asset['source_path'], source.name)
        result = self.store.recover(project['project_id'], asset['asset_id'])
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(result['kind'], 'recovered')
        self.assertEqual(result['source_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(Path(result['path']).read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(self.store.status(project['project_id'])['artifacts'][0]['asset_id'], asset['asset_id'])
        self.assertEqual(self.store.recover(project['project_id'], asset['asset_id']), result)

    def test_recovery_uses_snapshot_after_source_disappears(self):
        source = self.source / 'image.tga'
        source.write_bytes(fixture())
        p = self.store.inspect(self.source)
        source.unlink()
        result = self.store.recover(p['project_id'], p['assets'][0]['asset_id'])
        self.assertTrue(Path(result['path']).is_file())

    def test_modified_snapshot_is_rejected(self):
        (self.source / 'image.tga').write_bytes(fixture())
        p = self.store.inspect(self.source)
        asset = p['assets'][0]
        (self.store.root / p['project_id'] / 'originals' / asset['asset_id']).write_bytes(fixture(b'\0\0\0'))
        with self.assertRaisesRegex(ProjectError, 'integrity'):
            self.store.recover(p['project_id'], asset['asset_id'])

    def test_unknown_and_bad_tga_do_not_prevent_good_recovery(self):
        (self.source / 'unknown.bin').write_bytes(b'\x01\xff\0')
        (self.source / 'bad.tga').write_bytes(b'broken')
        (self.source / 'good.tga').write_bytes(fixture())
        p = self.store.inspect(self.source)
        by_name = {a['source_path']: a for a in p['assets']}
        self.assertEqual(by_name['unknown.bin']['format'], 'unknown')
        for name in ('unknown.bin', 'bad.tga'):
            with self.assertRaises(ProjectError):
                self.store.recover(p['project_id'], by_name[name]['asset_id'])
        self.assertEqual(self.store.recover(p['project_id'], by_name['good.tga']['asset_id'])['kind'], 'recovered')

    def test_excludes_credentials_and_hidden_vcs(self):
        (self.source / '.env').write_text('secret')
        (self.source / '.git').mkdir()
        (self.source / '.git' / 'config').write_text('private')
        (self.source / 'notes.txt').write_text('visible')
        p = self.store.inspect(self.source)
        self.assertEqual([a['source_path'] for a in p['assets']], ['notes.txt'])

    def test_excludes_common_credential_stores(self):
        for folder in ('.hermes', '.claude', '.codex', '.kube', '.Docker'):
            (self.source / folder).mkdir()
            (self.source / folder / 'config.json').write_text('private')
        (self.source / '.config' / 'gcloud').mkdir(parents=True)
        (self.source / '.config' / 'gcloud' / 'access_tokens.db').write_text('private')
        (self.source / '.config' / 'palette.txt').write_text('visible')
        # Only the cloud SDK folder under .config is a credential store.
        (self.source / 'gcloud').mkdir()
        (self.source / 'gcloud' / 'notes.txt').write_text('visible')
        secrets = ('auth.json', 'credentials', 'Credentials.json', 'server.pem', 'id_rsa', 'id_ed25519.pub',
                   'id_work', '.netrc', '.git-credentials')
        for name in secrets:
            (self.source / name).write_text('private')
        # Key files have no extension or end in .pub; an old image that happens to start with id_ is kept.
        (self.source / 'id_logo.tga').write_bytes(fixture())
        (self.source / 'notes.txt').write_text('visible')
        p = self.store.inspect(self.source)
        self.assertEqual(sorted(a['source_path'] for a in p['assets']),
                         ['.config/palette.txt', 'gcloud/notes.txt', 'id_logo.tga', 'notes.txt'])
        skipped = {row['source_path'] for row in p['skipped'] if row['reason'].startswith('excluded')}
        self.assertEqual(skipped, {'.hermes', '.claude', '.codex', '.kube', '.Docker', '.config/gcloud', *secrets})

    def test_rejects_source_store_overlap(self):
        for store in (ProjectStore(self.source / 'store'), ProjectStore(self.base)):
            with self.assertRaises(ProjectError):
                store.inspect(self.source)

    def test_limits_are_enforced_with_reported_skips(self):
        (self.source / 'a.tga').write_bytes(fixture())
        (self.source / 'b.txt').write_bytes(b'x' * 30)
        store = ProjectStore(self.base / 'store', limits=Limits(max_file_bytes=25, max_total_bytes=25))
        p = store.inspect(self.source)
        self.assertEqual(len(p['assets']), 1)
        self.assertTrue(p['skipped'])
        self.assertLessEqual(sum(a['size'] for a in p['assets']), 25)

    def test_file_count_limit(self):
        for name in ('a', 'b', 'c'):
            (self.source / name).write_text(name)
        store = ProjectStore(self.base / 'store', limits=Limits(max_files=2))
        p = store.inspect(self.source)
        self.assertEqual(len(p['assets']), 2)
        self.assertTrue(p['truncated'])

    def test_traversal_and_unknown_identifiers_are_rejected(self):
        for invalid in ('../source', '/etc', 'a'*31, 'z'*32):
            with self.assertRaises(ProjectError):
                self.store.status(invalid)
        with self.assertRaises(ProjectError):
            self.store.status('a'*32)

    def test_symlink_is_not_followed(self):
        target = self.base / 'private'
        target.mkdir()
        (target / 'secret').write_text('do not read')
        try:
            os.symlink(target, self.source / 'linked', target_is_directory=True)
        except OSError:
            self.skipTest('Host does not permit creating symlinks')
        p = self.store.inspect(self.source)
        self.assertEqual(p['assets'], [])
        self.assertTrue(p['skipped'])

    def test_malformed_manifest_has_actionable_failure(self):
        p = self.store.inspect(self.source)
        (self.store.root / p['project_id'] / 'project.json').write_text('{')
        with self.assertRaises(ProjectError):
            self.store.status(p['project_id'])

    def test_invalid_manifest_entries_fail_before_artifact_writes(self):
        (self.source / 'image.tga').write_bytes(fixture())
        p = self.store.inspect(self.source)
        asset_id = p['assets'][0]['asset_id']
        manifest = self.store.root / p['project_id'] / 'project.json'
        for field, values in (('artifacts', [None]), ('assets', [None]),
                              ('assets', [{'asset_id': asset_id, 'sha256': 17}])):
            invalid = dict(p)
            invalid[field] = values
            manifest.write_text(json.dumps(invalid))
            with self.subTest(field=field, values=values):
                with self.assertRaises(ProjectError):
                    self.store.recover(p['project_id'], asset_id)
                self.assertEqual(list((manifest.parent / 'artifacts').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
