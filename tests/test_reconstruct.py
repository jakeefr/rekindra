import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest

import test_recover_evidence as recover_tests
from test_image_recovery import encoded, noise
from test_recover_evidence import NOTE
from test_worlds import world
from rekindra_core.compositions import CompositionStore

HOSTILE = '<script>alert(1)</script> "><img src=x onerror=alert(2)> ‮gnp.exe\x07 &amp;'


class ReconstructTests(recover_tests.RecoverEvidenceTests):
    """rekindra_reconstruct through the registered handler, against a real project."""

    def setUp(self):
        super().setUp()
        self.pid = self.project['project_id']

    def reinspect(self):
        inspected = json.loads(self.handlers['rekindra_inspect']({'folder': str(self.source)}))
        self.assertTrue(inspected['ok'], inspected)
        self.project = inspected['result']
        self.pid = self.project['project_id']
        self.ids = {a['source_path']: a['asset_id'] for a in self.project['assets']}

    def evidence_for(self, name):
        out = self.recover(name)
        self.assertTrue(out['ok'], out)
        return [e['evidence_id'] for e in out['result']['evidence']]

    def call(self, **args):
        args.setdefault('project_id', self.pid)
        return json.loads(self.handlers['rekindra_reconstruct'](args))

    def refused(self, **args):
        out = self.call(**args)
        self.assertFalse(out['ok'], out)
        self.assertEqual(out['error']['code'], 'invalid_input')
        return out['error']['message']

    def proposal(self, **extra):
        self.assertTrue(self.recover('photo.tga')['ok'])
        ids = self.evidence_for('notes.txt')
        base = {'title': 'The lake house', 'sections': [
            {'title': 'What was found', 'items': [
                {'type': 'image', 'asset_id': self.ids['photo.tga']},
                {'type': 'note', 'text': 'The photo likely belongs with the note.'},
                {'type': 'text', 'asset_id': self.ids['notes.txt'], 'evidence_ids': ids[:1]}]}]}
        base.update(extra)
        return base, ids

    def snapshot(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(self.source.iterdir())}

    # --- rotated partial image ----------------------------------------------------------

    def test_partial_frame_follows_the_applied_exif_rotation(self):
        from rekindra_core import reconstruct as module
        page = module._Page()
        proposal, _ = self.proposal()
        project = self.store.status(self.pid)
        tga = self.ids['photo.tga']
        assets = {a['asset_id']: a for a in project['assets']}
        images = module._image_artifacts(project)
        # A damaged landscape JPEG whose EXIF asked for a quarter turn: the recovered pixels are portrait.
        images[tga] = dict(images[tga], partial=True, decoded_fraction=0.5, exif_orientation=6,
                           original_width=400, original_height=300)
        gaps = {k: [] for k in ('skipped_at_inspect', 'not_recovered', 'intake', 'partial_images',
                                'unplaced_images', 'unplaced_text')}
        gaps['inventory_truncated'] = False
        module._render(page, project, 'T', [{'title': 'S', 'items': [{'type': 'image', 'asset_id': tga}]}], [],
                       gaps, assets, images, self.store._project(self.pid))
        self.assertIn('style="aspect-ratio:300/400"', ''.join(page.parts))
        # TIFF is turned by its reader during load, so its stored size is already the turned one.
        page = module._Page()
        images[tga] = dict(images[tga], source_format='tiff', original_width=300, original_height=400)
        module._render(page, project, 'T', [{'title': 'S', 'items': [{'type': 'image', 'asset_id': tga}]}], [],
                       gaps, assets, images, self.store._project(self.pid))
        self.assertIn('style="aspect-ratio:300/400"', ''.join(page.parts))

    def test_joiners_in_quoted_text_are_kept(self):
        text = 'می‌خواهم 1990 \U0001F468‍\U0001F469‍\U0001F467'
        (self.source / 'fa.txt').write_bytes(text.encode('utf-8'))
        self.reinspect()
        ids = self.evidence_for('fa.txt')
        out = self.call(title='Joiners', sections=[{'title': 'S', 'items': [
            {'type': 'text', 'asset_id': self.ids['fa.txt'], 'evidence_ids': ids[:1]}]}])
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['result']['replaced_characters'], 0)
        self.assertIn(text, Path(out['result']['path']).read_text(encoding='utf-8'))

    @unittest.skipUnless(importlib.util.find_spec('pypdf'), 'pypdf is not installed')
    def test_pdf_quotes_carry_their_page_number(self):
        from test_pdf_text import make_pdf
        (self.source / 'two.pdf').write_bytes(make_pdf(['First page text here.', 'Second page text here.']))
        self.reinspect()
        ids = self.evidence_for('two.pdf')
        out = self.call(title='PDF', sections=[{'title': 'S', 'items': [
            {'type': 'text', 'asset_id': self.ids['two.pdf'], 'evidence_ids': ids}]}])
        self.assertTrue(out['ok'], out)
        self.assertIn('page 2', Path(out['result']['path']).read_text(encoding='utf-8'))
        record = json.loads(Path(out['result']['provenance_path']).read_text(encoding='utf-8'))
        quotes = record['sections'][0]['items'][0]['quotes']
        self.assertEqual([q['page_number'] for q in quotes], [1, 2])

    # --- happy path, labels, provenance -------------------------------------------------

    def test_writes_labeled_offline_page_and_provenance(self):
        before = self.snapshot()
        proposal, ids = self.proposal()
        out = self.call(**proposal)
        self.assertTrue(out['ok'], out)
        r = out['result']
        page = Path(r['path']).read_text(encoding='utf-8')
        self.assertEqual(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest(), r['sha256'])
        self.assertEqual(r['placed'], {'images': 1, 'passages': 1, 'notes': 1, 'sections': 1, 'timeline': 0})
        # Recovered material in place and labeled recovered; proposed structure labeled inferred.
        self.assertIn('<span class="tag rec">recovered</span>pixels decoded from <code>photo.tga</code>', page)
        self.assertIn('src="data:image/png;base64,', page)
        self.assertRegex(page, r'<blockquote><pre>[^<]*green door[^<]*</pre><div class="meta">'
                               r'<span class="tag rec">recovered</span>quoted from <code>notes.txt</code>')
        self.assertIn('<h1><span class="tag inf">inferred</span>The lake house</h1>', page)
        self.assertIn('<h2><span class="tag inf">inferred</span>What was found</h2>', page)
        self.assertIn('<p class="note"><span class="tag inf">inferred</span>The photo likely belongs with the note.</p>', page)
        # Offline: no script, no external reference, restrictive policy.
        self.assertNotIn('<script', page.lower())
        self.assertNotRegex(page, r'(?i)(https?:)?//[a-z]')
        self.assertIn("default-src 'none'; img-src data:; style-src 'unsafe-inline'", page)
        # Gaps: the rejected JSON and the unread ZIP member are listed without being placed.
        gaps = r['gaps']
        self.assertIn('bad.json', json.dumps(gaps))
        self.assertIn('<code>bad.json</code>', page)
        self.assertIn('<code>old.zip</code>', page)
        self.assertNotIn('secret body never read', page)
        # Provenance file.
        record = json.loads(Path(r['provenance_path']).read_text(encoding='utf-8'))
        self.assertEqual(record['html']['sha256'], r['sha256'])
        self.assertEqual(record['reconstruction_id'], r['reconstruction_id'])
        self.assertEqual(record['title_content'], 'inferred')
        sources = {s['source_path']: s for s in record['sources']}
        self.assertEqual(sources['photo.tga']['sha256'], before['photo.tga'])
        self.assertEqual(sources['notes.txt']['sha256'], before['notes.txt'])
        image, note, text = record['sections'][0]['items']
        self.assertEqual((image['content'], image['source_sha256']), ('recovered', before['photo.tga']))
        self.assertEqual((note['content'], note['origin'], note['recovered']), ('inferred', 'agent', False))
        [quote] = text['quotes']
        self.assertEqual((quote['evidence_id'], quote['content']), (ids[0], 'recovered'))
        self.assertIn(quote['text'], NOTE.decode())
        self.assertNotIn(note['text'], json.dumps(text))
        self.assertEqual(record['gaps'].keys(), {'skipped_at_inspect', 'inventory_truncated', 'not_recovered',
                                                 'intake', 'partial_images', 'unplaced_images', 'unplaced_text'})
        self.assertIn('games or software', r['out_of_scope'])
        # Originals untouched.
        self.assertEqual(self.snapshot(), before)

    def test_same_call_gives_same_reconstruction(self):
        proposal, _ = self.proposal()
        first, second = self.call(**proposal)['result'], self.call(**proposal)['result']
        self.assertEqual(first['reconstruction_id'], second['reconstruction_id'])
        self.assertEqual(first['sha256'], second['sha256'])
        changed = dict(proposal, title='Another title')
        self.assertNotEqual(self.call(**changed)['result']['reconstruction_id'], first['reconstruction_id'])

    def test_unrecovered_files_are_tried_once_and_listed(self):
        ids = self.evidence_for('notes.txt')   # photo.tga and old.zip deliberately not recovered by the caller
        out = self.call(title='Notes only', sections=[{'title': 'Note', 'items': [
            {'type': 'text', 'asset_id': self.ids['notes.txt'], 'evidence_ids': ids[:1]}]}])
        self.assertTrue(out['ok'], out)
        gaps = out['result']['gaps']
        self.assertEqual([g['source_path'] for g in gaps['unplaced_images']['first']], ['photo.tga'])
        listed = gaps['intake']['first'] + gaps['not_recovered']['first']
        self.assertTrue(any(g['source_path'] == 'bad.json' for g in listed), gaps)

    def test_reconstruct_never_rebuilds_the_evidence_dossier(self):
        # Text, ZIP and PDF sources the caller did not recover are listed, not recovered here:
        # recovering one would rebuild evidence.json and could re-id the passages being cited.
        ids = self.evidence_for('notes.txt')
        dossier = self.store._project(self.pid) / 'artifacts' / 'evidence.json'
        before = dossier.read_bytes()
        out = self.call(title='Notes only', sections=[{'title': 'Note', 'items': [
            {'type': 'text', 'asset_id': self.ids['notes.txt'], 'evidence_ids': ids[:1]}]}])
        self.assertTrue(out['ok'], out)
        self.assertEqual(dossier.read_bytes(), before)
        missing = out['result']['gaps']['not_recovered']['first']
        self.assertIn('old.zip', [g['source_path'] for g in missing])
        self.assertIn('rekindra_recover', next(g['reason'] for g in missing if g['source_path'] == 'old.zip'))
        self.refused(title='T', sections=[{'title': 'S', 'items': [
            {'type': 'text', 'asset_id': self.ids['notes.txt'], 'evidence_ids': ['ev-' + '0' * 24]}]}])
        self.assertEqual(dossier.read_bytes(), before)

    def test_crlf_text_is_quoted_without_replacement_marks(self):
        (self.source / 'dos.txt').write_bytes(b'First line, 1991.\r\nSecond line.\r\n')
        self.reinspect()
        ids = self.evidence_for('dos.txt')
        out = self.call(title='DOS', sections=[{'title': 'S', 'items': [
            {'type': 'text', 'asset_id': self.ids['dos.txt'], 'evidence_ids': ids[:1]}]}])
        self.assertTrue(out['ok'], out)
        page = Path(out['result']['path']).read_text(encoding='utf-8')
        self.assertEqual(out['result']['replaced_characters'], 0)
        self.assertNotIn('�', page)
        self.assertNotIn('\r', page)
        self.assertIn('First line, 1991.\nSecond line.', page)

    def test_surrogates_are_refused_by_name(self):
        proposal, _ = self.proposal()
        self.assertIn('surrogate', self.refused(**dict(proposal, title='bad \ud800 title')))

    # --- validation ---------------------------------------------------------------------

    def test_refusals_name_the_fix_and_valid_values(self):
        proposal, ids = self.proposal()
        tga, notes, bad = self.ids['photo.tga'], self.ids['notes.txt'], self.ids['bad.json']
        section = lambda *items: [{'title': 'S', 'items': list(items)}]
        image = {'type': 'image', 'asset_id': tga}
        text = {'type': 'text', 'asset_id': notes, 'evidence_ids': ids[:1]}
        # A text asset placed as an image: says what to pass, lists recovered images.
        message = self.refused(title='T', sections=section({'type': 'image', 'asset_id': notes}))
        self.assertIn('type: "text"', message); self.assertIn(tga, message)
        # An image cited as text.
        message = self.refused(title='T', sections=section({'type': 'text', 'asset_id': tga, 'evidence_ids': ids[:1]}))
        self.assertIn('type: "image"', message)
        # Evidence that was not recovered from that asset: lists that asset's ids.
        message = self.refused(title='T', sections=section(dict(text, evidence_ids=['ev-' + '0' * 24])))
        self.assertIn('was not recovered from asset', message); self.assertIn(ids[0], message)
        # Unknown asset.
        message = self.refused(title='T', sections=section({'type': 'image', 'asset_id': 'f' * 32}))
        self.assertIn('not in this project', message); self.assertIn(tga, message)
        # Text nobody recovered: reconstruct does not recover it, it names the tool that does.
        rejected = section(image, {'type': 'text', 'asset_id': bad, 'evidence_ids': ['ev-' + '0' * 24]})
        self.assertIn('rekindra_recover', self.refused(title='T', sections=rejected))
        # Notes alone.
        message = self.refused(title='T', sections=section({'type': 'note', 'text': 'Only my words.'}))
        self.assertIn('at least one recovered', message); self.assertIn(tga, message)
        # Placed twice.
        self.assertIn('already placed', self.refused(title='T', sections=section(image, image)))
        self.assertIn('already placed', self.refused(title='T', sections=section(text, text)))
        # Shape errors.
        self.assertIn('image, text, note', self.refused(title='T', sections=section({'type': 'video'})))
        self.assertIn('exactly', self.refused(title='T', sections=section(dict(image, caption='x'))))
        self.assertIn('title', self.refused(sections=section(image)))
        self.assertIn('sections', self.refused(title='T', sections=[]))
        # Rejected by intake once recovery was tried (last: recovering it rebuilds the dossier).
        self.recover('bad.json')
        self.assertIn('gaps', self.refused(title='T', sections=rejected))
        self.assertIn('does not accept: style', self.refused(title='T', sections=section(image), style='dark'))
        self.assertIn('at most 400', self.refused(title='T', sections=section(image, {'type': 'note', 'text': 'x' * 401})))
        # Nothing was written by any refusal.
        self.assertEqual(list((self.store._project(self.pid) / 'artifacts').glob('reconstruction-*')), [])

    def test_timeline_dates_need_recovered_backing(self):
        proposal, ids = self.proposal()
        notes, tga = self.ids['notes.txt'], self.ids['photo.tga']
        entry = {'date': '1998', 'label': 'Summer at the lake house', 'asset_id': notes, 'evidence_id': ids[0]}
        out = self.call(**dict(proposal, timeline=[entry]))
        self.assertTrue(out['ok'], out)
        page = Path(out['result']['path']).read_text(encoding='utf-8')
        self.assertIn('<td>1998</td><td><span class="tag inf">inferred</span>Summer at the lake house</td>', page)
        self.assertIn('the year 1998 appears in a passage of <code>notes.txt</code>', page)
        record = json.loads(Path(out['result']['provenance_path']).read_text(encoding='utf-8'))
        self.assertEqual(record['timeline'][0]['label_content'], 'inferred')
        self.assertEqual(record['timeline'][0]['quote']['evidence_id'], ids[0])
        # A finer date than the passage states is marked as the agent's reading.
        out = self.call(**dict(proposal, timeline=[dict(entry, date='1998-07')]))
        self.assertIn('Month or day is the agent&#x27;s reading', Path(out['result']['path']).read_text(encoding='utf-8'))
        # A year the passage does not state.
        message = self.refused(**dict(proposal, timeline=[dict(entry, date='2005')]))
        self.assertIn('2005 does not appear', message)
        # An image with no recovered capture date.
        message = self.refused(**dict(proposal, timeline=[{'date': '1998', 'label': 'x', 'asset_id': tga}]))
        self.assertIn('no recovered capture date', message)
        # A text asset without evidence_id: lists its ids.
        message = self.refused(**dict(proposal, timeline=[{'date': '1998', 'label': 'x', 'asset_id': notes}]))
        self.assertIn(ids[0], message)
        self.assertIn('YYYY', self.refused(**dict(proposal, timeline=[dict(entry, date='1998-13')])))
        self.assertIn('YYYY', self.refused(**dict(proposal, timeline=[dict(entry, date='summer 98')])))

    # --- escaping -----------------------------------------------------------------------

    def test_untrusted_text_is_escaped_everywhere(self):
        (self.source / "a&b'.txt").write_text('Found 1987. ' + HOSTILE.replace('\x07', '') + '\n', encoding='utf-8')
        self.reinspect()
        self.assertTrue(self.recover('photo.tga')['ok'])
        ids = self.evidence_for("a&b'.txt")
        out = self.call(title=HOSTILE, sections=[{'title': HOSTILE, 'items': [
            {'type': 'image', 'asset_id': self.ids['photo.tga']},
            {'type': 'note', 'text': HOSTILE},
            {'type': 'text', 'asset_id': self.ids["a&b'.txt"], 'evidence_ids': ids[:1]}]}],
            timeline=[{'date': '1987', 'label': HOSTILE, 'asset_id': self.ids["a&b'.txt"], 'evidence_id': ids[0]}])
        self.assertTrue(out['ok'], out)
        page = Path(out['result']['path']).read_text(encoding='utf-8')
        self.assertNotIn('<script', page.lower())
        self.assertNotIn('<img src=x', page)
        self.assertNotIn('onerror=alert(2)>', page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt; &quot;&gt;&lt;img src=x onerror=alert(2)&gt;', page)
        self.assertIn('&amp;amp;', page)
        self.assertIn('a&amp;b&#x27;.txt', page)
        self.assertNotIn("a&b'.txt", page)
        for bad in '‮\x07':
            self.assertNotIn(bad, page)
        self.assertGreaterEqual(out['result']['replaced_characters'], 2)
        # Every tag in the page is one this module writes.
        tags = set(re.findall(r'<\s*/?\s*([a-zA-Z0-9]+)', page))
        self.assertLessEqual(tags, {'html', 'head', 'meta', 'title', 'style', 'body', 'main', 'h1', 'h2', 'p', 'div',
                                    'span', 'code', 'section', 'figure', 'img', 'figcaption', 'blockquote', 'pre',
                                    'table', 'tr', 'th', 'td', 'ul', 'li', 'br'})
        self.assertEqual(len(re.findall(r'<img ', page)), 1)

    # --- partial images -----------------------------------------------------------------

    def test_partial_image_shows_recovered_pixels_and_marks_the_missing_region(self):
        data = encoded(noise((80, 80)), 'PNG')
        (self.source / 'cut.png').write_bytes(data[:len(data) * 6 // 10])
        self.reinspect()
        recovered = self.recover('cut.png')
        self.assertTrue(recovered['ok'], recovered)
        out = self.call(title='Damaged', sections=[{'title': 'S', 'items': [
            {'type': 'image', 'asset_id': self.ids['cut.png']}]}])
        self.assertTrue(out['ok'], out)
        page = Path(out['result']['path']).read_text(encoding='utf-8')
        self.assertIn('<div class="frame" style="aspect-ratio:80/80">', page)
        self.assertIn('<span>missing: not recovered</span>', page)
        self.assertIn('not filled in', page)
        gaps = out['result']['gaps']['partial_images']
        self.assertEqual((gaps['count'], gaps['first'][0]['source_path']), (1, 'cut.png'))
        record = json.loads(Path(out['result']['provenance_path']).read_text(encoding='utf-8'))
        item = record['sections'][0]['items'][0]
        self.assertIs(item['partial'], True)
        self.assertTrue(0 < item['decoded_fraction'] < 1)
        # The embedded pixels are exactly the recovered PNG, nothing synthesized.
        artifact = self.store._project(self.pid) / 'artifacts' / (self.ids['cut.png'] + '.png')
        self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), item['image_sha256'])
        import base64
        embedded = re.search(r'src="data:image/png;base64,([A-Za-z0-9+/=]+)"', page)[1]
        self.assertEqual(base64.b64decode(embedded), artifact.read_bytes())

    # --- a world citing the reconstruction ----------------------------------------------

    def test_world_cites_reconstruction_and_revision_keeps_it(self):
        proposal, ids = self.proposal()
        r = self.call(**proposal)['result']
        tga = self.ids['photo.tga']
        scene = world(tga)
        made = json.loads(self.handlers['rekindra_create_world'](
            {'project_id': self.pid, 'asset_ids': [tga], 'scene': scene, 'reconstruction_id': r['reconstruction_id']}))
        self.assertTrue(made['ok'], made)
        plans = CompositionStore(self.store)
        cited = {'reconstruction_id': r['reconstruction_id'], 'html_sha256': r['sha256']}
        self.assertEqual(plans.load_plan(self.pid, made['result']['plan_id'])['model']['reconstruction'], cited)
        revised = json.loads(self.handlers['rekindra_revise_world'](
            {'project_id': self.pid, 'plan_id': made['result']['plan_id'], 'edits': [{'field': 'title', 'value': 'Kept'}]}))
        self.assertTrue(revised['ok'], revised)
        self.assertEqual(plans.load_plan(self.pid, revised['result']['plan_id'])['model']['reconstruction'], cited)
        # Without the field nothing is stored.
        plain = json.loads(self.handlers['rekindra_create_world']({'project_id': self.pid, 'asset_ids': [tga], 'scene': scene}))
        self.assertNotIn('reconstruction', plans.load_plan(self.pid, plain['result']['plan_id'])['model'])
        # Unknown, malformed and tampered reconstructions are refused.
        for value in ('0' * 32, 'nope', 7):
            out = json.loads(self.handlers['rekindra_create_world'](
                {'project_id': self.pid, 'asset_ids': [tga], 'scene': scene, 'reconstruction_id': value}))
            self.assertFalse(out['ok'], out)
            self.assertIn('rekindra_reconstruct', out['error']['message'])
        with open(r['path'], 'ab') as page:
            page.write(b'<!-- edited -->')
        out = json.loads(self.handlers['rekindra_create_world'](
            {'project_id': self.pid, 'asset_ids': [tga], 'scene': scene, 'reconstruction_id': r['reconstruction_id']}))
        self.assertFalse(out['ok'], out)
        self.assertIn('changed after it was written', out['error']['message'])


# The base class only lends its fixture; its own tests already run in test_recover_evidence.
for _name in dir(recover_tests.RecoverEvidenceTests):
    if _name.startswith('test_'):
        setattr(ReconstructTests, _name, None)
