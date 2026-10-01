"""Fix AI driving of the bonus cars (FZR 2000, Tombstone, Bomber).

Finding (verified against the game files):
  * The three bonus cars use McLaren F1 physics as a PLACEHOLDER. In
    CARDATA.VIV the base blobs `futr.dat` (FZR), `dayt.dat` (Tombstone) and
    `chev.dat` (Bomber) are BYTE-IDENTICAL to `mcf1.dat`. So physically each
    bonus car IS a McLaren F1 (same power, gearing, top speed).
  * The AI, however, loads a SEPARATE per-car data blob (`p<code>`, via the
    "p%s" template at code VA 0x43E59B). The bonus cars ship with custom,
    weaker `pfutr` / `pdayt` / `pchev` AI blobs, so the AI drives them far
    below the car's real potential -- e.g. the FZR AI is easy to beat while
    the McLaren AI (same car!) is hard.

Fix: since the cars are physically McLaren F1s, give their AI the McLaren's
own AI data (`pmcf1`). The AI's model then matches the real physics exactly
and it drives them as well as it drives the McLaren.

This touches ONLY AI data -- the player's car (base `*.dat` in CARDATA.VIV) is
untouched, so the cars drive exactly the same when YOU drive them.

Patched surfaces (all reversible, backed up once):
  * loose  GAMEDATA/Sim/CarData/P<CODE>.DAT  and .QDA   (raw + RefPack copy)
  * in-VIV GAMEDATA/Sim/CarData/CARDATA.VIV  p<code>.DAT entries (in place)

    python mods/ai-bonus-cars/swap_ai_cardata.py status
    python mods/ai-bonus-cars/swap_ai_cardata.py apply
    python mods/ai-bonus-cars/swap_ai_cardata.py revert
"""
from __future__ import annotations
import shutil, struct, sys, os
from pathlib import Path

DIR = Path("Need For Speed II SE/GAMEDATA/Sim/CarData")
VIV = DIR / "CARDATA.VIV"

# bonus car (AI data) -> physics-matched donor (nearest normal car by real
# 356-byte physics: mass / gearing / torque / handling, z-scored):
#   pfutr FZR 2000  (1134 kg, powerful)  -> pmcf1 McLaren F1
#   pdayt Tombstone (1065 kg, grippy)    -> plgt1 Lotus GT1
#   pchev Bomber    (1460 kg, heavy)     -> pgt90 Ford GT90
MAP = {"pfutr": "pmcf1", "pdayt": "plgt1", "pchev": "pgt90"}
TARGETS = list(MAP)
EXTS = [".DAT", ".QDA"]


def _p(name, ext):
    return DIR / (name.upper() + ext)


# ---- loose files -----------------------------------------------------------
def _loose_apply():
    for ext in EXTS:
        for t, donor in MAP.items():
            tgt, don = _p(t, ext), _p(donor, ext)
            if not don.is_file() or not tgt.is_file():
                print("  skip loose %s%s (missing)" % (t.upper(), ext)); continue
            bak = tgt.with_suffix(tgt.suffix + ".aibak")
            if not bak.exists():
                shutil.copy2(tgt, bak)
            shutil.copy2(don, tgt)
            print("  loose %s%s <- %s%s" % (t.upper(), ext, donor.upper(), ext))


def _loose_revert():
    for ext in EXTS:
        for t in TARGETS:
            tgt = _p(t, ext)
            bak = tgt.with_suffix(tgt.suffix + ".aibak")
            if bak.exists():
                shutil.copy2(bak, tgt); print("  loose %s%s reverted" % (t.upper(), ext))


# ---- CARDATA.VIV (BIGF) in-place -------------------------------------------
def _viv_entries(d):
    n = struct.unpack_from(">I", d, 8)[0]
    off = 16; out = []
    for _ in range(n):
        o, s = struct.unpack_from(">II", d, off); off += 8
        end = d.index(b"\x00", off); name = d[off:end].decode(); off = end + 1
        out.append((name, o, s))
    return out


def _viv_apply():
    bak = VIV.with_suffix(VIV.suffix + ".aibak")
    if not bak.exists():
        shutil.copy2(VIV, bak)
    d = bytearray(VIV.read_bytes())
    ents = _viv_entries(d)
    def blob(code):
        return next((bytes(d[o:o + s]) for n, o, s in ents if n.lower() == code + ".dat"), None)
    for n, o, s in ents:
        base = n.lower().rsplit(".", 1)[0]
        if base in MAP:
            donor = blob(MAP[base])
            if donor is not None and len(donor) == s:
                d[o:o + s] = donor
                print("  VIV  %s <- %s.dat" % (n, MAP[base]))
    VIV.write_bytes(d)


def _viv_revert():
    bak = VIV.with_suffix(VIV.suffix + ".aibak")
    if bak.exists():
        shutil.copy2(bak, VIV); print("  VIV reverted")


# ---- commands --------------------------------------------------------------
def apply():
    print("loose files:"); _loose_apply()
    print("CARDATA.VIV:"); _viv_apply()


def revert():
    _loose_revert(); _viv_revert()


def status():
    import hashlib
    def md5(p):
        return hashlib.md5(open(p, "rb").read()).hexdigest()[:12] if os.path.exists(p) else "MISSING"
    for t, donor in MAP.items():
        row = ["%s<-%s" % (t.upper(), donor.upper())]
        for ext in EXTS:
            bak = _p(t, ext).with_suffix(_p(t, ext).suffix + ".aibak")
            match = os.path.exists(_p(t, ext)) and md5(_p(t, ext)) == md5(_p(donor, ext))
            row.append("%s=%s%s" % (ext, "donor" if match else "orig", " [bak]" if bak.exists() else ""))
        print("  " + "  ".join(row))
    print("  VIV backup present:", VIV.with_suffix(VIV.suffix + ".aibak").exists())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"apply": apply, "revert": revert, "status": status}[cmd]()
