"""Give Class D a real "class D" text by overwriting record 124 ("speedometer").

Class A/B/C are text ids 0x7C/0x7D/0x7E (records 121/122/123). Class D uses the
next id 0x7F -> record 124 ("speedometer"). We overwrite it in place with
"class D". The game actually loads TEXT.MET (English + metric), so we patch that
AND TEXT.ENG for safety. Same file size; side effect: options "speedometer"
label reads "class D".
"""
import struct, shutil
from pathlib import Path

TARGET_REC = 124            # text id 0x7F
NEW = b"class D\x00"
FILES = ["TEXT.MET", "TEXT.ENG"]
DIR = Path("Need For Speed II SE/FEDATA/PC/TEXT")


def patch_bytes(d):
    off = struct.unpack_from("<I", d, TARGET_REC * 12 + 8)[0]
    cur = bytes(d[off:d.find(b"\x00", off)])
    if cur == b"class D":
        return None
    assert len(cur) >= len(NEW) - 1, "record %d too short (%r)" % (TARGET_REC, cur)
    out = bytearray(d)
    out[off:off + len(NEW)] = NEW
    o = struct.unpack_from("<I", out, TARGET_REC * 12 + 8)[0]
    assert out[o:o + 7] == b"class D"
    return bytes(out)


def apply():
    for name in FILES:
        p = DIR / name
        if not p.is_file():
            continue
        bak = p.with_suffix(p.suffix + ".class-d.bak")
        d = bytearray(p.read_bytes())
        out = patch_bytes(d)
        if out is None:
            print("%s: already 'class D'" % name); continue
        if not bak.exists():
            shutil.copy2(p, bak)
        p.write_bytes(out)
        print("%s: record %d = 'class D'" % (name, TARGET_REC))


def revert():
    for name in FILES:
        p = DIR / name
        bak = p.with_suffix(p.suffix + ".class-d.bak")
        if bak.exists():
            shutil.copy2(bak, p); print("%s: reverted" % name)


def status():
    for name in FILES:
        p = DIR / name
        if not p.is_file():
            continue
        d = p.read_bytes()
        o = struct.unpack_from("<I", d, TARGET_REC * 12 + 8)[0]
        print("%s: record %d = %r" % (name, TARGET_REC, bytes(d[o:d.find(b'\x00', o)])))


if __name__ == "__main__":
    import sys
    {"apply": apply, "revert": revert}.get(sys.argv[1] if len(sys.argv) > 1 else "status", status)()
