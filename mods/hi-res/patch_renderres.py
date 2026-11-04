"""Raise the internal RENDER resolution in DDNFS.dll to RENDER_W x RENDER_H.

DDNFS bakes 640x480 into several spots; ALL must agree or the render tears:
  * two SDL_CreateTexture calls (render textures)
  * the 8-bit surface buffer malloc (W*H bytes)
  * the palette->RGB copy loop count (W*H pixels)
  * TWO template DDSURFACEDESCs (0x689c5020 16bpp, 0x689c50a0 8bpp) whose
    dwWidth/dwHeight/lPitch the game reads on Lock -> its render stride.
Pair with mods/hi-res/patch_gameres.py (forces the game's render dims to match).

    python mods/hi-res/patch_renderres.py apply | revert | status
"""
import struct, sys
from pathlib import Path

DLL = Path("Need For Speed II SE/DDNFS.dll")
RENDER_W = 1024
RENDER_H = 768

# (va, original, kind)  kinds: W=width H=height A=area(W*H) P1=pitch@1bpp(W) P2=pitch@2bpp(W*2)
P = [
    (0x689c1b44, 480,     "H"),   # SDL_CreateTexture #1 height
    (0x689c1b4c, 640,     "W"),   # SDL_CreateTexture #1 width
    (0x689c1b79, 480,     "H"),   # SDL_CreateTexture #2 height
    (0x689c1b81, 640,     "W"),   # SDL_CreateTexture #2 width
    (0x689c1b9d, 0x4b000, "A"),   # 8-bit surface buffer malloc (bytes)
    (0x689c1cc0, 0x4b000, "A"),   # palette->RGB copy loop count
    (0x689c5028, 480,     "H"),   # template 16bpp  dwHeight
    (0x689c502c, 640,     "W"),   # template 16bpp  dwWidth
    (0x689c5030, 1280,    "P2"),  # template 16bpp  lPitch
    (0x689c50a8, 480,     "H"),   # template 8bpp   dwHeight
    (0x689c50ac, 640,     "W"),   # template 8bpp   dwWidth
    (0x689c50b0, 640,     "P1"),  # template 8bpp   lPitch  (the render stride!)
]
NEW = {"W": RENDER_W, "H": RENDER_H, "A": RENDER_W * RENDER_H, "P1": RENDER_W, "P2": RENDER_W * 2}
ORIG = {"W": 640, "H": 480, "A": 640 * 480, "P1": 640, "P2": 1280}


def _v2f(d, va):
    pe = struct.unpack_from("<I", d, 0x3c)[0]
    imgbase = struct.unpack_from("<I", d, pe + 0x34)[0]
    nsec = struct.unpack_from("<H", d, pe + 6)[0]
    secoff = pe + 24 + struct.unpack_from("<H", d, pe + 20)[0]
    for i in range(nsec):
        o = secoff + i * 40
        sva = struct.unpack_from("<I", d, o + 12)[0]
        vs = struct.unpack_from("<I", d, o + 8)[0]
        raw = struct.unpack_from("<I", d, o + 20)[0]
        rs = struct.unpack_from("<I", d, o + 16)[0]
        sz = vs if vs else rs
        if imgbase + sva <= va < imgbase + sva + sz:
            return raw + (va - imgbase - sva)
    raise SystemExit("no section for 0x%x" % va)


def _set(f):
    d = bytearray(DLL.read_bytes())
    for va, orig, kind in P:
        struct.pack_into("<I", d, _v2f(d, va), f(kind, orig))
    DLL.write_bytes(d)


def apply():
    d = DLL.read_bytes()
    for va, orig, kind in P:
        cur = struct.unpack_from("<I", d, _v2f(d, va))[0]
        if cur != orig:
            raise SystemExit("refuse: 0x%X = %d, expected %d (revert first)" % (va, cur, orig))
    _set(lambda k, o: NEW[k])
    print("render resolution -> %dx%d (textures+buffer+copy+both templates)" % (RENDER_W, RENDER_H))


def revert():
    _set(lambda k, o: ORIG[k]); print("render resolution -> 640x480 (stock)")


def status():
    d = DLL.read_bytes()
    w = struct.unpack_from("<I", d, _v2f(d, 0x689c1b4c))[0]
    h = struct.unpack_from("<I", d, _v2f(d, 0x689c1b44))[0]
    pitch8 = struct.unpack_from("<I", d, _v2f(d, 0x689c50b0))[0]
    print("render %dx%d, 8bpp lPitch=%d %s" % (w, h, pitch8, "(stock)" if (w, h) == (640, 480) else "(patched)"))


if __name__ == "__main__":
    {"apply": apply, "revert": revert, "status": status}[sys.argv[1] if len(sys.argv) > 1 else "status"]()
