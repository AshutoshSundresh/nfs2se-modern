#!/usr/bin/env python3
"""Give the McLaren F1 (carType 0) 35 factory paint colours in nfs2se-modern.exe.

COLOUR SYSTEM (modern NFSIISE build, reverse-engineered):
  * Static HSV palette, 89 entries x 16 bytes (H,S,V,x as 4x int32, H/S/V on 0..255),
    read by ONE bounds-check-free accessor FUN_0045980A at VA 0x45980A, which hard-codes
    the palette base 0x4AF473 (+4/+8/+C) in four MOV disp32s.
  * Static per-car {baseSlot,count} byte-pair table at VA 0x4ADD2F (carType-indexed).
    McLaren(0) = {60,6} -> slots 60..65 (confirmed live).  Count byte is the real limiter.
  * The garage swatch AND the 3D model recolour both go through the one accessor.

WHY A RELOCATION (and why NOT a .data "cave"):  McLaren's 6 slots are boxed in; slots 0..88
are all used by some car; slots >=89 alias other data.  A first attempt relocated the palette
into a 3101-byte zero run in .data -- but that region is a RUNTIME-LIVE buffer (reached via a
computed pointer, so it has no static xref), and the game zeroed the upper half at runtime ->
GT90/Isdera/Cala/McLaren went black.  Fix: the relocated 124-entry palette now lives in a
`const int mclaren_ext_palette[124*4]` compiled from mods/mclaren-colors/mclaren_palette.c,
which the linker places in READ-ONLY .rdata -- the running game physically cannot write it.

THIS PATCH (post-build, in-place, reversible via .mcbak):
  1) find mclaren_ext_palette in the exe by its unique 35-entry McLaren byte signature
     (the stock palette has no such block), deriving the array base = sig - 89*16;
  2) repoint the accessor's 4 base disp32s 0x4AF473.. -> &mclaren_ext_palette[0.. ] ;
  3) set McLaren's table entry (0x4ADD2F) base 60->89, count 6->35.
Other cars keep slots 0..88 (identical copies baked into the array); only the McLaren moves
to slots 89..123.  Requires the build to have compiled mclaren_palette.c (build.sh does).

    python patch_mclaren_colors.py apply | revert | status [--exe <path>]
"""
from __future__ import annotations
import argparse, struct, sys, shutil, colorsys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "Need For Speed II SE"
DEFAULT_EXE = ROOT / "nfs2se-modern.exe"

IMGBASE      = 0x400000
PAL_VA       = 0x4af473
PAL_ENTRIES  = 89
ENTRY        = 16
ACCESSOR_VA  = 0x45980a
ACCESSOR_LEN = 44
TABLE_VA     = 0x4add2f
MCLAREN      = 0
NEW_BASE     = PAL_ENTRIES   # 89
OLD_BASES    = [PAL_VA + k for k in (0, 4, 8, 12)]

# --- minimap/blip colour table (stock DAT_0116194c): 89 packed-RGBA entries, keyed by a car's
#     colour slot, built each race by FUN_0047B47B. McLaren slots 89..123 overrun it, so it is
#     relocated to the writable `mclaren_color_table` global and its builder loop bumped 89->124.
#     NOTE: the table lives in .bss, which the added .rdata palette shifts between builds, so its
#     current address is READ from the code (CT_READ0) rather than hard-coded. The code sites are
#     in .text (before any inserted data) and so are stable.
CT_READS     = [0x47905d, 0x4791c8]   # imm32 == color_table      (MOV reg,[slot*4+ct])
CT_WRITE     = 0x47b5eb                # imm32 == color_table-4    (MOV [EDI+ct-4],EAX, EDI pre+4)
CT_LOOP_CMP  = 0x47b5f1                # 'CMP ESI,0x59 ; JL loop_top' (9 bytes: 83 fe 59 0f 8c rel32)
CT_NEW_COUNT = 144                     # new builder-loop bound (89 stock + 35 McLaren + 20 F355)
# The builder loop bound is a SIGNED imm8 (CMP ESI,imm8).  124 (0x7C) fit, but 144 (0x90) would
# sign-extend to -112 and kill the loop, and we can't widen the instruction in place (it would
# shift .data/.rdata and break every fixed VA below).  So the 9-byte CMP+JL is replaced by a jump
# to a .text code cave that re-does the compare with a 32-bit immediate (see patch_loop_bound).

X = 0x50
MCLAREN_PAINTS = [
    ("AMG Green Velvet","294438"),("Aubergine","493746"),("Base Silver","B9BCC0"),
    ("Black Metallic","20211F"),("Blood Red Solid","981B2E"),("Brazilian Brown Metallic","5D4840"),
    ("Brilliant Blue Metallic","0758B3"),("British Racing Green","123A35"),("Calypso Red Pearl","AA3B53"),
    ("Carbon","303235"),("Cobalt Blue","283E7C"),("Creighton Brown","64565F"),
    ("Dandelion Yellow","E6BF35"),("Dark Blue Mica","162642"),("Dark Burgundy","4F1426"),
    ("Dark Metallic Green","2F452F"),("Dark Purple Pearl","302747"),("Dark Silver","777B80"),
    ("Dorchester Grey","54595B"),("Genesis Blue Metallic","295C94"),("Genesis Dark Blue","1A2D4A"),
    ("Grand Prix Red","CA1833"),("Historic Orange","F67E10"),("Jet Black","101113"),
    ("Jet Black 10pct Flake","18191A"),("Magnesium Silver","B9BCC1"),("Mercedes Brilliant Silver","C8CDD1"),
    ("Mid Blue Pearl","60728A"),("Midnight Blue Pearl","172640"),("Pale Blue Metallic","97AFC0"),
    ("Special Silver","C9CDCF"),("Special White","F2F1EF"),("Titanium Yellow","F3D849"),
    ("Marlboro White","F2F2EF"),("Yquem","D56835"),
]
NEW_COUNT = len(MCLAREN_PAINTS)   # 35
# Ferrari F355 (carType 2): 20 factory paints baked into mclaren_ext_palette[124..143].
F355_BASE  = NEW_BASE + NEW_COUNT  # 89 + 35 = 124
F355_COUNT = 20
# Mustang Mach III (carType 5): trimmed from 4 stock colours to just 2 (Hot Poppy, Jungle Green
# Pearl), which overwrite its first two in-place palette slots 56..57 (set in mclaren_palette.c).
MACH_BASE  = 56
MACH_COUNT = 2

def hex_to_hsv255(hx):
    r = int(hx[0:2], 16)/255.0; g = int(hx[2:4], 16)/255.0; b = int(hx[4:6], 16)/255.0
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return (int(round(h*255)) & 0xff, int(round(s*255)), int(round(v*255)))

def mclaren_block():
    out = bytearray()
    for _n, hx in MCLAREN_PAINTS:
        h, s, v = hex_to_hsv255(hx)
        out += struct.pack("<4i", h, s, v, X)
    return bytes(out)

# ---- PE VA<->file offset ----
def _secs(d):
    pe = struct.unpack_from("<I", d, 0x3c)[0]
    nsec = struct.unpack_from("<H", d, pe+6)[0]; opt = struct.unpack_from("<H", d, pe+20)[0]
    so = pe+24+opt; out = []
    for i in range(nsec):
        e = so+i*40; vs, va, rs, ptr = struct.unpack_from("<IIII", d, e+8)
        out.append((IMGBASE+va, vs, ptr, rs))
    return out
def v2f(d, va):
    for sva, vs, ptr, rs in _secs(d):
        if sva <= va < sva+max(vs, rs): return ptr+(va-sva)
    raise SystemExit("VA 0x%x not mapped" % va)
def f2v(d, fo):
    for sva, vs, ptr, rs in _secs(d):
        if ptr <= fo < ptr+rs: return sva+(fo-ptr)
    raise SystemExit("file off 0x%x not in a raw section" % fo)

def find_array_base(d):
    """Return (array_base_va, array_base_fo) by locating the unique McLaren block."""
    sig = mclaren_block()
    i = d.find(sig)
    if i < 0:
        raise SystemExit("mclaren_ext_palette not found -- did the build compile "
                         "mclaren_palette.c?  (McLaren 35-colour signature absent)")
    if d.find(sig, i+1) >= 0:
        raise SystemExit("McLaren signature found more than once -- ambiguous")
    base_fo = i - PAL_ENTRIES*ENTRY
    return f2v(d, base_fo), base_fo

def map_symbol_va(path, name):
    """Read a symbol's VA from the ld .map next to the exe (handles leading underscore)."""
    mp = path.with_suffix(".map")
    if not mp.exists():
        raise SystemExit("map file not found: %s (needed for %s)" % (mp.name, name))
    import re
    want = (name, "_" + name)
    va = None
    for ln in mp.read_text(errors="replace").splitlines():
        m = re.search(r"0x([0-9a-fA-F]{8,16})\s+(\S+)", ln)
        if m and m.group(2) in want:
            va = int(m.group(1), 16); break
    if va is None:
        raise SystemExit("symbol %s not in map (did mclaren_palette.c link?)" % name)
    return va & 0xffffffff

def _patch_u32_at(d, va, expect, newv):
    fo = v2f(d, va)
    if struct.unpack_from("<I", d, fo)[0] != expect:
        raise SystemExit("at 0x%x expected 0x%x, got 0x%x (layout shifted / already patched)"
                         % (va, expect, struct.unpack_from("<I", d, fo)[0]))
    struct.pack_into("<I", d, fo, newv & 0xffffffff)

def find_text_cave(d, need):
    """Return the VA of a run of >= `need` zero bytes inside an executable section (.text)."""
    pe = struct.unpack_from("<I", d, 0x3c)[0]
    nsec = struct.unpack_from("<H", d, pe+6)[0]; opt = struct.unpack_from("<H", d, pe+20)[0]
    so = pe+24+opt
    for i in range(nsec):
        e = so+i*40
        vs, va, rs, ptr = struct.unpack_from("<IIII", d, e+8)
        chars = struct.unpack_from("<I", d, e+36)[0]
        if not (chars & 0x20000000):            # IMAGE_SCN_MEM_EXECUTE
            continue
        blob = d[ptr:ptr+rs]; run = 0; start = 0
        for j, b in enumerate(blob):
            if b == 0:
                if run == 0: start = j
                run += 1
                if run >= need:
                    return IMGBASE + va + start   # VA of cave start
            else:
                run = 0
    raise SystemExit("no %d-byte code cave found in an executable section" % need)

def patch_loop_bound(d):
    """Replace 'CMP ESI,0x59 ; JL loop_top' (9 bytes) with a jump to a code-cave trampoline that
    does 'CMP ESI,144 (imm32) ; JL loop_top ; JMP loop_exit', so the minimap colour_table builder
    fills all 144 slots.  Keeps every other address fixed (no section shift)."""
    op_va = CT_LOOP_CMP - 2                            # CT_LOOP_CMP points at the imm8; opcode is -2
    f = v2f(d, op_va)
    if d[f:f+5] != b"\x83\xfe\x59\x0f\x8c":            # CMP ESI,0x59 ; JL rel32
        raise SystemExit("loop site at 0x%x != 'cmp esi,0x59 / jl' (got %s) -- already patched or "
                         "layout changed" % (op_va, d[f:f+5].hex()))
    jl_rel   = struct.unpack_from("<i", d, f+5)[0]
    jl_end   = op_va + 9                               # byte after the JL  (= loop exit / fallthru)
    loop_top = (jl_end + jl_rel) & 0xffffffff          # JL target
    loop_exit = jl_end
    cave_va = find_text_cave(d, 18)
    cf = v2f(d, cave_va)
    t = bytearray(b"\x81\xfe" + struct.pack("<I", CT_NEW_COUNT))        # CMP ESI, 144
    jl_at = cave_va + len(t)
    t += b"\x0f\x8c" + struct.pack("<i", loop_top - (jl_at + 6))         # JL loop_top
    jmp_at = cave_va + len(t)
    t += b"\xe9" + struct.pack("<i", loop_exit - (jmp_at + 5))   # JMP loop_exit
    d[cf:cf+len(t)] = t
    site = bytearray(b"\xe9" + struct.pack("<i", cave_va - (op_va + 5)))
    site += b"\x90" * (9 - len(site))                  # pad to the original 9 bytes with NOPs
    d[f:f+9] = site
    return cave_va, loop_top

def apply(path: Path):
    d = bytearray(path.read_bytes())
    bak = path.with_suffix(path.suffix + ".mcbak")
    if not bak.exists():
        shutil.copyfile(path, bak)
    arr_va, arr_fo = find_array_base(d)
    # sanity: array entry 0 must equal stock palette entry 0 (0,0,210,80)
    stock0 = d[v2f(d, PAL_VA):v2f(d, PAL_VA)+ENTRY]
    if d[arr_fo:arr_fo+ENTRY] != stock0:
        raise SystemExit("array entry0 != stock palette entry0 -- wrong array located")
    # 1) repoint accessor's 4 base disp32s (within its 44-byte window only)
    acc = v2f(d, ACCESSOR_VA); win = d[acc:acc+ACCESSOR_LEN]
    for k, oldv in enumerate(OLD_BASES):
        j = win.find(struct.pack("<I", oldv))
        if j < 0:
            raise SystemExit("accessor base 0x%x not found (already patched?)" % oldv)
        win[j:j+4] = struct.pack("<I", arr_va + 4*k)
    d[acc:acc+ACCESSOR_LEN] = win
    # 2) McLaren table base 60->89, count 6->35
    tbl = v2f(d, TABLE_VA)
    d[tbl + MCLAREN*2] = NEW_BASE
    d[tbl + MCLAREN*2 + 1] = NEW_COUNT
    # Ford GT90 (carType 3): FORCED single colour -> count 6->0 (same as the stock forced cars
    # Indigo/Bomber/Tombstone, so the garage shows no paint selector). Base stays slot 66, which
    # the car-load init copies into the live colour slot, so the model renders #F1F1EF (set in
    # mclaren_palette.c). Slot 66 is GT90-only; slots 67..71 become unused.
    GT90 = 3
    d[tbl + GT90*2 + 1] = 0
    # Ferrari F355 F1 (carType 2): 20 factory paints -> relocated slots 124..143 (same lockstep
    # expansion as the McLaren: the 20 entries are baked into mclaren_ext_palette[124..143] and
    # the minimap table/loop below cover them). base 82->124, count 5->20.
    F355 = 2
    d[tbl + F355*2]     = F355_BASE   # 124
    d[tbl + F355*2 + 1] = F355_COUNT  # 20
    # Mustang Mach III (carType 5): keep base slot 56, trim count 4 -> 2 (slots 56..57 reskinned).
    MACH = 5
    d[tbl + MACH*2]     = MACH_BASE   # 56
    d[tbl + MACH*2 + 1] = MACH_COUNT  # 2
    # 3) relocate the 89-entry minimap colour table to the 124-slot writable global and
    #    bump its builder loop so slots 89..123 are covered (fixes black/absent minimap dots
    #    and the OOB that crashed the 2nd race when the field is McLarens).
    ct_va = map_symbol_va(path, "mclaren_color_table")
    # current stock color_table VA = whatever the first read instruction references in THIS build
    ct_cur = struct.unpack_from("<I", d, v2f(d, CT_READS[0]))[0]
    for site in CT_READS:                      # MOV reg,[slot*4 + color_table]
        _patch_u32_at(d, site, ct_cur, ct_va)
    _patch_u32_at(d, CT_WRITE, ct_cur - 4, ct_va - 4)   # MOV [EDI + color_table-4], EAX
    cave_va, _ = patch_loop_bound(d)           # builder loop 89 -> 144 via .text trampoline
    path.write_bytes(d)
    print("patched: accessor -> mclaren_ext_palette @ 0x%x ; color_table -> 0x%x (%d, loop-cave "
          "@0x%x) ; McLaren base=%d count=%d ; F355 base=%d count=%d"
          % (arr_va, ct_va, CT_NEW_COUNT, cave_va, NEW_BASE, NEW_COUNT, F355_BASE, F355_COUNT))
    status(path)

def revert(path: Path):
    bak = path.with_suffix(path.suffix + ".mcbak")
    if not bak.exists():
        print("no backup (%s); nothing to revert" % bak.name); return
    shutil.copyfile(bak, path); print("reverted from %s" % bak.name)

def status(path: Path):
    d = path.read_bytes()
    tbl = v2f(d, TABLE_VA)
    base = d[tbl + MCLAREN*2]; cnt = d[tbl + MCLAREN*2 + 1]
    acc = v2f(d, ACCESSOR_VA); win = d[acc:acc+ACCESSOR_LEN]
    repointed = struct.pack("<I", PAL_VA) not in win
    print("  McLaren table: base=%d count=%d" % (base, cnt))
    print("  accessor repointed off stock palette: %s" % repointed)
    try:
        arr_va, _ = find_array_base(d)
        print("  mclaren_ext_palette present @ 0x%x" % arr_va)
    except SystemExit as e:
        print("  mclaren_ext_palette: NOT FOUND (%s)" % e)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", nargs="?", default="status", choices=("apply", "revert", "status"))
    ap.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    a = ap.parse_args()
    if not a.exe.exists():
        print("ERROR: exe not found: %s" % a.exe, file=sys.stderr); return 1
    {"apply": apply, "revert": revert, "status": status}[a.action](a.exe)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
