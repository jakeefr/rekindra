import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import zipfile
import zlib

from test_worlds import world
import test_recover_evidence as rt
from test_tga import fixture
from rekindra_core.compositions import CompositionStore
from rekindra_core.projects import ProjectStore, _stored_intake_size
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


SEEN = b'Text in the directory intake inventoried.\n'
UNSEEN = b'Text from a directory intake never walked.\n'


def local(name, body):
    return struct.pack('<4sHHHHHIIIHH', b'PK\x03\x04', 20, 0, 0, 0, 0, zlib.crc32(body),
                       len(body), len(body), len(name), 0) + name + body


def central(name, body, offset):
    return struct.pack('<4sHHHHHHIIIHHHHHII', b'PK\x01\x02', 20, 20, 0, 0, 0, 0, zlib.crc32(body),
                       len(body), len(body), len(name), 0, 0, 0, 0, 0, offset) + name


def end(cd_size, cd_offset, comment_len):
    return struct.pack('<4sHHHHIIH', b'PK\x05\x06', 0, 0, 1, 1, cd_size, cd_offset, comment_len)


def late_end_record_zip():
    """One end record reaches end of file exactly, so intake calls the archive ``ok``.

    A second sits in its comment, in the last 22 bytes, claiming a one-byte comment that is
    not there. Intake ignores it; stdlib zipfile takes the last signature and reads directory B.
    """
    name = b'notes/tide.txt'
    first, directory_a = local(name, SEEN), central(name, SEEN, 0)
    second_at = len(first) + len(directory_a) + 22
    second = local(name, UNSEEN)
    directory_b = central(name, UNSEEN, second_at)
    tail = second + directory_b + end(len(directory_b), second_at + len(second), 1)
    return first + directory_a + end(len(directory_a), len(first), len(tail)) + tail


def two_directory_zip():
    """Two end records: intake inventories directory A, stdlib zipfile would read directory B.

    From docs/acceptance/live-wiring-audit-af67b55.md, finding 1. B hides in A's comment and
    declares itself 100 bytes early, so each reader settles on a different directory.
    """
    name = b'notes/tide.txt'
    first, directory_a = local(name, SEEN), central(name, SEEN, 0)
    second_at = len(first) + len(directory_a) + 22
    second = local(name, UNSEEN)
    directory_b = central(name, UNSEEN, second_at - 100)
    tail = second + directory_b + end(len(directory_b), second_at + len(second) - 100, 0)
    return first + directory_a + end(len(directory_a), len(first), len(tail)) + tail


class ReaderTests(unittest.TestCase):
    def test_bomb_rejected_with_reason(self):
        out = read(make_zip([('notes/big.txt', b'a' * (zip_text.BOMB_FLOOR_BYTES + 1))]))
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

    def test_oversized_compressible_note_is_skipped_not_refused(self):
        out = read(make_zip([('big.csv', b'a' * (1024 * 1024)), ('ok.txt', 'fine')]))
        self.assertEqual(out['status'], 'partial')
        self.assertEqual([m['name'] for m in out['text_members']], ['ok.txt'])
        self.assertEqual(out['text_member_report']['skipped'][0]['code'], 'member_too_large')
        self.assertTrue(out['facts']['entries'])

    def test_large_log_at_ordinary_ratio_is_skipped_not_refused(self):
        data = make_zip([('server.log', 'x'), ('ok.txt', 'fine')])
        env = inspect_archive(data, 'a.zip')
        env['facts']['entries'][0]['claimed_uncompressed_size_bytes'] = 70 * 1024 * 1024
        env['facts']['entries'][0]['compressed_size_bytes'] = 7 * 1024 * 1024
        out = zip_text.read_archive_text(env, data, inspect_text)
        self.assertEqual(out['text_member_report']['skipped'][0]['code'], 'member_too_large')
        self.assertEqual([m['name'] for m in out['text_members']], ['ok.txt'])

    def test_small_heavily_compressed_note_reported_per_member(self):
        out = read(make_zip([('blank.txt', b'a' * (200 * 1024)), ('ok.txt', 'fine')]))
        self.assertEqual(out['text_member_report']['skipped'][0]['code'], 'member_compresses_heavily')
        self.assertEqual([m['name'] for m in out['text_members']], ['ok.txt'])

    def test_total_read_is_capped(self):
        with mock.patch.object(zip_text, 'MAX_TOTAL_READ_BYTES', 10):
            out = read(make_zip([('a.txt', 'eight ch'), ('b.txt', 'eight ch')]))
        self.assertEqual([m['name'] for m in out['text_members']], ['a.txt'])
        self.assertEqual(out['text_member_report']['skipped'][0]['code'], 'total_read_limit')

    def test_members_past_the_read_limit_are_never_opened(self):
        data = make_zip([('a.txt', 'eight ch'), ('b.txt', 'eight ch'), ('c.txt', 'eight ch')])
        with mock.patch.object(zip_text, 'MAX_TOTAL_READ_BYTES', 10), \
                mock.patch.object(zipfile.ZipFile, 'open', autospec=True, side_effect=zipfile.ZipFile.open) as opened:
            out = read(data)
        self.assertEqual([call.args[1].filename for call in opened.call_args_list], ['a.txt'])
        self.assertEqual([s['code'] for s in out['text_member_report']['skipped']], ['total_read_limit'] * 2)

    def test_failed_reads_count_against_the_read_limit(self):
        data = corrupt_member(make_zip([('a.txt', KEEPER), ('b.txt', KEEPER)]), 'a.txt')
        with mock.patch.object(zip_text, 'MAX_TOTAL_READ_BYTES', len(KEEPER) + 1):
            out = read(data)
        self.assertEqual([s['code'] for s in out['text_member_report']['skipped']],
                         ['corrupt_member', 'total_read_limit'])

    def test_older_manifests_are_sized_from_the_saved_intake(self):
        with tempfile.TemporaryDirectory() as folder:
            root, asset_id = Path(folder), 'a' * 32
            (root / f'{asset_id}.intake.json').write_bytes(b'x' * 900)
            self.assertEqual(_stored_intake_size(root, {'asset_id': asset_id}), 900)
            self.assertEqual(_stored_intake_size(root, {'asset_id': asset_id, 'intake_bytes': 5}), 5)
            self.assertEqual(_stored_intake_size(root, {'asset_id': '../escape'}), 0)

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
        self.assertEqual((zip_text.MAX_DOSSIER_SOURCES, zip_text.MAX_DOSSIER_PATH, zip_text.MAX_DOSSIER_INPUT_BYTES),
                         (_limits.MAX_RECORDS, _limits.MAX_PATH_CHARS, _limits.MAX_INPUT_BYTES))

    def test_two_end_records_are_never_read(self):
        data = two_directory_zip()
        with mock.patch.object(zipfile.ZipFile, 'open', autospec=True, side_effect=zipfile.ZipFile.open) as opened:
            out = read(data, 'pack.zip')
        self.assertIn('multiple_eocd_candidates', [w['code'] for w in out['warnings']])
        self.assertEqual(opened.call_count, 0)
        self.assertEqual(out['text_members'], [])
        self.assertEqual(out['text_member_report']['refused']['code'], 'ambiguous_archive')
        self.assertEqual(out['text_member_report']['read'], 0)
        # The inventory intake did finish is kept: only member contents are withheld.
        self.assertEqual(out['status'], 'partial')
        self.assertEqual([e['name'] for e in out['facts']['entries']], ['notes/tide.txt'])
        self.assertIn('ambiguous_archive', [w['code'] for w in out['warnings']])

    def test_late_end_record_in_an_ok_archive_is_never_read(self):
        data = late_end_record_zip()
        # The two readers really do disagree, and intake raises no flag about it.
        self.assertEqual(inspect_archive(data, 'pack.zip')['status'], 'ok')
        self.assertEqual(zipfile.ZipFile(io.BytesIO(data)).read('notes/tide.txt'), UNSEEN)
        with mock.patch.object(zipfile.ZipFile, 'open', autospec=True, side_effect=zipfile.ZipFile.open) as opened:
            out = read(data, 'pack.zip')
        self.assertEqual(opened.call_count, 0)
        self.assertEqual(out['text_members'], [])
        self.assertEqual(out['text_member_report']['refused']['code'], 'ambiguous_archive')
        self.assertEqual(out['status'], 'partial')
        self.assertEqual([e['name'] for e in out['facts']['entries']], ['notes/tide.txt'])

    def test_end_signature_inside_a_member_does_not_withhold_the_archive(self):
        # A stored nested archive carries its own end record, but it sits before the real one.
        inner = make_zip([('deep.txt', 'inside')])
        out = read(make_zip([('inner.zip', inner), ('a.txt', 'fine')], zipfile.ZIP_STORED))
        self.assertEqual([m['name'] for m in out['text_members']], ['a.txt'])
        self.assertNotIn('refused', out['text_member_report'])

    def test_partial_archive_is_never_read(self):
        data = make_zip([('a.txt', 'fine')]) + b'bytes after the end record'
        with mock.patch.object(zipfile.ZipFile, 'open', autospec=True, side_effect=zipfile.ZipFile.open) as opened:
            out = read(data)
        self.assertEqual(inspect_archive(data, 'archive.zip')['status'], 'partial')
        self.assertEqual(opened.call_count, 0)
        self.assertEqual(out['text_members'], [])
        refused = out['text_member_report']['refused']
        self.assertEqual(refused['code'], 'partial_archive_not_read')
        self.assertIn('trailing_data', refused['reason'])
        self.assertEqual(out['status'], 'partial')
        self.assertEqual([e['name'] for e in out['facts']['entries']], ['a.txt'])

    def test_member_that_disagrees_with_the_inventory_is_skipped(self):
        data = make_zip([('a.txt', 'one'), ('b.txt', 'two')])
        for field, value in (('claimed_crc32', '00000000'), ('compressed_size_bytes', 9999),
                             ('claimed_uncompressed_size_bytes', 7), ('compression_method', 99)):
            env = inspect_archive(data, 'a.zip')
            env['facts']['entries'][0][field] = value
            out = zip_text.read_archive_text(env, data, inspect_text)
            self.assertEqual([m['name'] for m in out['text_members']], ['b.txt'], field)
            self.assertEqual(out['text_member_report']['skipped'][0]['code'], 'unsafe_member', field)

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
        (self.source / 'bomb.zip').write_bytes(make_zip([('big.txt', b'a' * (zip_text.BOMB_FLOOR_BYTES + 1))]))
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

    def test_two_end_records_give_inventory_but_no_member_text(self):
        (self.source / 'pack.zip').write_bytes(two_directory_zip())
        project = self.store.inspect(self.source)
        pid, ids = project['project_id'], {a['source_path']: a['asset_id'] for a in project['assets']}
        out = self.store.recover(pid, ids['pack.zip'], rt.plugin.handlers.evidence_reader())
        texts = [e.get('text') or '' for e in out['dossier']['evidence']]
        self.assertFalse([t for t in texts if 'never walked' in t or 'intake inventoried' in t])
        self.assertIn('notes/tide.txt', texts)
        self.assertFalse([s for s in out['dossier']['sources'] if ':' in s['source_id']])
        summary = rt.plugin.handlers.evidence_summary(out)
        self.assertEqual(summary['intake_status'], 'partial')
        self.assertEqual(summary['text_members']['refused']['code'], 'ambiguous_archive')
        self.assertEqual(summary['text_members']['read'], 0)

    def test_recover_reply_fits_the_host_result_floor(self):
        # docs/acceptance/live-wiring-audit-af67b55.md, finding 3: long names made the reply
        # 14,969 characters with the untrusted label at 4,189, past the host's 1,500 preview.
        note = 'The harbour bell rang twice at low tide while the ferry waited at the north quay. ' * 4
        members = [(f'notes/{"long-folder-name-" * 10}{i:02d}/note{i:02d}.txt', note) for i in range(40)]
        members += [(f'bin/{"x" * 186}{i:03d}.bin', b'\0' * 16) for i in range(40)]
        source = self.temp / 'wide'
        source.mkdir()
        (source / 'wide.zip').write_bytes(make_zip(members))
        handlers = rt.plugin.handlers
        tools = handlers.make_handlers(store_factory=lambda: self.store)
        project = json.loads(tools['rekindra_inspect']({'folder': str(source)}))['result']
        asset_id = project['assets'][0]['asset_id']
        raw = tools['rekindra_recover']({'project_id': project['project_id'], 'asset_id': asset_id})
        self.assertLessEqual(len(raw), handlers.SUMMARY_MAX_CHARS)
        self.assertLessEqual(handlers.SUMMARY_MAX_CHARS, 8_000)
        self.assertLess(raw.index('"untrusted_content"'), 1_500)
        self.assertLess(raw.index('"notice"'), 1_500)
        summary = json.loads(raw)['result']
        members_view = summary['text_members']
        self.assertEqual(members_view['read'], zip_text.MAX_TEXT_MEMBERS)
        self.assertLessEqual(len(members_view['skipped']), handlers.SUMMARY_SKIPPED)
        self.assertTrue(all(len(s['name']) <= handlers.SUMMARY_NAME_CHARS for s in members_view['skipped']))
        self.assertRegex(members_view['skipped_truncated'], r'^truncated, \d+ more')
        self.assertEqual(sum(members_view['skipped_counts'].values()) + members_view['skipped_uncounted'],
                         len(members_view['skipped']) + int(members_view['skipped_truncated'].split()[1]))
        self.assertTrue(summary['evidence'])
        self.assertRegex(summary['evidence_truncated'], r'^truncated, \d+ more')
        self.assertEqual(int(summary['evidence_truncated'].split()[1]), summary['evidence_omitted_from_summary'])
        self.assertEqual(summary['evidence_count'],
                         len(summary['evidence']) + summary['evidence_omitted_from_summary'])
        # Only the first view is compacted: the saved intake keeps every reported skip and reason.
        stored = json.loads(next((self.temp / 'projects').rglob(f'{asset_id}.intake.json')).read_text('utf-8'))
        self.assertGreater(len(stored['text_member_report']['skipped']), handlers.SUMMARY_SKIPPED)
        self.assertTrue(all(s.get('reason') for s in stored['text_member_report']['skipped']))

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

    def test_multibyte_members_stay_within_the_dossier_input_limit(self):
        for i in range(3):
            names = [(f'n{j}.txt', ('\u706f\u53f0\u306e\u8a18\u9332 %d %d\u3002' % (i, j)) * 400)
                     for j in range(zip_text.MAX_TEXT_MEMBERS)]
            (self.source / f'wide{i}.zip').write_bytes(make_zip(names))
        project = self.store.inspect(self.source)
        pid, ids = project['project_id'], {a['source_path']: a['asset_id'] for a in project['assets']}
        reader = rt.plugin.handlers.evidence_reader()
        reports = [self.store.recover(pid, ids[f'wide{i}.zip'], reader)['artifact']['text_members'] for i in range(3)]
        self.assertEqual(reports[0]['read'], zip_text.MAX_TEXT_MEMBERS)
        self.assertLess(reports[2]['read'], zip_text.MAX_TEXT_MEMBERS)
        self.assertIn('project_evidence_size_limit', {s['code'] for s in reports[2]['skipped']})
        # A whole text asset still fits after the members have taken their share.
        self.assertEqual(self.store.recover(pid, ids['archive.zip'], reader)['artifact']['intake_format'], 'zip')

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
