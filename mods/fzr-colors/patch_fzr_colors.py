#!/usr/bin/env python3
"""Give the FZR 2000 (FUTR, car 14) a real 6-colour palette in nfs2se-modern.exe.

Stock FUTR ships with colorCount = 1 (a single dark-blue), so neither the player
nor the AI has any colour choice, and the Class D code had to borrow out-of-range
indices (which is how the hidden "ghost" easter egg at colour 88 got exposed).

This patch, applied to the freshly built nfs2se-modern.exe:
  1) sets FUTR's per-car colour count from 1 to 6, so the garage colour picker
     (single player) AND the normal AI colour logic both offer 6 FZR colours;
  2) overwrites FUTR's six global palette slots (71..76) with a curated set:
        71 red, 72 black, 73 white/silver (Isdera), 74 blue, 75 gold, 76 green.
The matching Class D asm pass (bonus_fzr_cols) cycles opponents through 71..76.

Everything is located by CONTENT (the 15-entry colour-count table), so it keeps
working even if the build layout shifts. Idempotent and reversible.

    python patch_fzr_colors.py apply | revert | status | --exe <path>
"""
from __future__ import annotations
import argparse, struct, sys, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "Need For Speed II SE"
DEFAULT_EXE = ROOT / "nfs2se-modern.exe"

# stock per-car colour counts (carType 0..14), used to locate the table by content
STOCK_COUNTS = [6, 4, 4, 4, 10, 4, 11, 10, 10, 1, 2, 2, 2, 1, 1]
FUTR = 14                       # FZR 2000 car index
NEW_FUTR_COUNT = 6
PAL_FROM_COUNT = 0x13C          # palette VA 0x4af473 - count-table VA 0x4af337
FUTR_BASE_SLOT = 71             # cumulative colour slots of cars 0..13 = 71

# curated FZR palette, HSV(H,S,V,x) as the game stores it (all copied from real
# in-game colours so they render correctly): red, black, white, blue, gold, green
FZR_COLORS = [
    (254, 215, 249, 96),   # 71 red
    (0,   0,   24,  96),   # 72 black (dark "opponent black")
    (45,  0,   254, 104),  # 73 white / silver  (Isdera Commendatore)
    (160, 255, 220, 104),  # 74 Bugatti EB110 electric blue
    (205, 220, 195, 104),  # 75 Jaguar XJ220 / Diablo metallic violet
    (115, 235, 205, 104),  # 76 Vector-style 90s teal
]

# The FZR's garage "black" uses palette slot 88 (the old ghost-black slot, now a normal
# colour since the ghost easter egg is disabled). Match it to the dark opponent black.
GARAGE_BLACK_SLOT = 88
GARAGE_BLACK = (0, 0, 24, 96)

def _count_pat(counts):
    return b"".join(struct.pack("<i", c) for c in counts)

def _find_count_table(d):
    pat = _count_pat(STOCK_COUNTS)
    i = d.find(pat)
    if i < 0:
        # maybe already patched (FUTR count changed) -> match first 14 entries
        pat14 = _count_pat(STOCK_COUNTS[:14])
        i = d.find(pat14)
        if i < 0:
            raise RuntimeError("colour-count table not found (unexpected exe)")
    return i

def _slots(d, cnt_off):
    pal = cnt_off + PAL_FROM_COUNT + FUTR_BASE_SLOT * 16
    return pal

def status(path):
    d = path.read_bytes()
    c = _find_count_table(d)
    futr_cnt = struct.unpack("<i", d[c + FUTR * 4:c + FUTR * 4 + 4])[0]
    pal = _slots(d, c)
    print("%s" % path.name)
    print("  count-table @ file 0x%x   FUTR colorCount = %d" % (c, futr_cnt))
    for k in range(6):
        hsv = struct.unpack("<4i", d[pal + k * 16:pal + k * 16 + 16])
        print("  slot %2d  HSV=%s" % (FUTR_BASE_SLOT + k, hsv))

def apply(path):
    d = bytearray(path.read_bytes())
    c = _find_count_table(d)
    bak = path.with_suffix(path.suffix + ".fzrbak")
    if not bak.exists():
        shutil.copyfile(path, bak)
    # IMPORTANT: palette slots 71..76 are the Isdera Commendatore's REAL 6 colours. The
    # stock per-car count table (which claimed FUTR=71 / ISDE=66-67) is vestigial and WRONG;
    # overwriting 71..76 replaced the Isdera's colours in-game. So we DO NOT touch them -- and
    # because the Class D FZR opponents already index 71..76, they correctly show the real
    # Isdera colours (which was the whole "give the FZR the Isdera Commendatore colours" goal).
    # We also no longer poke the vestigial count table (it had no effect).
    # Only the garage-black slot 88 (the ex-ghost slot, not any car's colour) is set.
    pal_base = c + PAL_FROM_COUNT
    struct.pack_into("<4i", d, pal_base + GARAGE_BLACK_SLOT * 16, *GARAGE_BLACK)
    path.write_bytes(d)
    print("patched FZR garage-black slot %d; Isdera colours (slots 71-76) left stock"
          % GARAGE_BLACK_SLOT)
    status(path)

def revert(path):
    bak = path.with_suffix(path.suffix + ".fzrbak")
    if not bak.exists():
        print("no backup (%s); nothing to revert" % bak.name); return
    shutil.copyfile(bak, path)
    print("reverted from %s" % bak.name)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", nargs="?", default="status",
                    choices=("apply", "revert", "status"))
    ap.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    a = ap.parse_args()
    if not a.exe.exists():
        print("ERROR: exe not found: %s" % a.exe, file=sys.stderr); return 1
    {"apply": apply, "revert": revert, "status": status}[a.action](a.exe)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
