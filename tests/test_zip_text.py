import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import zipfile

from test_worlds import world
import test_recover_evidence as rt
from test_tga import fixture
from rekindra_core.compositions import CompositionStore
from rekindra_core.projects import ProjectStore
from rekindra_core.scenes import SceneError
from rekindra_core import zip_text
from rekindra_intake import inspect_archive, inspect_text

KEEPER = ('Keeper log, winter 1931.\n\nThe lamp was lit at dusk and the fog came in from the north. '
          'Beam turned all night.\n')


def make_zip(members, compression=zipfile.ZIP_DEFLATED):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression) as archive:
        for name, body in members:
            archive.writestr(name, body)
    return buffer.getvalue()


def set_encrypted(data):
    """Flip the encrypted flag on every member: stdlib cannot write encrypted ZIPs."""
    out = bytearray(data)
    for sig, offset in ((b'PK\x03\x04', 6), (b'PK\x01\x02', 8)):
        at = out.find(sig)
        while at != -1:
            flags = struct.unpack_from('<H', out, at + offset)[0]
            struct.pack_into('<H', out, at + offset, flags | 1)
            at = out.find(sig, at + 4)
    return bytes(out)


def corrupt_member(data, name):
    """Damage the member's compressed bytes so decompression or its checksum fails."""
    out = bytearray(data)
    start = out.find(name.encode()) + len(name)
    for i in range(start + 2, start + 12):
        out[i] ^= 0x5A
    return bytes(out)


def read(data, name='archive.zip', **kw):
    return zip_text.read_archive_text(inspect_archive(data, name), data, inspect_text, **kw)


class ReaderTests(unittest.TestCase):
    def test_bomb_rejected_with_reason(self):
        out = read(make_zip([('notes/big.txt', b'a' * (2 * 1024 * 1024))]))
        self.assertEqual(out['status'], 'rejected')
        self.assertEqual(out['text_member_report']['refused']['code'], 'zip_bomb_guard')
        self.assertIn('100:1', out['text_member_report']['refused']['reason'])
        self.assertEqual(out['text_members'], [])

    def test_total_claimed_cap_rejected(self):
        # Random-looking stored data: ratio is fine, the total is not.
        body = bytes(range(256)) * 1024
        env = inspect_archive(make_zip([('a.txt', body)], zipfile.ZIP_STORED), 'a.zip')
        env['facts']['entries'][0]['claimed_uncompressed_size_bytes'] = zip_text.MAX_TOTAL_CLAIMED_BYTES + 1
        out = zip_text.read_archive_text(env, make_zip([('a.txt', body)], zipfile.ZIP_STORED), inspect_text)
        self.assertEqual((out['status'], out['text_member_report']['refused']['code']), ('rejected', 'zip_bomb_guard'))

    def test_encrypted_rejected_with_reason(self):
        out = read(set_encrypted(make_zip([('notes/keeper.txt', KEEPER)])))
        self.assertEqual(out['status'], 'rejected')
        self.assertEqual(out['text_member_report']['refused']['code'], 'encrypted_archive')
        self.assertEqual(out['text_member_report']['skipped'][0]['code'], 'encrypted_member')

    def test_corrupt_rejected_with_reason(self):
        out = read(corrupt_member(make_zip([('notes/keeper.txt', KEEPER)]), 'notes/keeper.txt'))
        self.assertEqual(out['status'], 'rejected')
        self.assertEqual(out['text_member_report']['refused']['code'], 'corrupt_archive')

    def test_not_a_zip_stays_rejected_by_intake(self):
        out = read(b'PK\x03\x04 this is not really a zip')
        self.assertEqual(out['status'], 'rejected')
        self.assertNotIn('text_members', out)

    def test_mixed_archive_is_partial_with_reasons(self):
        data = make_zip([('good.txt', KEEPER), ('bad.txt', KEEPER * 3), ('inner.zip', b'PK'), ('photo.png', b'x'),
                         ('notes/', b'')])
        data = corrupt_member(data, 'bad.txt')
        out = read(data)
        self.assertEqual(out['status'], 'partial')
        self.assertEqual([m['name'] for m in out['text_members']], ['good.txt'])
        codes = {s['name']: s['code'] for s in out['text_member_report']['skipped']}
        self.assertEqual(codes, {'bad.txt': 'corrupt_member', 'inner.zip': 'nested_archive_not_read',
                                 'photo.png': 'unsupported_member_type'})

    def test_clean_archive_with_nested_only_extra_stays_ok(self):
        out = read(make_zip([('a.md', '# Title\nbody\n'), ('photo.png', b'x')]))
        self.assertEqual(out['status'], 'ok')
        self.assertEqual(out['text_member_report']['read'], 1)

    def test_oversized_member_skipped(self):
        body = bytes(i * 7 % 251 for i in range(zip_text.MAX_MEMBER_BYTES + 10))
        out = read(make_zip([('big.txt', body), ('ok.txt', 'fine')], zipfile.ZIP_STORED))
        self.assertEqual([m['name'] for m in out['text_members']], ['ok.txt'])
        self.assertEqual(out['text_member_report']['skipped'][0]['code'], 'member_too_large')
        self.assertEqual(out['status'], 'partial')

    def test_member_count_capped(self):
        names = [(f'n{i}.txt', 'note') for i in range(zip_text.MAX_TEXT_MEMBERS + 2)]
        out = read(make_zip(names))
        self.assertEqual(len(out['text_members']), zip_text.MAX_TEXT_MEMBERS)
        self.assertEqual({s['code'] for s in out['text_member_report']['skipped']}, {'member_limit'})

    def test_time_budget_stops_reading(self):
        ticks = iter([0.0] + [100.0] * 50)
        out = read(make_zip([('a.txt', 'one'), ('b.txt', 'two')]), clock=lambda: next(ticks))
        self.assertEqual(out['text_members'], [])
        self.assertEqual({s['code'] for s in out['text_member_report']['skipped']}, {'time_budget_exhausted'})

    def test_path_traversal_member_not_read(self):
        out = read(make_zip([('../evil.txt', 'nope'), ('ok.txt', 'fine')]))
        self.assertEqual([m['name'] for m in out['text_members']], ['ok.txt'])
        self.assertEqual(out['text_member_report']['skipped'][0]['code'], 'unsafe_member')

    def test_compressible_unread_member_does_not_refuse_archive(self):
        out = read(make_zip([('texture.tga', b'\0' * (512 * 1024)), ('a.txt', 'fine')]))
        self.assertEqual(out['status'], 'ok')
        self.assertEqual(out['text_member_report']['read'], 1)
        self.assertIn('unread_members_compress_heavily', [w['code'] for w in out['warnings']])

    def test_one_bad_note_among_other_entries_is_partial(self):
        out = read(make_zip([('photo.tga', b'x' * 40), ('bad.log', b'\x00\x01\x02' * 40)]))
        self.assertEqual(out['status'], 'partial')
        self.assertNotIn('refused', out['text_member_report'])
        self.assertTrue(out['facts']['entries'])

    def test_name_the_dossier_would_refuse_is_skipped(self):
        out = read(make_zip([('a\u2028b.txt', 'nope'), ('.. /c.txt', 'nope'), ('ok.txt', 'fine')]))
        self.assertEqual([m['name'] for m in out['text_members']], ['ok.txt'])
        self.assertEqual({s['code'] for s in out['text_member_report']['skipped']}, {'unsafe_member'})

    def test_fit_members_reports_what_it_leaves_out(self):
        out = zip_text.fit_members(read(make_zip([('a.txt', 'one'), ('b.txt', 'two')])), 'x.zip', 1)
        self.assertEqual([m['name'] for m in out['text_members']], ['a.txt'])
        self.assertEqual(out['status'], 'partial')
        self.assertEqual(out['text_member_report']['read'], 1)
        self.assertEqual(out['text_member_report']['skipped'][0]['code'], 'project_source_limit')

    def test_fit_members_reports_over_long_paths(self):
        parent = 'p/' * 200 + 'x.zip'
        out = zip_text.fit_members(read(make_zip([('n' * 150 + '.txt', 'one'), ('b.txt', 'two')])), parent, 5)
        self.assertEqual([m['name'] for m in out['text_members']], ['b.txt'])
        self.assertEqual(out['text_member_report']['skipped'][0]['code'], 'member_path_too_long')

    def test_limits_match_the_dossier(self):
        from rekindra_evidence import _limits
        self.assertEqual((zip_text.MAX_DOSSIER_SOURCES, zip_text.MAX_DOSSIER_PATH),
                         (_limits.MAX_RECORDS, _limits.MAX_PATH_CHARS))

    def test_binary_text_member_is_reported(self):
        out = read(make_zip([('a.txt', b'\x00\x01\x02' * 40), ('b.txt', 'fine')]))
        self.assertEqual(out['text_member_report']['skipped'][0]['code'], 'text_intake_rejected')
        self.assertEqual(out['status'], 'partial')


class PipelineTests(unittest.TestCase):
    def setUp(self):
        base = rt.ROOT / '.local' / 'tests'
        base.mkdir(parents=True, exist_ok=True)
        self._temp = tempfile.TemporaryDirectory(dir=base)
        temp = Path(self._temp.name)
        self.source = temp / 'input'
        self.source.mkdir()
        self.bytes = make_zip([('notes/keeper.txt', KEEPER), ('inner.zip', b'PK'),
                               ('notes/data.csv', 'year,lamp\n1931,lit\n')])
        (self.source / 'archive.zip').write_bytes(self.bytes)
        (self.source / 'bomb.zip').write_bytes(make_zip([('big.txt', b'a' * (2 * 1024 * 1024))]))
        (self.source / 'locked.zip').write_bytes(set_encrypted(make_zip([('s.txt', KEEPER)])))
        (self.source / 'photo.tga').write_bytes(fixture())
        self.store = ProjectStore(temp / 'projects')
        self.project = self.store.inspect(self.source)
        self.pid = self.project['project_id']
        self.ids = {a['source_path']: a['asset_id'] for a in self.project['assets']}
        self.temp = temp

    def tearDown(self):
        self._temp.cleanup()

    def recover(self, name):
        return self.store.recover(self.pid, self.ids[name], rt.plugin.handlers.evidence_reader())

    def test_member_evidence_has_provenance_and_exact_ranges(self):
        out = self.recover('archive.zip')
        sid = self.ids['archive.zip']
        rows = {row['source_id']: row for row in out['dossier']['sources']}
        keeper = next(r for r in rows.values() if r['relative_path'] == 'archive.zip!notes/keeper.txt')
        self.assertTrue(keeper['source_id'].startswith(sid + ':'))
        self.assertTrue(rows[sid]['coverage']['member_contents_inspected'])
        items = [e for e in out['dossier']['evidence'] if e['source_id'] == keeper['source_id']]
        spans = [e for e in items if 'char_start' in (e.get('locator') or {})]
        self.assertTrue(spans)
        for item in spans:
            start, end = item['locator']['char_start'], item['locator']['char_end']
            self.assertEqual(KEEPER[start:end], item['text'])

    def test_summary_lists_member_evidence_first_with_paths(self):
        summary = rt.plugin.handlers.evidence_summary(self.recover('archive.zip'))
        self.assertEqual(summary['evidence'][0]['member_path'], 'archive.zip!notes/keeper.txt')
        self.assertEqual(summary['text_members']['read'], 2)
        self.assertEqual(summary['text_members']['skipped'][0]['code'], 'nested_archive_not_read')
        self.assertNotIn('member contents were not read', summary['guidance'])

    def test_bad_archives_reach_the_summary_with_reasons(self):
        for name, code in (('bomb.zip', 'zip_bomb_guard'), ('locked.zip', 'encrypted_archive')):
            summary = rt.plugin.handlers.evidence_summary(self.recover(name))
            self.assertEqual(summary['intake_status'], 'rejected', name)
            self.assertEqual(summary['text_members']['refused']['code'], code)
            self.assertEqual(summary['evidence_count'], 0)

    def test_text_reference_resolves_and_survives_reload(self):
        out = self.recover('archive.zip')
        sid = self.ids['archive.zip']
        item = next(e for e in out['dossier']['evidence']
                    if e['source_id'].startswith(sid + ':') and 'lamp was lit' in e['text'])
        refs = [{'asset_id': sid, 'evidence_ids': [item['evidence_id']], 'interpretation': 'A lamp against fog.'}]
        scene = world(self.ids['photo.tga'])
        scene['text_references'] = refs
        compositions = CompositionStore(self.store)
        saved = compositions.save_plan(self.pid, scene, [self.ids['photo.tga']], {'origin': 'test'})
        [quote] = saved['text_provenance']['recovered_evidence']
        self.assertEqual(quote['source_path'], 'archive.zip!notes/keeper.txt')
        self.assertEqual(quote['member_source_id'], item['source_id'])
        loaded = compositions.load_plan(self.pid, saved['plan_id'])
        self.assertEqual(loaded['text_provenance'], saved['text_provenance'])

    def test_other_archives_member_cannot_be_cited(self):
        out = self.recover('archive.zip')
        sid = self.ids['archive.zip']
        item = next(e for e in out['dossier']['evidence'] if e['source_id'].startswith(sid + ':'))
        scene = world(self.ids['photo.tga'])
        scene['text_references'] = [{'asset_id': self.ids['locked.zip'], 'evidence_ids': [item['evidence_id']],
                                     'interpretation': 'x'}]
        with self.assertRaises(SceneError):
            CompositionStore(self.store).save_plan(self.pid, scene, [self.ids['photo.tga']], {})

    def test_members_cannot_use_up_the_project_source_limit(self):
        for i in range(5):
            names = [(f'n{j}.txt', f'note {i} {j}') for j in range(zip_text.MAX_TEXT_MEMBERS)]
            (self.source / f'many{i}.zip').write_bytes(make_zip(names))
        project = self.store.inspect(self.source)
        pid, ids = project['project_id'], {a['source_path']: a['asset_id'] for a in project['assets']}
        reader = rt.plugin.handlers.evidence_reader()
        for i in range(5):
            out = self.store.recover(pid, ids[f'many{i}.zip'], reader)
        # 128 slots, 8 evidence assets keep one each, so 120 members fit across the archives.
        self.assertEqual(out['dossier']['counts']['sources'], 5 + 120)
        report = out['artifact']['text_members']
        self.assertEqual(report['read'], 0)
        self.assertEqual(report['skipped'][0]['code'], 'project_source_limit')

    def test_source_unchanged_and_nothing_extracted(self):
        before = sorted(p.name for p in self.source.rglob('*'))
        with mock.patch('zipfile.ZipFile.extract', side_effect=AssertionError), \
                mock.patch('zipfile.ZipFile.extractall', side_effect=AssertionError):
            self.recover('archive.zip')
        self.assertEqual((self.source / 'archive.zip').read_bytes(), self.bytes)
        self.assertEqual(sorted(p.name for p in self.source.rglob('*')), before)
        artifacts = [p.name for p in (self.store._project(self.pid) / 'artifacts').iterdir()]
        self.assertFalse([n for n in artifacts if 'keeper' in n or n.endswith('.txt')])


if __name__ == '__main__':
    unittest.main()
