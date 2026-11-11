"""Local rendered-frame review using an installed browser, no creative engine."""
import base64
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from .compositions import CompositionStore
from .export_gate import preview_gate
from .image_recovery import measure_review_frames
from .intent_check import intent_check, photo_material_candidates
from .image_recovery import clean_palette
from .palette_drift import measure_drift
from .projects import ProjectError, _atomic, _no_links
from .report_checks import focal_framing, haze_report, object_motion_report, source_mist
from .scenes import SceneError

_PREVIEW_LOCK = threading.Lock()
MAX_DOM_BYTES = 40_000_000
MAX_PNG_BYTES = 8_000_000
MAX_FRAME_BYTES = 2_000_000
FRAME_SIZE = (640, 360)
# A preview that cannot run is the user's to fix. Working around it produced unreviewed exports.
STOP_MARK = 'Stop and tell the user'
_STOP = (' ' + STOP_MARK + '. Do not render, measure or record a preview by any other route, and do not edit '
         'skill or plugin files.')


def find_browser():
    override = os.environ.get('REKINDRA_BROWSER')
    if override:
        path = Path(override)
        if not path.is_absolute() or not path.is_file():
            raise SceneError('REKINDRA_BROWSER must name an absolute installed browser executable.' + _STOP)
        return path
    candidates = []
    if sys.platform == 'win32':
        for base in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
            if os.environ.get(base):
                for relative in ('Google/Chrome/Application/chrome.exe', 'Microsoft/Edge/Application/msedge.exe'):
                    candidates.append(Path(os.environ[base]) / relative)
    elif sys.platform == 'darwin':
        candidates = [Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
                      Path('/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'),
                      Path('/Applications/Chromium.app/Contents/MacOS/Chromium')]
    for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'microsoft-edge'):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise SceneError('Local preview needs installed Chrome, Chromium or Edge, and none was found. The user can install one or set '
                     'REKINDRA_BROWSER to its executable path. No browser was downloaded.' + _STOP)


class _ReviewResult(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.active = False
        self.parts = []
        self.count = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and attrs.get('id') == 'rekindra-review-result' and attrs.get('type') == 'application/json':
            self.active = True
            self.count += 1

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False


def _elevated():
    if sys.platform != 'win32':
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _no_output_error():
    if _elevated():
        cause = ('The browser returned nothing because Hermes is running as Administrator: Chrome and Edge restart '
                 'themselves without administrator rights and their output is lost. Fix: close this session, open a '
                 'normal (not "Run as administrator") PowerShell, start Hermes there and run rekindra_preview again.')
    else:
        cause = ('The browser exited without returning the preview. Fix: check that Chrome or Edge opens normally '
                 'for this user and that security software is not blocking it in the Rekindra project folder, then '
                 'run rekindra_preview again.')
    return SceneError(cause + _STOP)


def _frame_images(result):
    """The six frames as separate small PNGs, or [] when the page did not supply usable ones."""
    frames = result.get('frames')
    if not isinstance(frames, list) or len(frames) != 6:
        return []
    decoded = []
    for encoded in frames:
        if not isinstance(encoded, str) or len(encoded) > MAX_FRAME_BYTES*4//3+4:
            return []
        try:
            png = base64.b64decode(encoded, validate=True)
        except ValueError:
            return []
        if (len(png) > MAX_FRAME_BYTES or len(png) < 33 or png[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
                or struct.unpack('>II', png[16:24]) != FRAME_SIZE):
            return []
        decoded.append(png)
    return decoded


def _decode_result(document, duration):
    return _decode_review(document, duration)[:2]


def _white_off_emitter(result):
    """The page's per-frame near-white share outside glow surfaces, or None (no glow surfaces, or malformed)."""
    shares = result.get('whiteOffEmitter') if isinstance(result, dict) else None
    if (not isinstance(shares, list) or len(shares) != 6
            or any(type(v) not in (int, float) or not 0 <= v <= 100 for v in shares)):
        return None
    return shares
def _source_mist(store, project_id, plan):
    """How misty the plan's source images read, from their measured palettes; None without palettes."""
    # Only palettes already measured: this reading must never decode a source again.
    try:
        artifacts = store.status(project_id)['artifacts']
    except (ProjectError, OSError, KeyError, TypeError):
        return None
    sources = set(plan.get('source_ids') or [])
    palettes = [clean_palette(item.get('palette')) for item in artifacts if isinstance(item, dict)
                and item.get('kind') == 'recovered' and item.get('asset_id') in sources and item.get('palette')]
    return source_mist([p for p in palettes if p])


def _decode_review(document, duration):
    return _decode_review_full(document, duration)[:3]


def _object_motion(result):
    """The frozen-camera change the page measured, or None when it did not (older page, no world)."""
    value = result.get('objectMotion')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 255:
        return None
    return float(value)


def _decode_review_full(document, duration):
    parser = _ReviewResult()
    parser.feed(document)
    if parser.count != 1:
        if not document.strip():
            raise _no_output_error()
        raise SceneError('Browser did not finish the scene preview. Check browser graphics support and try again.')
    try:
        result = json.loads(''.join(parser.parts))
        if result.get('ok') is not True:
            raise SceneError('Scene preview failed. Check source integrity, graphics support and scene geometry.')
        result = result['result']
        expected = [(i+.5)*duration/6 for i in range(6)]
        if result['kind'] != 'rendered-frame-review' or result['times'] != expected:
            raise ValueError('Invalid frame times')
        encoded = result['png']
        if not isinstance(encoded, str) or len(encoded) > MAX_PNG_BYTES*4//3+4:
            raise ValueError('Oversized preview')
        png = base64.b64decode(encoded, validate=True)
        if len(png) > MAX_PNG_BYTES or len(png) < 33 or png[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR':
            raise ValueError('Invalid PNG')
        if struct.unpack('>II', png[16:24]) != (1280, 1128):
            raise ValueError('Invalid preview dimensions')
        return png, expected, _frame_images(result), _white_off_emitter(result), _object_motion(result)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise SceneError('Browser returned an invalid scene preview') from exc


def _stop_process(process):
    if sys.platform == 'win32':
        # The process belongs to this invocation and has its own profile.
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=10, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=10)


def preview_scene(store, project_id, plan_id, review_camera=None, draft=False):
    if not _PREVIEW_LOCK.acquire(blocking=False):
        raise SceneError('Another local scene preview is running. Retry after it finishes.')
    working = None
    project = None
    try:
        compositions = CompositionStore(store)
        plan = compositions.load_plan(project_id, plan_id)
        browser = find_browser()
        # Never execute an existing potentially modified HTML file: regenerate it
        # from validated plan/source data and the bundled renderer immediately.
        artifact = compositions.build(project_id, plan_id, review_camera=review_camera, draft=draft)
        project = store._project(project_id).resolve()
        working = Path(tempfile.mkdtemp(prefix='preview-work-', dir=project)).resolve()
        _no_links(working)
        profile = working / 'profile'
        temp = working / 'temp'
        temp.mkdir()
        source_html = Path(artifact['path'])
        _no_links(source_html)
        html = source_html.read_bytes()
        if hashlib.sha256(html).hexdigest() != artifact['sha256']:
            raise SceneError('Scene changed while preparing its preview. Retry with the saved plan.')
        snapshot = working / 'scene.html'
        _atomic(snapshot, html)
        env = os.environ.copy()
        env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp),
                   XDG_CACHE_HOME=str(working/'cache'), XDG_DATA_HOME=str(working/'data'), XDG_CONFIG_HOME=str(working/'config'))
        command = [str(browser), '--headless', '--no-first-run', '--no-default-browser-check',
                   '--disable-background-networking', '--disable-component-update', '--disable-sync',
                   '--disable-default-apps', '--disable-extensions', '--disable-crash-reporter',
                   '--disable-features=MediaRouter,OptimizationHints',
                   # Started elevated, the browser relaunches itself unelevated and its output never arrives.
                   '--do-not-de-elevate',
                   f'--user-data-dir={profile}', f'--disk-cache-dir={working / "cache"}',
                   f'--crash-dumps-dir={working / "crashes"}', '--window-size=1280,1128',
                   '--virtual-time-budget=10000', '--dump-dom',
                   snapshot.as_uri()+'?rekindra_review=1']
        options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == 'win32' else {'start_new_session': True}
        output = working / 'dom.txt'
        with output.open('wb') as stream:
            process = subprocess.Popen(command, cwd=working, env=env, stdout=stream, stderr=subprocess.DEVNULL, **options)
            try:
                deadline = time.monotonic()+45
                while process.poll() is None:
                    if output.stat().st_size > MAX_DOM_BYTES:
                        raise SceneError('Browser preview output exceeded its size limit')
                    remaining = deadline-time.monotonic()
                    if remaining <= 0:
                        raise SceneError('Scene preview exceeded 45 seconds. Simplify the scene or check browser graphics support.')
                    try:
                        process.wait(timeout=min(.25, remaining))
                    except subprocess.TimeoutExpired:
                        pass
                code = process.returncode
            finally:
                # Covers interruption/cancellation as well as budget failure.
                if process.poll() is None:
                    _stop_process(process)
        if code != 0:
            raise SceneError('The local browser could not render this scene. Check browser installation and graphics support.' + _STOP)
        if output.stat().st_size > MAX_DOM_BYTES:
            raise SceneError('Browser preview output exceeded its size limit')
        png, times, frame_pngs, off_emitter, object_motion = _decode_review_full(output.read_text(encoding='utf-8', errors='replace'), plan['scene']['duration'])
        review_id = uuid.uuid4().hex
        target = project / 'artifacts' / f'{plan_id}-review-{review_id}.png'
        _no_links(target)
        _atomic(target, png)
        frames = []
        for index, (frame, at) in enumerate(zip(frame_pngs, times), 1):
            frame_path = project / 'artifacts' / f'{plan_id}-review-{review_id}-frame-{index}.png'
            _no_links(frame_path)
            _atomic(frame_path, frame)
            frames.append({'path': str(frame_path), 'time_seconds': at})
        drift = measure_drift(store, project_id, plan, png, review_camera)
        # Only a world's presentation preview is gated; nothing else uses the measurement.
        gated = review_camera is None and plan['scene']['schema_version'] == 2
        frame_stats = measure_review_frames(png) if gated else None
        if frame_stats is not None and off_emitter is not None:
            # Near-white the page measured with glow surfaces masked out: the blown-out check gates on this.
            frame_stats = dict(frame_stats, white_off_emitter=off_emitter)
        next_step = ('Inspect this PNG with native vision under the user image-sharing consent, once. Put it beside the '
                     'source images themselves, not only the palette numbers: review source faithfulness, composition, '
                     'lighting, silhouettes and spatial conflicts; revise observed defects. These are rendered scene '
                     'samples, not decoded video or proof of collision-free motion.')
        if frames:
            next_step += (' If viewing the sheet times out, do not retry it: view one or two of the 640x360 images in '
                          'frames instead, and if those time out too, decide from palette_drift and export_gate.')
        if drift['status'] == 'drift':
            flags = ' '.join(row['flag'] + '.' for row in drift['regions'] if row['over_threshold'])
            next_step = f'Rendered colors drifted from the source: revise before exporting. {flags} {next_step}'
        mist = _source_mist(store, project_id, plan) if gated else None
        gate = preview_gate(store, project_id, plan, drift, review_camera, frame_stats,
                            {'object_motion': object_motion if gated else None, 'source_mist': mist})
        defects = gate.pop('defects', None) if gate is not None else None
        cleared = gate.pop('cleared', None) if gate is not None else None
        framing = focal_framing(plan['scene']) if gated else None
        motion = object_motion_report(object_motion) if gated else None
        haze = haze_report(plan['scene'], mist) if gated else None
        if motion is not None:
            next_step += f" object_motion: {motion['statement']}."
        if defects:
            carried = [d['id'] for d in defects if d['carried']]
            next_step += (' defects lists what this preview flagged. When you revise, pass addresses [{id, how}] for '
                          'each one you fix; any you leave out are reported as unaddressed and carried forward.')
            if carried:
                next_step += f" Still open from the previous preview: {', '.join(carried)}."
        if cleared:
            next_step += (' cleared_defects lists what the previous preview flagged and this one no longer measures; '
                          'those count as addressed whether or not the revise declared them.')
        if gate is not None:
            if gate['warnings']:
                next_step += ' rekindra_export will refuse this plan until every item in export_gate.warnings is revised away or acknowledged with a reason.'
            next_step += ' When satisfied, call rekindra_export with this plan_id; only its HTML can save video.'
        intent = intent_check(plan) if plan['scene'].get('schema_version') == 2 else []
        if intent:
            next_step += ' intent_check lists what the scene leaves off or renders dark against your own notes; follow each hint and preview again.'
        photo = photo_material_candidates(plan) if plan['scene'].get('schema_version') == 2 else None
        if photo:
            next_step += (' photo_materials flags a photo used as the subject: construct the subject from geometry '
                          'instead, then preview again.' if photo['status'] == 'subject_photo' else
                          ' photo_materials names recovered images that texture nothing and the surfaces each could '
                          'texture (ground, bark, leaves, stone, fabric). Photos are texture only; subjects are built '
                          'from geometry.')
        result = {'kind': 'rendered-frame-review', 'project_id': project_id, 'plan_id': plan_id,
                'inspection_only': artifact['inspection_only'], 'review_camera': review_camera,
                'plan_path': str(project / 'plans' / f'{plan_id}.json'),
                'path': str(target), 'format': 'png', 'times_seconds': times,
                'width': 1280, 'height': 1128, 'sha256': hashlib.sha256(png).hexdigest(), 'frames': frames,
                'html_sha256': artifact['sha256'], 'palette_drift': drift, 'export_gate': gate, 'next_step': next_step}
        if motion is not None:
            result['object_motion'] = motion
        if haze is not None:
            result['haze'] = haze
        if framing is not None:
            result['focal_framing'] = framing
        if defects:
            result['defects'] = defects
        if cleared:
            result['cleared_defects'] = cleared
        if intent:
            result['intent_check'] = intent
        if photo:
            result['photo_materials'] = photo
        return result
    finally:
        try:
            if working is not None and project is not None:
                # Never recursively clean a computed path without containment checks.
                _no_links(working)
                resolved = working.resolve()
                if resolved.is_relative_to(project) and resolved.name.startswith('preview-work-'):
                    shutil.rmtree(resolved, ignore_errors=True)
        finally:
            _PREVIEW_LOCK.release()
