"""Child process: read one PDF from stdin and print its page text as JSON lines.

Runs on its own so a hostile PDF is confined to this process: the parent kills it
at its deadline, and memory is capped where the OS enforces it (a Job Object on
Windows, RLIMIT_AS on Linux; macOS has only the deadline and a CPU limit). Never
imported by the plugin. Each line is flushed
as it is produced, so the pages read before a hang still reach the parent.

    python -I -S -B _pdf_worker.py <dir holding pypdf> <max pages> <max chars per page>
"""
import io
import json
import os
import re
import sys

_CONTROL = re.compile('[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f-\\x9f]')
_MEMORY_BYTES = 1024 * 1024 * 1024
_CPU_SECONDS = 60
_JOB_EXTENDED_LIMITS = 9
_JOB_LIMIT_PROCESS_MEMORY = 0x100


def _limit_windows_memory():
    """Put this process in a Job Object that fails allocations past the memory cap."""
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [('user_time', ctypes.c_int64), ('job_time', ctypes.c_int64), ('flags', wintypes.DWORD),
                    ('min_working_set', ctypes.c_size_t), ('max_working_set', ctypes.c_size_t),
                    ('processes', wintypes.DWORD), ('affinity', ctypes.c_size_t),
                    ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', ctypes.c_uint64 * 6), ('process_memory', ctypes.c_size_t),
                    ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t),
                    ('peak_job', ctypes.c_size_t)]

    kernel32 = ctypes.WinDLL('kernel32')
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return
    limits = Extended()
    limits.basic.flags = _JOB_LIMIT_PROCESS_MEMORY
    limits.process_memory = _MEMORY_BYTES
    if kernel32.SetInformationJobObject(job, _JOB_EXTENDED_LIMITS, ctypes.byref(limits), ctypes.sizeof(limits)):
        kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess())


def _limit_resources():
    """Hard process limits, applied before any untrusted byte is read."""
    if os.name == 'nt':
        try:
            _limit_windows_memory()
        except (ImportError, OSError, AttributeError):
            pass
        return
    try:
        import resource
    except ImportError:
        return
    for limit, value in ((resource.RLIMIT_AS, _MEMORY_BYTES), (resource.RLIMIT_CPU, _CPU_SECONDS)):
        try:
            resource.setrlimit(limit, (value, value))
        except (ValueError, OSError):
            pass


def _emit(record):
    sys.stdout.buffer.write(json.dumps(record, ensure_ascii=True).encode('ascii') + b'\n')
    sys.stdout.buffer.flush()


def _open(data):
    """Return (reader, encrypted) or None after reporting why the file cannot be read."""
    from pypdf import PdfReader
    from pypdf.errors import DependencyError, FileNotDecryptedError
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        encrypted = bool(reader.is_encrypted)
        # An empty user password is how "protected against editing" PDFs stay readable.
        if encrypted and not reader.decrypt(''):
            _emit({'kind': 'refused', 'code': 'encrypted'})
            return None
        return reader, encrypted
    except (FileNotDecryptedError, DependencyError):
        _emit({'kind': 'refused', 'code': 'encrypted'})
    except MemoryError:
        _emit({'kind': 'refused', 'code': 'memory_limit'})
    except Exception:  # pypdf raises many types on damaged input; all mean the same here
        _emit({'kind': 'refused', 'code': 'malformed'})
    return None


def main(argv):
    _limit_resources()
    sys.path.insert(0, argv[1])
    max_pages, max_chars = int(argv[2]), int(argv[3])
    data = sys.stdin.buffer.read()
    try:
        import pypdf  # noqa: F401
    except Exception:  # a missing or broken install says nothing about this file
        _emit({'kind': 'refused', 'code': 'reader_unavailable'})
        return 0
    opened = _open(data)
    if opened is None:
        return 0
    reader, encrypted = opened
    from pypdf.errors import FileNotDecryptedError
    try:
        pages = reader.pages
        count = len(pages)
    except FileNotDecryptedError:
        _emit({'kind': 'refused', 'code': 'encrypted'})
        return 0
    except MemoryError:
        _emit({'kind': 'refused', 'code': 'memory_limit'})
        return 0
    except Exception:
        _emit({'kind': 'refused', 'code': 'malformed'})
        return 0
    if count == 0:
        _emit({'kind': 'refused', 'code': 'malformed'})
        return 0
    _emit({'kind': 'start', 'page_count': count, 'encrypted': encrypted})
    for number in range(1, min(count, max_pages) + 1):
        try:
            text = _CONTROL.sub('', pages[number - 1].extract_text() or '')
        except Exception:
            _emit({'kind': 'page_failed', 'page': number})
            continue
        _emit({'kind': 'page', 'page': number, 'text': text[:max_chars], 'truncated': len(text) > max_chars})
    _emit({'kind': 'done'})
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
