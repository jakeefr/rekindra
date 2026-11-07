"""Forge tiny ZIP byte strings, including metadata zipfile refuses to write.

Sizes are written as plain claims. Nothing here compresses anything, so an
"extreme expansion" fixture is a few bytes claiming to expand, not a real bomb.
"""
import struct
import zlib

EOCD = b'PK\x05\x06'
CENTRAL = b'PK\x01\x02'
LOCAL = b'PK\x03\x04'
ZIP64_LOCATOR = b'PK\x06\x07'
MADE_BY_UNIX = (3 << 8) | 20
MADE_BY_DOS = 20
UTF8_NAME = 0x800


def entry(name, payload=b'', **overrides):
    raw = name if isinstance(name, bytes) else name.encode()
    fields = dict(name=raw, payload=payload, method=0, flags=UTF8_NAME, made_by=MADE_BY_UNIX, external=0,
                  compressed=len(payload), uncompressed=len(payload), crc=zlib.crc32(payload), extra=b'',
                  comment=b'', disk=0, local_name=raw, local_signature=LOCAL, offset=None)
    fields.update(overrides)
    return fields


def build(entries, comment=b'', declared=None, cd_size=None, cd_offset=None, disk=0, cd_disk=0, on_disk=None,
          prefix=b'', trailer=b'', zip64_locator=False, cd_tail=b''):
    body = bytearray(prefix)
    central = bytearray()
    for item in entries:
        offset = len(body) if item['offset'] is None else item['offset']
        body += struct.pack('<4sHHHHHIIIHH', item['local_signature'], 20, item['flags'], item['method'], 0, 33,
                            item['crc'], item['compressed'], item['uncompressed'], len(item['local_name']), 0)
        body += item['local_name'] + item['payload']
        central += struct.pack('<4sHHHHHHIIIHHHHHII', CENTRAL, item['made_by'], 20, item['flags'], item['method'],
                               0, 33, item['crc'], item['compressed'], item['uncompressed'], len(item['name']),
                               len(item['extra']), len(item['comment']), item['disk'], 0, item['external'], offset)
        central += item['name'] + item['extra'] + item['comment']
    central += cd_tail
    start = len(body)
    count = len(entries) if declared is None else declared
    tail = bytes(body) + bytes(central)
    if zip64_locator:
        tail += struct.pack('<4sIQI', ZIP64_LOCATOR, 0, 0, 1)
    tail += struct.pack('<4sHHHHIIH', EOCD, disk, cd_disk, count if on_disk is None else on_disk, count,
                        len(central) if cd_size is None else cd_size, start if cd_offset is None else cd_offset,
                        len(comment))
    return tail + comment + trailer
