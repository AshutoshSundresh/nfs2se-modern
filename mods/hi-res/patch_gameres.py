"""Force nfs2sen.exe's internal render resolution to 1024x768.

The resolution setup func at 0x47E6D0 writes the render width/height globals
(0x51D384/0x51D388) and has a built-in path: width==-1 -> 1024, height==-1 ->
768. We NOP the two "if != -1" branches so it ALWAYS falls into the 1024x768
case, regardless of the requested (640x480) resolution. Pair with the DDNFS
1024x768 patch (buffer+texture+copy loop) so both sides agree.

    python mods/hi-res/patch_gameres.py apply
    python mods/hi-res/patch_gameres.py revert
    python mods/hi-res/patch_gameres.py status
"""
import sys
from pathlib import Path

EXE = Path("Need For Speed II SE/nfs2sen.exe")
# (va, original 2 bytes, patched 2 bytes)
P = [
    (0x47e72b, b"\x75\xca", b"\x90\x90"),  # jne (width != -1) -> nop -> width=1024
    (0x47e737, b"\x75\xc7", b"\x90\x90"),  # jne (height != -1) -> nop -> height=768
]


def off(va):
    return va - 0x400C00


def apply():
    d = bytearray(EXE.read_bytes())
    for va, orig, new in P:
        if d[off(va):off(va) + 2] != orig:
            raise SystemExit("refuse: 0x%X != %s (revert first)" % (va, orig.hex()))
    for va, orig, new in P:
        d[off(va):off(va) + 2] = new
    EXE.write_bytes(d)
    print("render dims forced -> 1024x768")


def revert():
    d = bytearray(EXE.read_bytes())
    for va, orig, new in P:
        d[off(va):off(va) + 2] = orig
    EXE.write_bytes(d)
    print("render dims -> stock (from requested resolution)")


def status():
    d = EXE.read_bytes()
    on = all(d[off(va):off(va) + 2] == new for va, orig, new in P)
    print("forced-1024x768:", "YES" if on else "no (stock)")


if __name__ == "__main__":
    {"apply": apply, "revert": revert, "status": status}[sys.argv[1] if len(sys.argv) > 1 else "status"]()
