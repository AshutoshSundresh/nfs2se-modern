"""Multiply NFS2SE view-distance constants for huge draw distance + no LOD/cull dropout.

Found via Cheat Engine: the view-distance setup at code VA 0x434F5F writes three
distances (scaled by track size + the low/med/high setting) into globals:
  0x4DB330 = far DRAW distance   (base 440/500 units, biggest)
  0x4DB334 = LOD/cull distance   (base 60/110)
  0x4DB338 = LOD/cull distance   (base 92/150)
Both code branches hold the base constants as `mov eax, imm32` (16.16 fixed).
We multiply them: DRAW ~modest (FPS cost), LOD/CULL huge (cheap, keeps distant
cars full-detail and un-culled). Fully reversible; SHA-independent (verifies the
exact old immediate before writing).

    python mods/draw-distance/patch_drawdist.py apply
    python mods/draw-distance/patch_drawdist.py revert
    python mods/draw-distance/patch_drawdist.py status
Tune the two multipliers below and re-run apply (revert first if already applied).
"""
import struct, sys, os
from pathlib import Path

EXE = Path("Need For Speed II SE/nfs2sen.exe")

DRAW_MULT = 5       # 0x4DB330 far draw distance  (raises FPS cost; lower if sluggish)
LODCULL_MULT = 1    # 0x4DB334/338 = fog/depth-cue (NOT car LOD); >1 causes splotchy far terrain

# (imm_va, original_imm, multiplier)
P = [
    (0x434f6b, 0x01b80000, "DRAW"),     # branch A -> 0x4DB330 (440u)
    (0x434fd8, 0x01f40000, "DRAW"),     # branch B -> 0x4DB330 (500u)
    (0x434f8a, 0x003c0000, "LODCULL"),  # branch A -> 0x4DB334 (60u)
    (0x434ff2, 0x006e0000, "LODCULL"),  # branch B -> 0x4DB334 (110u)
    (0x434fb0, 0x005c0000, "LODCULL"),  # branch A -> 0x4DB338 (92u)
    (0x435013, 0x00960000, "LODCULL"),  # branch B -> 0x4DB338 (150u)
]
MULT = {"DRAW": DRAW_MULT, "LODCULL": LODCULL_MULT}


def off(va):
    return va - 0x400C00          # AUTO/code section mapping


def apply():
    d = bytearray(EXE.read_bytes())
    for va, old, kind in P:
        cur = struct.unpack_from("<I", d, off(va))[0]
        if cur != old:
            raise SystemExit("refuse: 0x%X = 0x%X, expected original 0x%X "
                             "(revert first)" % (va, cur, old))
    for va, old, kind in P:
        new = old * MULT[kind]
        assert new < 0x7fffffff, "overflow at 0x%X" % va
        struct.pack_into("<I", d, off(va), new)
        print("  %-8s %5d -> %6d units @0x%X" % (kind, old >> 16, new >> 16, va))
    EXE.write_bytes(d)
    print("applied.")


def revert():
    d = bytearray(EXE.read_bytes())
    for va, old, kind in P:
        struct.pack_into("<I", d, off(va), old)
    EXE.write_bytes(d)
    print("reverted to stock distances.")


def status():
    d = EXE.read_bytes()
    for va, old, kind in P:
        cur = struct.unpack_from("<I", d, off(va))[0]
        tag = "stock" if cur == old else "x%d" % (cur // old) if old and cur % old == 0 else "custom"
        print("  0x%X %-8s cur=%-6d units (orig %d)  [%s]" % (va, kind, cur >> 16, old >> 16, tag))


if __name__ == "__main__":
    {"apply": apply, "revert": revert, "status": status}[sys.argv[1] if len(sys.argv) > 1 else "status"]()
