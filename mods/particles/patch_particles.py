#!/usr/bin/env python3
r"""Beef up the tyre-kicked-up effects (smoke / dust / snow / gravel) in nfs2se-modern.exe.

The particle system (c:\nfs2se\game\pc\skidmark.c; code around 0x435c4c spawn-init,
0x4529c7 per-wheel hub, 0x475193 smoke emitter) throws little animated sprite puffs behind
the tyres: 'sm'=smoke, 'di'=dirt, 'ga'=gravel, 'sn'=snow, 'gr'=grass frames out of
RENDER/PC/FXTEXT.FSH + SFX.FSH.  It's a 2-D sprite system (can't be made volumetric), but
we can make it emit far more readily, keep more puffs alive at once, and render softer.

v2 — v1 was too timid (it only nudged the per-emit throttle, which is a milliseconds gate
that already passes every frame, and only halved one slip threshold).  v2 hits the real
limiters: the slip level needed before loose-surface spray triggers, and the cap on how many
spray puffs may coexist; plus it lowers the per-type sprite alpha so the puffs read as
translucent dust rather than solid blobs.

Each edit is in-place (no size change), located by a UNIQUE byte signature, and applied to a
pristine copy restored from the .partbak backup first -- so it is fully re-tunable: edit the
constants below and re-run `apply`.

    python patch_particles.py apply | revert | status [--exe <path>]
"""
from __future__ import annotations
import argparse, struct, sys, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "Need For Speed II SE"
DEFAULT_EXE = ROOT / "nfs2se-modern.exe"

# ================= TUNABLES (edit + re-run `apply`) =================
# --- frequency ---
SLIP_TRIGGER = 0x00010000   # orig 0x000A0000. Slip needed before dust/snow/gravel spray
                            # fires. LOWER = spray during gentler driving. (1/10th of stock.)
SPRAY_CAP    = 0x64         # orig 0x1E (30). Max concurrent spray-puff "age" before new ones
                            # are skipped. HIGHER = spray re-emits almost every frame.
SMOKE_THROTTLE = 0x00       # orig 0x04. Min ticks between smoke emits (minor; ms-based gate).
ALWAYS_TWO_SMOKE = True     # orig: 2nd smoke puff only 7/8 of the time -> always emit it.
RISE_VEL = 0x1800           # orig 0x0F5C. Upward kick per puff; higher = fuller billow.
# --- translucency (particle alpha 0x00..0xFF; LOWER = more see-through) ---
A_DIRT       = 0x58         # orig 0x90  (type 6 dirt)
A_SMOKE_SNOW = 0x50         # orig 0x80  (type 2 smoke, type 9 snow)
A_GRAVEL_GRASS = 0x80       # orig 0xFF  (type 8 gravel, type 7 grass)
A_SPECIAL    = 0xA0         # orig 0xE2  (types 4/5 big 'ms'/'sp' puffs, packed ARGB)
# ===================================================================

def _patch_list():
    rise = struct.pack("<H", RISE_VEL & 0xffff).hex()        # e.g. 0018
    slip = struct.pack("<I", SLIP_TRIGGER & 0xffffffff).hex() # e.g. 00000100
    smoke2 = "9090" if ALWAYS_TWO_SMOKE else "7415"          # NOP the JZ, or leave it
    # (name, orig_hex, patched_hex, expected_count)
    return [
        ("spray slip trigger",   "81be6001000000000a00", "81be60010000" + slip,              1),
        ("spray concurrent cap", "83f81e7f79",           "83f8%02x7f79" % (SPRAY_CAP & 0xff), 1),
        ("smoke emit throttle",  "29d083f8047f03",       "29d083f8%02x7f03" % (SMOKE_THROTTLE & 0xff), 1),
        ("smoke always-two",     "a8077415ba02000000",   "a807" + smoke2 + "ba02000000",     1),
        ("plume rise velocity",  "8140205c0f0000",       "814020" + rise + "0000",           2),
        ("dirt alpha",           "c6801001000090",       "c68010010000%02x" % (A_DIRT & 0xff), 1),
        ("smoke/snow alpha",     "c6801001000080",       "c68010010000%02x" % (A_SMOKE_SNOW & 0xff), 2),
        ("gravel/grass alpha",   "c68010010000ff",       "c68010010000%02x" % (A_GRAVEL_GRASS & 0xff), 2),
        ("special-fx alpha",     "c780e0000000ffffffe2", "c780e0000000ffffff%02x" % (A_SPECIAL & 0xff), 2),
    ]

def _find_all(d: bytes, pat: bytes):
    out, i = [], d.find(pat)
    while i >= 0:
        out.append(i); i = d.find(pat, i + 1)
    return out

def _check(name, orig, patched):
    o, p = bytes.fromhex(orig), bytes.fromhex(patched)
    if len(o) != len(p):
        raise RuntimeError("%s: length mismatch orig=%d patched=%d" % (name, len(o), len(p)))
    return o, p

def status(path: Path):
    d = path.read_bytes()
    print("%s" % path.name)
    for name, orig, patched, cnt in _patch_list():
        o, p = _check(name, orig, patched)
        no, npp = len(_find_all(d, o)), len(_find_all(d, p))
        state = "PATCHED" if npp else "ORIG" if no else "NOT FOUND"
        print("  %-22s %-9s  %s -> %s   (%d/%d patched)"
              % (name, state, o.hex(), p.hex(), npp, cnt))

def apply(path: Path):
    bak = path.with_suffix(path.suffix + ".partbak")
    if not bak.exists():
        shutil.copyfile(path, bak)          # first run: current exe is the pristine baseline
    else:
        shutil.copyfile(bak, path)          # re-tune: always patch a pristine copy
    d = bytearray(path.read_bytes())
    for name, orig, patched, cnt in _patch_list():
        o, p = _check(name, orig, patched)
        hits = _find_all(bytes(d), o)
        if len(hits) != cnt:
            raise RuntimeError("'%s': expected %d site(s), found %d (unexpected exe)"
                               % (name, cnt, len(hits)))
        for h in hits:
            d[h:h+len(p)] = p
        print("  %-22s patched %d site(s)  %s -> %s" % (name, len(hits), o.hex(), p.hex()))
    path.write_bytes(d)
    print("done.")
    status(path)

def revert(path: Path):
    bak = path.with_suffix(path.suffix + ".partbak")
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
