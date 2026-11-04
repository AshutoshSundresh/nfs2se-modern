"""Make DDNFS.dll (the SDL2 render shim) fill the screen at native resolution.

nfs2sen.exe renders through DDNFS.dll, which by default forces a 640x480 display
mode (ChangeDisplaySettingsExA) and a 640x480 window (MoveWindow), then lets the
MONITOR upscale -> blurry, doesn't fill. We rewrite those four hardcoded 640/480
immediates to the target resolution so:
  * DEVMODE = native  -> ChangeDisplaySettings is a no-op (no ugly mode switch)
  * MoveWindow = native -> full-screen window; SDL upscales the 640x480 render
    to native itself (crisper than the monitor's stretch)
Pair with the DPI-aware compat flag so Windows doesn't add its own 200% blur.

    python mods/hi-res/patch_ddnfs.py apply
    python mods/hi-res/patch_ddnfs.py revert
    python mods/hi-res/patch_ddnfs.py status
"""
import struct, sys
from pathlib import Path

DLL = Path("Need For Speed II SE/DDNFS.dll")

WIDTH  = 2880
HEIGHT = 1800

# (va, orig, axis)  -- DDNFS.dll preferred base 0x689c0000
P = [
    (0x689c186b, 640, "W"),   # DEVMODE.dmPelsWidth
    (0x689c1876, 480, "H"),   # DEVMODE.dmPelsHeight
    (0x689c18d9, 640, "W"),   # MoveWindow nWidth
    (0x689c18d1, 480, "H"),   # MoveWindow nHeight
]
NEW = {"W": WIDTH, "H": HEIGHT}
ORIG = {"W": 640, "H": 480}


def _v2f(d, va):
    pe = struct.unpack_from("<I", d, 0x3c)[0]
    imgbase = struct.unpack_from("<I", d, pe + 0x34)[0]
    nsec = struct.unpack_from("<H", d, pe + 6)[0]
    secoff = pe + 24 + struct.unpack_from("<H", d, pe + 20)[0]
    for i in range(nsec):
        o = secoff + i * 40
        if d[o:o + 8].rstrip(b"\0") == b".text":
            tv = struct.unpack_from("<I", d, o + 12)[0]
            tr = struct.unpack_from("<I", d, o + 20)[0]
            return tr + (va - imgbase - tv)


def _set(val_for):
    d = bytearray(DLL.read_bytes())
    for va, orig, axis in P:
        struct.pack_into("<I", d, _v2f(d, va), val_for(axis, orig))
    DLL.write_bytes(d)


def apply():
    d = DLL.read_bytes()
    for va, orig, axis in P:
        cur = struct.unpack_from("<I", d, _v2f(d, va))[0]
        if cur != orig:
            raise SystemExit("refuse: 0x%X = %d (expected %d; revert first)" % (va, cur, orig))
    _set(lambda a, o: NEW[a])
    print("DDNFS window/mode -> %dx%d" % (WIDTH, HEIGHT))


def revert():
    _set(lambda a, o: ORIG[a])
    print("DDNFS window/mode -> 640x480 (stock)")


def status():
    d = DLL.read_bytes()
    w = struct.unpack_from("<I", d, _v2f(d, P[0][0]))[0]
    h = struct.unpack_from("<I", d, _v2f(d, P[1][0]))[0]
    print("DDNFS render window: %dx%d %s" % (w, h, "(stock)" if (w, h) == (640, 480) else "(patched)"))


if __name__ == "__main__":
    {"apply": apply, "revert": revert, "status": status}[sys.argv[1] if len(sys.argv) > 1 else "status"]()
