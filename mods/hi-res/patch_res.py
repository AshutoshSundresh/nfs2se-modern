"""Raise NFS2SE internal render resolution from 640x480.

Two setup functions default the render surface to 640x480x16 via immediate
`mov reg, 0x280` (640) / `mov reg, 0x1e0` (480). We rewrite those width/height
immediates. The engine takes an arbitrary requested WxH (validated against a
max) and already supports 1024x768 natively, so this is a safe first step.

NOTE: the 3D world renders at the new res, but 2D UI/HUD use fixed 640x480
coords -- expect UI placement issues until those are separately rescaled.

    python mods/hi-res/patch_res.py apply
    python mods/hi-res/patch_res.py revert
    python mods/hi-res/patch_res.py status
Edit WIDTH/HEIGHT below and re-run apply (revert first) to try other resolutions.
"""
import struct, sys
from pathlib import Path

EXE = Path("Need For Speed II SE/nfs2sen.exe")

WIDTH  = 1024      # try 1024/1280/1600 (keep 4:3 to avoid stretch: 1024x768,1280x960,1600x1200)
HEIGHT = 768

# (imm_va, original_value, which)  -- the render-res default immediates
P = [
    (0x47e6f3, 640, "W"),   # mov ecx, 0x280
    (0x47e6fc, 480, "H"),   # mov esi, 0x1e0
    (0x48838d, 640, "W"),   # mov ebp, 0x280
    (0x488392, 480, "H"),   # mov eax, 0x1e0
]
NEW = {"W": WIDTH, "H": HEIGHT}
ORIG = {"W": 640, "H": 480}


def off(va):
    return va - 0x400C00


def _write(d, val_for):
    for va, orig, which in P:
        struct.pack_into("<I", d, off(va), val_for(which, orig))


def apply():
    d = bytearray(EXE.read_bytes())
    for va, orig, which in P:
        cur = struct.unpack_from("<I", d, off(va))[0]
        if cur != orig:
            raise SystemExit("refuse: 0x%X = %d, expected %d (revert first)" % (va, cur, orig))
    _write(d, lambda w, o: NEW[w])
    EXE.write_bytes(d)
    print("render resolution -> %dx%d" % (WIDTH, HEIGHT))


def revert():
    d = bytearray(EXE.read_bytes())
    _write(d, lambda w, o: ORIG[w])
    EXE.write_bytes(d)
    print("render resolution -> 640x480 (stock)")


def status():
    d = EXE.read_bytes()
    w = struct.unpack_from("<I", d, off(P[0][0]))[0]
    h = struct.unpack_from("<I", d, off(P[1][0]))[0]
    print("current render resolution default: %dx%d %s" % (w, h, "(stock)" if (w, h) == (640, 480) else "(patched)"))


if __name__ == "__main__":
    {"apply": apply, "revert": revert, "status": status}[sys.argv[1] if len(sys.argv) > 1 else "status"]()
