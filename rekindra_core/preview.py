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
from .projects import _atomic, _no_links
from .scenes import SceneError

_PREVIEW_LOCK = threading.Lock()
MAX_DOM_BYTES = 40_000_000
MAX_PNG_BYTES = 8_000_000


def find_browser():
    override = os.environ.get('REKINDRA_BROWSER')
    if override:
        path = Path(override)
        if not path.is_absolute() or not path.is_file():
            raise SceneError('REKINDRA_BROWSER must name an absolute installed browser executable')
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
    raise SceneError('Local preview needs installed Chrome, Chromium or Edge. Install one or set REKINDRA_BROWSER to its executable path. No browser was downloaded.')


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


def _decode_result(document, duration):
    parser = _ReviewResult()
    parser.feed(document)
    if parser.count != 1:
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
        return png, expected
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


def preview_scene(store, project_id, plan_id):
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
        artifact = compositions.build(project_id, plan_id)
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
            raise SceneError('The local browser could not render this scene. Check browser installation and graphics support.')
        if output.stat().st_size > MAX_DOM_BYTES:
            raise SceneError('Browser preview output exceeded its size limit')
        png, times = _decode_result(output.read_text(encoding='utf-8', errors='replace'), plan['scene']['duration'])
        review_id = uuid.uuid4().hex
        target = project / 'artifacts' / f'{plan_id}-review-{review_id}.png'
        _no_links(target)
        _atomic(target, png)
        return {'kind': 'rendered-frame-review', 'project_id': project_id, 'plan_id': plan_id,
                'path': str(target), 'format': 'png', 'times_seconds': times,
                'width': 1280, 'height': 1128, 'sha256': hashlib.sha256(png).hexdigest(),
                'html_sha256': artifact['sha256'],
                'next_step': 'Inspect this PNG with native vision under the user image-sharing consent. Review source faithfulness, composition, lighting, silhouettes and spatial conflicts; revise observed defects. These are rendered scene samples, not decoded video or proof of collision-free motion.'}
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
