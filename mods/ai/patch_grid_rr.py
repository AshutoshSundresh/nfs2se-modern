"""Round-robin the mid/back grid personalities into the top three.

PRSONAL.DAT opens with four 12-byte grid tables (one ASCII personality letter
per grid slot):
    0x00 KnockOut            a b c d e f g h i j k l
    0x0c Tournament          a b c d e f g h i j k l
    0x18 Single (1 opponent)  m m m m m m m m m m m m   (untouched - no d..h)
    0x24 Single (multi)      a b c d e f g h i j k l
Everything from 0x30 on is parameter data (glue curves, speed factors) where
these byte values recur as plain numbers, so we ONLY rewrite the 48-byte grid
region.

We remap d e f g h -> a b c a b (a round-robin of a,b,c), turning each multi-car
grid into  a b c a b c a b i j k l  so slots 0-7 cycle the three fast/aggressive
personalities (A front-runner, B aggressor, C player-hunter).

    python mods/ai/patch_grid_rr.py apply | revert | status
"""
import sys, shutil
from pathlib import Path

DAT = Path("Need For Speed II SE/GAMEDATA/Sim/AI/PRSONAL.DAT")
BAK = DAT.with_suffix(".DAT.rrbak")
GRID = 0x30  # first 48 bytes = 4 x 12-slot grid tables

REMAP = {ord("d"): ord("a"), ord("e"): ord("b"),
         ord("f"): ord("c"), ord("g"): ord("a"), ord("h"): ord("b")}
INV = b"defgh"          # letters we replace (for status/verify)


def apply():
    if not BAK.exists():
        shutil.copyfile(DAT, BAK)
    d = bytearray(DAT.read_bytes())
    n = 0
    for i in range(GRID):
        if d[i] in REMAP:
            d[i] = REMAP[d[i]]; n += 1
    DAT.write_bytes(d)
    print("remapped %d grid slots (d->a e->b f->c g->a h->b)" % n)
    _show(d)


def revert():
    if BAK.exists():
        shutil.copyfile(BAK, DAT)
        print("PRSONAL.DAT restored from backup")
    else:
        print("no backup found")
    _show(DAT.read_bytes())


def status():
    _show(DAT.read_bytes())


def _show(d):
    names = ["KnockOut  ", "Tournament", "Single-1  ", "Single-N  "]
    for k in range(4):
        row = d[k * 12:(k + 1) * 12].decode("latin1")
        print("  %s : %s" % (names[k], " ".join(row)))
    left = sum(d[i] in REMAP for i in range(GRID))
    print("  d..h remaining in grids:", left)


if __name__ == "__main__":
    {"apply": apply, "revert": revert, "status": status}[sys.argv[1] if len(sys.argv) > 1 else "status"]()
