#!/usr/bin/env python3
"""EA FSH/QFS (SHPI + RefPack) codec for NFS2SE textures -- decode side first.

QFS = RefPack-compressed SHPI.  SHPI = EA bitmap bundle (dir of tagged entries).
This module can: refpack_decompress(), parse_shpi(), and a CLI to inspect a file
and export its bitmaps to PNG so we can see what we're working with (and confirm
the Glide 256x256 reality for car/track textures).

    python fsh.py inspect <file.qfs|.fsh>
    python fsh.py extract <file.qfs|.fsh> <outdir>
"""
from __future__ import annotations
import struct, sys
from pathlib import Path

# ---------------- RefPack (QFS) decompression ----------------
def refpack_decompress(d: bytes) -> bytes:
    i = 0
    flags = d[0] | (d[1] << 8)
    # signature 0x10FB (little end shows 10 fb). bit layout: d[0]=0x10, d[1]=0xFB
    i = 2
    if d[0] & 0x01:            # large-file bit -> 4-byte sizes
        i += 4
    outlen = (d[i] << 16) | (d[i + 1] << 8) | d[i + 2]
    i += 3
    out = bytearray()
    n = len(d)
    while i < n:
        c = d[i]; i += 1
        if c < 0x80:                      # 0xxxxxxx : 2-byte form
            a = d[i]; i += 1
            nproc = c & 0x03
            out += d[i:i + nproc]; i += nproc
            cnt = ((c & 0x1C) >> 2) + 3
            ref = ((c & 0x60) << 3) + a + 1
            for _ in range(cnt):
                out.append(out[-ref])
        elif c < 0xC0:                    # 10xxxxxx : 3-byte form
            a = d[i]; b = d[i + 1]; i += 2
            nproc = (a >> 6) & 0x03
            out += d[i:i + nproc]; i += nproc
            cnt = (c & 0x3F) + 4
            ref = ((a & 0x3F) << 8) + b + 1
            for _ in range(cnt):
                out.append(out[-ref])
        elif c < 0xE0:                    # 110xxxxx : 4-byte form
            a = d[i]; b = d[i + 1]; e = d[i + 2]; i += 3
            nproc = c & 0x03
            out += d[i:i + nproc]; i += nproc
            cnt = ((c & 0x0C) << 6) + e + 5
            ref = ((c & 0x10) << 12) + (a << 8) + b + 1
            for _ in range(cnt):
                out.append(out[-ref])
        elif c < 0xFC:                    # 111xxxxx : literal run
            cnt = ((c & 0x1F) << 2) + 4
            out += d[i:i + cnt]; i += cnt
        else:                             # 1111110x..: final literal 0-3
            cnt = c & 0x03
            out += d[i:i + cnt]; i += cnt
            break
    return bytes(out[:outlen])


def is_qfs(d: bytes) -> bool:
    return len(d) > 5 and d[0] in (0x10, 0x11) and d[1] == 0xFB


def load_shpi(path: Path) -> bytes:
    d = path.read_bytes()
    if is_qfs(d):
        d = refpack_decompress(d)
    if d[:4] != b"SHPI":
        raise ValueError("not SHPI (got %r)" % d[:4])
    return d


# ---------------- SHPI parse ----------------
BMP_CODES = {0x7b: "8bit-idx", 0x7d: "32bit", 0x7f: "24bit",
             0x78: "16bit-0565", 0x7e: "16bit-4444", 0x7a: "16bit-1555",
             0x6d: "16bit-alt"}
PAL_CODES = {0x22, 0x24, 0x29, 0x2a, 0x2b, 0x2d, 0x42}

def parse_shpi(d: bytes):
    size, n = struct.unpack_from("<II", d, 4)
    dirid = d[12:16]
    entries = []
    off = 16
    for _ in range(n):
        tag = d[off:off + 4]; (eoff,) = struct.unpack_from("<I", d, off + 4); off += 8
        entries.append([tag.decode("latin1"), eoff])
    # attach parsed header to each
    out = []
    for idx, (tag, eoff) in enumerate(entries):
        code = d[eoff] & 0x7f
        attach = d[eoff] & 0x80
        blk = d[eoff + 1] | (d[eoff + 2] << 8) | (d[eoff + 3] << 16)
        w, h = struct.unpack_from("<HH", d, eoff + 4)
        out.append({"tag": tag, "off": eoff, "code": code, "attach": bool(attach),
                    "kind": BMP_CODES.get(code, "pal/other" if code in PAL_CODES else "0x%02x" % code),
                    "w": w, "h": h, "blk": blk})
    return {"size": size, "n": n, "dirid": dirid.decode("latin1"), "entries": out}


def _to_rgba(d, e, pal=None):
    import numpy as np
    w, h, code, off = e["w"], e["h"], e["code"], e["off"] + 16
    px = w * h
    if code == 0x7d:  # 32-bit BGRA
        a = np.frombuffer(d, np.uint8, px * 4, off).reshape(h, w, 4)
        return a[..., [2, 1, 0, 3]].copy()
    if code == 0x7f:  # 24-bit BGR
        a = np.frombuffer(d, np.uint8, px * 3, off).reshape(h, w, 3)
        out = np.dstack([a[..., 2], a[..., 1], a[..., 0], np.full((h, w), 255, np.uint8)])
        return out
    if code in (0x78,):  # 0565
        a = np.frombuffer(d, np.uint16, px, off).reshape(h, w).astype(np.uint32)
        r = ((a >> 11) & 0x1f) * 255 // 31; g = ((a >> 5) & 0x3f) * 255 // 63; b = (a & 0x1f) * 255 // 31
        return np.dstack([r, g, b, np.full((h, w), 255, np.uint32)]).astype(np.uint8)
    if code == 0x7e:  # 4444 ARGB
        a = np.frombuffer(d, np.uint16, px, off).reshape(h, w).astype(np.uint32)
        al = ((a >> 12) & 0xf) * 17; r = ((a >> 8) & 0xf) * 17; g = ((a >> 4) & 0xf) * 17; b = (a & 0xf) * 17
        return np.dstack([r, g, b, al]).astype(np.uint8)
    if code == 0x7a:  # 1555 ARGB
        a = np.frombuffer(d, np.uint16, px, off).reshape(h, w).astype(np.uint32)
        al = ((a >> 15) & 1) * 255; r = ((a >> 10) & 0x1f) * 255 // 31; g = ((a >> 5) & 0x1f) * 255 // 31; b = (a & 0x1f) * 255 // 31
        return np.dstack([r, g, b, al]).astype(np.uint8)
    if code == 0x7b and pal is not None:  # 8-bit indexed
        idx = np.frombuffer(d, np.uint8, px, off).reshape(h, w)
        return pal[idx]
    return None


def _palette(d, e):
    import numpy as np
    off = e["off"] + 16
    code = e["code"]
    ncol = e["w"] if e["w"] else 256
    if code in (0x2a, 0x2d):      # 32-bit entries BGRA
        a = np.frombuffer(d, np.uint8, ncol * 4, off).reshape(ncol, 4)
        return a[:, [2, 1, 0, 3]].copy()
    if code == 0x22:              # 24-bit
        a = np.frombuffer(d, np.uint8, ncol * 3, off).reshape(ncol, 3)
        return np.column_stack([a[:, 2], a[:, 1], a[:, 0], np.full(ncol, 255, np.uint8)])
    if code in (0x24, 0x29):      # 16-bit entries
        a = np.frombuffer(d, np.uint16, ncol, off).astype(np.uint32)
        r = ((a >> 10) & 0x1f) * 255 // 31; g = ((a >> 5) & 0x1f) * 255 // 31; b = (a & 0x1f) * 255 // 31
        return np.column_stack([r, g, b, np.full(ncol, 255, np.uint32)]).astype(np.uint8)
    return None


def inspect(path: Path):
    d = load_shpi(path)
    s = parse_shpi(d)
    print("%s  -> SHPI dir=%s entries=%d uncompressed=%d bytes" % (path.name, s["dirid"], s["n"], len(d)))
    mx = 0
    for e in s["entries"]:
        print("  %-5s %-10s %4dx%-4d  blk=%d" % (e["tag"], e["kind"], e["w"], e["h"], e["blk"]))
        if e["code"] in BMP_CODES:
            mx = max(mx, e["w"], e["h"])
    print("  -> max bitmap dimension: %d  (Glide hard cap = 256)" % mx)


def extract(path: Path, outdir: Path):
    import numpy as np
    from PIL import Image
    d = load_shpi(path); s = parse_shpi(d)
    outdir.mkdir(parents=True, exist_ok=True)
    pal = None
    for e in s["entries"]:
        if e["code"] in PAL_CODES:
            pal = _palette(d, e)
    saved = 0
    for e in s["entries"]:
        if e["code"] not in BMP_CODES or e["w"] == 0 or e["h"] == 0:
            continue
        rgba = _to_rgba(d, e, pal)
        if rgba is None:
            print("  skip %s (%s, no decoder)" % (e["tag"], e["kind"])); continue
        Image.fromarray(rgba, "RGBA").save(outdir / ("%s_%s.png" % (path.stem, e["tag"])))
        saved += 1
    print("extracted %d bitmap(s) from %s -> %s" % (saved, path.name, outdir))


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 1
    act, f = sys.argv[1], Path(sys.argv[2])
    if act == "inspect":
        inspect(f)
    elif act == "extract":
        extract(f, Path(sys.argv[3]) if len(sys.argv) > 3 else Path("tex_out"))
    else:
        print("unknown action"); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
