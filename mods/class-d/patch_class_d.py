#!/usr/bin/env python3
"""nfs2sen.exe: bonus cars (16-18) + new Class D (value 19) opponent option.

Supersedes patch_bonus_ai_cars.py. Class D picks a bonus car (Bomber/Tombstone/
FZR) per AI opponent, round-robin, and shows the 'clsd' card + 'class D' label.
Applies to the ORIGINAL nfs2sen.exe; fully reversible and SHA-guarded.
"""
from __future__ import annotations
import argparse, hashlib, shutil, struct, sys
from dataclasses import dataclass
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
GAME = PROJECT / "Need For Speed II SE"
EXE = "nfs2sen.exe"
ORIGINAL_SHA256 = "467B2757F65B26E22688E0568A370DB9B2C6EFA417ABB465BD250169BE57E495"

SEL = 0x4E0115                        # selected-opponent global (byte)

# ---- data region (DGROUP tail padding, zero + unreferenced) ----
DATA_VA   = 0x4D3900
DATA_OFF  = DATA_VA - 0x401C00        # file offset (DGROUP mapping)
ICON_TABLE_VA = DATA_VA               # 20 dwords
CLSD_NAME_VA  = DATA_VA + 20 * 4      # "clsd\0"
RR_CTR_VA     = CLSD_NAME_VA + 5      # round-robin counter byte

CARD_NAMES = [0x4B9320 + i * 8 for i in range(12)] + [0x4B9398, 0x4B93A0, 0x4B93A8] \
             + [0] + [0x4B9380, 0x4B9388, 0x4B9390] + [CLSD_NAME_VA]  # idx 0..19
D_STR_VA = DATA_VA + 20 * 4 + 5 + 1   # "D\0" string (after icon table, clsd name, RR ctr)

# ---- code cave (region 1, 0x1EA bytes free) ----
CAVE_VA  = 0x482D06
CAVE_OFF = CAVE_VA - 0x400C00
CAVE_CAP = 0x1EA

# hook targets inside original code
FG_ORIG, FG_WRITE   = 0x40657C, 0x406593
OO_ORIG, OO_CONT    = 0x4072D4, 0x4064BB
SUM_MAP, SUM_LEG    = 0x40BA3D, 0x40BF14
UI_CLASS, UI_DIRECT = 0x40C882, 0x40CB56
ICON_RENDER         = 0x405ED0
SS_OK, SS_REJECT    = 0x40E55E, 0x40E528
NORM_DIRECT, NORM_CLASS = 0x40EF96, 0x40F2F2


def r32(after, dst):
    return struct.pack("<i", dst - after)


class Asm:
    """Single-stream assembler for the cave; supports named labels."""

    def __init__(self, base):
        self.base = base
        self.b = bytearray()
        self.lab = {}
        self.fix = []

    @property
    def va(self):
        return self.base + len(self.b)

    def label(self, n):
        self.lab[n] = self.va

    def db(self, *x):
        self.b += bytes(x)

    def raw(self, d):
        self.b += bytes(d)

    def imm32(self, a):
        self.b += struct.pack("<I", a)

    def mov_al_m(self, a):
        self.db(0xA0); self.imm32(a)               # mov al,[a]

    def mov_dh_m(self, a):
        self.db(0x8A, 0x35); self.imm32(a)          # mov dh,[a]

    def mov_ah_m(self, a):
        self.db(0x8A, 0x25); self.imm32(a)          # mov ah,[a]

    def movzx_eax_m(self, a):
        self.db(0x0F, 0xB6, 0x05); self.imm32(a)    # movzx eax,byte[a]

    def mov_m_dl(self, a):
        self.db(0x88, 0x15); self.imm32(a)          # mov [a],dl

    def ret(self):
        self.db(0xC3)

    def jmp_abs(self, dst):
        self.db(0xE9); self.b += r32(self.va + 4, dst)

    def call_abs(self, dst):
        self.db(0xE8); self.b += r32(self.va + 4, dst)

    def jcc_abs(self, cc, dst):
        self.db(0x0F, cc); self.b += r32(self.va + 4, dst)

    def _pl(self, n):
        off = len(self.b); self.b += b"\x00\x00\x00\x00"; self.fix.append((off, n))

    def jmp_lbl(self, n):
        self.db(0xE9); self._pl(n)

    def call_lbl(self, n):
        self.db(0xE8); self._pl(n)

    def jcc_lbl(self, cc, n):
        self.db(0x0F, cc); self._pl(n)

    def finish(self):
        for off, n in self.fix:
            struct.pack_into("<i", self.b, off, self.lab[n] - (self.base + off + 4))
        return bytes(self.b)


JB, JBE, JA, JNE, JE = 0x82, 0x86, 0x87, 0x85, 0x84


def build_cave():
    a = Asm(CAVE_VA)
    # ---- ROUNDROBIN: eax = 12/13/14 (cycling), preserves edx ----
    a.label("rr")
    a.movzx_eax_m(RR_CTR_VA)              # eax = ctr 0..2
    a.db(0x52)                            # push edx
    a.db(0x8D, 0x50, 0x01)               # lea edx,[eax+1]
    a.db(0x80, 0xFA, 0x03)               # cmp dl,3
    a.jcc_lbl(JB, "rr_s")
    a.db(0x31, 0xD2)                     # xor edx,edx
    a.label("rr_s")
    a.mov_m_dl(RR_CTR_VA)                 # mov [ctr],dl
    a.db(0x5A)                            # pop edx
    a.db(0x83, 0xC0, 0x0C)               # add eax,12
    a.ret()
    # ---- FULL_GRID ----
    a.label("fg")
    a.mov_dh_m(SEL)
    a.db(0x80, 0xFE, 0x13)               # cmp dh,19
    a.jcc_lbl(JNE, "fg_n19")
    a.call_lbl("rr")                     # eax = car
    a.jmp_abs(FG_WRITE)
    a.label("fg_n19")
    a.db(0x80, 0xFE, 0x10)               # cmp dh,16
    a.jcc_abs(JB, FG_ORIG)
    a.db(0x80, 0xFE, 0x12)               # cmp dh,18
    a.jcc_abs(JA, FG_ORIG)
    a.db(0x80, 0xEE, 0x04)               # sub dh,4
    a.db(0x31, 0xC0, 0x88, 0xF0)         # xor eax,eax; mov al,dh
    a.jmp_abs(FG_WRITE)
    # ---- ONE_OPPONENT ----
    a.label("oo")
    a.mov_ah_m(SEL)
    a.db(0x80, 0xFC, 0x13)               # cmp ah,19
    a.jcc_lbl(JNE, "oo_n19")
    a.call_lbl("rr")                     # eax = car
    a.db(0x89, 0xC3)                     # mov ebx,eax
    a.jmp_abs(OO_CONT)
    a.label("oo_n19")
    a.db(0x80, 0xFC, 0x10)               # cmp ah,16
    a.jcc_abs(JB, OO_ORIG)
    a.db(0x80, 0xFC, 0x12)               # cmp ah,18
    a.jcc_abs(JA, OO_ORIG)
    a.db(0x80, 0xEC, 0x04)               # sub ah,4
    a.db(0x31, 0xDB, 0x88, 0xE3)         # xor ebx,ebx; mov bl,ah
    a.jmp_abs(OO_CONT)
    # ---- VALID_CAR_FLAGS (called; returns flags via cmp) ----
    a.label("valid")
    a.mov_al_m(SEL)
    a.db(0x3C, 0x10)                     # cmp al,16
    a.jcc_lbl(JB, "vc_legacy")
    a.db(0x3C, 0x12, 0xC3)               # cmp al,18; ret  (16-18 direct)
    a.label("vc_legacy")
    a.db(0x3C, 0x0B, 0xC3)               # cmp al,11; ret  (0-11 direct; 12-15,19 -> class)
    # ---- NORMALIZE ----
    a.label("norm")
    a.call_lbl("valid")
    a.jcc_abs(JBE, NORM_DIRECT)          # jbe -> regular/bonus direct car
    a.jmp_abs(NORM_CLASS)                # else -> class full-grid (12-14,19)
    # ---- CAR_UI ----
    a.label("ui")
    a.db(0x50)                           # push eax
    a.mov_al_m(SEL)
    a.db(0x3C, 0x0C); a.jcc_lbl(JB, "ui_direct")   # <12 direct car
    a.db(0x3C, 0x0F); a.jcc_lbl(JBE, "ui_class")   # 12-15 class/None
    a.db(0x3C, 0x12); a.jcc_lbl(JBE, "ui_direct")  # 16-18 bonus direct car
    a.db(0x3C, 0x13); a.jcc_lbl(JE, "ui_class")    # 19 -> class
    a.label("ui_class")
    a.db(0x58); a.jmp_abs(UI_CLASS)      # pop eax; jmp class_or_none
    a.label("ui_direct")
    a.db(0x58); a.jmp_abs(UI_DIRECT)     # pop eax; jmp direct
    # ---- SETUP_STATE ----
    a.label("ss")
    a.db(0x80, 0xFF, 0x0E); a.jcc_abs(JBE, SS_OK)      # bh<=14 original valid
    a.db(0x80, 0xFF, 0x10); a.jcc_abs(JB, SS_REJECT)   # 15 None reject
    a.db(0x80, 0xFF, 0x12); a.jcc_abs(JBE, SS_OK)      # 16-18 accept
    a.db(0x80, 0xFF, 0x13); a.jcc_abs(JE, SS_OK)       # 19 Class D accept
    a.jmp_abs(SS_REJECT)
    # ---- SUMMARY ----
    a.label("sum")
    a.db(0x31, 0xC0)                     # xor eax,eax
    a.mov_al_m(SEL)
    a.db(0x3C, 0x13); a.jcc_lbl(JNE, "sum_c19")  # if ==19:
    a.db(0xB0, 0x0E)                     #   mov al,14  (Class D shown as Class C in summary)
    a.label("sum_c19")
    a.db(0x3C, 0x10); a.jcc_lbl(JB, "sum_leg")   # <16 legacy (classes/None -> icon val+4)
    a.db(0x3C, 0x12); a.jcc_lbl(JA, "sum_leg")   # >18 legacy
    a.db(0x2C, 0x04)                     # sub al,4 -> car 12-14
    a.raw(bytes.fromhex("668984249201 0000".replace(" ", "")))  # mov [esp+0x192],ax
    a.jmp_abs(SUM_MAP)
    a.label("sum_leg")
    a.jmp_abs(SUM_LEG)
    # ---- ICON_LOOKUP ----
    a.label("icon")
    a.db(0x8B, 0x04, 0x85); a.imm32(ICON_TABLE_VA)   # mov eax,[ICON_TABLE+eax*4]
    a.jmp_abs(ICON_RENDER)
    return a


def jump5(site, dst, length):
    return b"\xE9" + r32(site + 5, dst) + b"\x90" * (length - 5)


def call5(site, dst, length):
    return b"\xE8" + r32(site + 5, dst) + b"\x90" * (length - 5)


@dataclass(frozen=True)
class Hunk:
    off: int
    original: bytes
    patched: bytes


def build():
    a = build_cave()
    cave = a.finish()
    L = a.lab
    if len(cave) > CAVE_CAP:
        raise RuntimeError("cave overflow %d > %d" % (len(cave), CAVE_CAP))
    data = bytearray()
    for v in CARD_NAMES:
        data += struct.pack("<I", v)
    data += b"clsd\x00"
    data += b"\x00"                      # RR_CTR init 0
    d_str_va = DATA_VA + len(data)       # "D" class-letter string for the setup-screen gold letter
    data += b"D\x00"
    opt_orig = bytes.fromhex("7C007D007E00780000005A015A015A015A01")
    opt_new = bytes.fromhex("7C007D007E0078006C006D006E005A0100005A01")  # Class D label = text id 0x15A (single space " ", record 343) -> blank; no text-file edits
    # name-table (0x40A288) free class-letter slots 85/86/87 -> "D" so the setup-screen
    # opponent indicator builds "D5"/"Dd" for Class D (letters A/B/C are at 82/83/84)
    NAMETBL = 0x40A288 - 0x400C00
    hunks = [
        Hunk(0x5976, bytes.fromhex("8A3515014E00"), jump5(0x406576, L["fg"], 6)),
        Hunk(0x66CE, bytes.fromhex("8A2515014E00"), jump5(0x4072CE, L["oo"], 6)),
        Hunk(0xB30D, bytes.fromhex("31C0A015014E00"), jump5(0x40BF0D, L["sum"], 7)),
        Hunk(0xBF49, bytes.fromhex("803D15014E000B0F872CFDFFFF"), jump5(0x40CB49, L["ui"], 13)),
        Hunk(0xC7D3, bytes.fromhex("8B0484E8F58AFFFF"), call5(0x40D3D3, L["icon"], 8)),
        Hunk(0xD923, bytes.fromhex("80FF0E7636"), jump5(0x40E523, L["ss"], 5)),
        Hunk(0xE363, bytes.fromhex("803D15014E000B"), call5(0x40EF63, L["valid"], 7)),
        Hunk(0xE6EA, bytes.fromhex("3C0B0F86A4FCFFFF"), jump5(0x40F2EA, L["norm"], 8)),
        Hunk(0xC1330, opt_orig, opt_new),
        Hunk(CAVE_OFF, bytes(len(cave)), cave),
        Hunk(DATA_OFF, bytes(len(data)), bytes(data)),
    ]
    return hunks, cave, L


def sha(d):
    return hashlib.sha256(d).hexdigest().upper()


def verify(data, patched):
    bad = []
    for h in build()[0]:
        exp = h.patched if patched else h.original
        if bytes(data[h.off:h.off + len(exp)]) != exp:
            bad.append(hex(h.off))
    if bad:
        raise RuntimeError("unexpected bytes at " + ", ".join(bad))


def apply(path):
    data = bytearray(path.read_bytes())
    if sha(data) != ORIGINAL_SHA256:
        try:
            verify(data, True)
            return "already patched"
        except Exception:
            pass
        raise RuntimeError("exe is not the pristine nfs2sen.exe (sha %s). "
                           "Revert the bonus-cars mod first." % sha(data)[:12])
    verify(data, False)
    for h in build()[0]:
        data[h.off:h.off + len(h.patched)] = h.patched
    bak = path.with_name(path.name + ".preclassd.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return "patched (Class D + bonus cars); backup %s" % bak.name


def revert(path):
    data = bytearray(path.read_bytes())
    verify(data, True)
    for h in build()[0]:
        data[h.off:h.off + len(h.original)] = h.original
    if sha(data) != ORIGINAL_SHA256:
        raise RuntimeError("revert did not reproduce original sha")
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return "reverted to original"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("status", "apply", "revert", "selftest"))
    ap.add_argument("--game-dir", type=Path, default=GAME)
    a = ap.parse_args()
    p = a.game_dir / EXE
    if a.action == "selftest":
        hunks, cave, L = build()
        print("cave=%d/%d bytes" % (len(cave), CAVE_CAP))
        print("labels:", {k: hex(v) for k, v in L.items()})
        print("data region 0x%X..0x%X" % (DATA_VA, DATA_VA + len(build()[0][-1].patched)))
        return 0
    try:
        d = p.read_bytes()
        if a.action == "status":
            s = sha(d)
            st = "original" if s == ORIGINAL_SHA256 else "unknown"
            try:
                verify(bytearray(d), True)
                st = "class-d patched"
            except Exception:
                pass
            print("%s: %s (sha %s)" % (EXE, st, s[:12]))
        elif a.action == "apply":
            print(apply(p))
        else:
            print(revert(p))
        return 0
    except (OSError, RuntimeError) as e:
        print("ERROR:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
