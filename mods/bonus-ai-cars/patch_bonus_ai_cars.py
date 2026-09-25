#!/usr/bin/env python3
"""Add bonus cars to the nfs2sen.exe opponent picker without renumbering classes.

Original menu/protocol values remain stable:
  0-11 normal cars, 12-14 Class A/B/C, 15 None.
New values 16-18 select Bomber BFS, Tombstone, and FZR 2000.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_GAME_DIR = PROJECT_DIR / "Need For Speed II SE"
EXE_NAME = "nfs2sen.exe"
ORIGINAL_SHA256 = (
    "467B2757F65B26E22688E0568A370DB9B2C6EFA417ABB465BD250169BE57E495"
)
PATCHED_SHA256 = (
    "BE1433BF3AA70F5DB795214ECE98C617D4251F4A44EB40C9D9C496013082F585"
)

SELECTED_OPPONENT = 0x4E0115
CAVE_VA = 0x482D06
CAVE_OFFSET = 0x82106


@dataclass(frozen=True)
class Hunk:
    offset: int
    original: bytes
    patched: bytes


def rel32(source_after_instruction: int, destination: int) -> bytes:
    return struct.pack("<i", destination - source_after_instruction)


def jump_patch(site_va: int, destination: int, length: int) -> bytes:
    if length < 5:
        raise ValueError("a near jump requires at least five bytes")
    return b"\xE9" + rel32(site_va + 5, destination) + b"\x90" * (length - 5)


def call_patch(site_va: int, destination: int, length: int) -> bytes:
    if length < 5:
        raise ValueError("a near call requires at least five bytes")
    return b"\xE8" + rel32(site_va + 5, destination) + b"\x90" * (length - 5)


class CodeBuilder:
    """Tiny builder for the few x86 relative branches used by this patch."""

    def __init__(self, start_va: int) -> None:
        self.start_va = start_va
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, int, str]] = []

    @property
    def va(self) -> int:
        return self.start_va + len(self.code)

    def emit(self, data: bytes) -> None:
        self.code.extend(data)

    def label(self, name: str) -> None:
        self.labels[name] = self.va

    def jmp(self, destination: int) -> None:
        source_after = self.va + 5
        self.emit(b"\xE9" + rel32(source_after, destination))

    def jcc(self, condition_opcode: int, destination: int) -> None:
        source_after = self.va + 6
        self.emit(bytes((0x0F, condition_opcode)) + rel32(source_after, destination))

    def jmp_label(self, label: str) -> None:
        displacement_offset = len(self.code) + 1
        source_after_offset = len(self.code) + 5
        self.emit(b"\xE9\x00\x00\x00\x00")
        self.fixups.append((displacement_offset, source_after_offset, label))

    def jcc_label(self, condition_opcode: int, label: str) -> None:
        displacement_offset = len(self.code) + 2
        source_after_offset = len(self.code) + 6
        self.emit(bytes((0x0F, condition_opcode)) + b"\x00\x00\x00\x00")
        self.fixups.append((displacement_offset, source_after_offset, label))

    def finish(self) -> bytes:
        for displacement_offset, source_after_offset, label in self.fixups:
            destination = self.labels[label]
            displacement = destination - (self.start_va + source_after_offset)
            self.code[displacement_offset:displacement_offset + 4] = struct.pack(
                "<i", displacement
            )
        return bytes(self.code)


FULL_GRID_HELPER = 0x482D06
ONE_OPPONENT_HELPER = 0x482D30
VALID_CAR_FLAGS_HELPER = 0x482D60
NORMALIZE_HELPER = 0x482D80
CAR_UI_HELPER = 0x482DC0
SETUP_STATE_HELPER = 0x482DF0
SUMMARY_HELPER = 0x482E10
ICON_LOOKUP_HELPER = 0x482E50
ICON_TABLE_VA = 0x482E70


def build_full_grid_helper() -> bytes:
    code = CodeBuilder(FULL_GRID_HELPER)
    code.emit(b"\x8A\x35" + struct.pack("<I", SELECTED_OPPONENT))  # mov dh,[...]
    code.emit(b"\x80\xFE\x10")  # cmp dh,16
    code.jcc(0x82, 0x40657C)  # jb: retain original car/class/None path
    code.emit(b"\x80\xFE\x12")  # cmp dh,18
    code.jcc(0x87, 0x40657C)  # ja: let original validation reject it
    code.emit(b"\x80\xEE\x04")  # sub dh,4 -> actual car ID 12-14
    code.emit(b"\x31\xC0\x88\xF0")  # xor eax,eax; mov al,dh
    code.jmp(0x406593)  # write the mapped car directly
    return code.finish()


def build_one_opponent_helper() -> bytes:
    code = CodeBuilder(ONE_OPPONENT_HELPER)
    code.emit(b"\x8A\x25" + struct.pack("<I", SELECTED_OPPONENT))  # mov ah,[...]
    code.emit(b"\x80\xFC\x10")  # cmp ah,16
    code.jcc(0x82, 0x4072D4)  # jb: original path
    code.emit(b"\x80\xFC\x12")  # cmp ah,18
    code.jcc(0x87, 0x4072D4)  # ja: original rejection path
    code.emit(b"\x80\xEC\x04")  # sub ah,4 -> actual car ID 12-14
    code.emit(b"\x31\xDB\x88\xE3")  # xor ebx,ebx; mov bl,ah
    code.jmp(0x4064BB)  # continue with the mapped direct car
    return code.finish()


def build_valid_car_flags_helper() -> bytes:
    code = CodeBuilder(VALID_CAR_FLAGS_HELPER)
    code.emit(b"\xA0" + struct.pack("<I", SELECTED_OPPONENT))  # mov al,[...]
    code.emit(b"\x3C\x10")  # cmp al,16
    code.jcc_label(0x82, "legacy")  # jb
    code.emit(b"\x3C\x12\xC3")  # cmp al,18; ret (16-18 are valid)
    code.label("legacy")
    code.emit(b"\x3C\x0B\xC3")  # cmp al,11; ret (0-11 are valid)
    return code.finish()


def build_normalize_helper() -> bytes:
    code = CodeBuilder(NORMALIZE_HELPER)
    code.emit(b"\xE8" + rel32(code.va + 5, VALID_CAR_FLAGS_HELPER))
    code.jcc(0x86, 0x40EF96)  # jbe: regular or bonus direct car
    code.jmp(0x40F2F2)  # class selector retains original full-grid behavior
    return code.finish()


def build_car_ui_helper() -> bytes:
    code = CodeBuilder(CAR_UI_HELPER)
    code.emit(b"\x50")  # push eax
    code.emit(b"\xA0" + struct.pack("<I", SELECTED_OPPONENT))
    code.emit(b"\x3C\x0C")  # below 12: regular direct car
    code.jcc_label(0x82, "direct")
    code.emit(b"\x3C\x0F")  # 12-15: classes or None
    code.jcc_label(0x86, "class_or_none")
    code.emit(b"\x3C\x12")  # 16-18: bonus direct car
    code.jcc_label(0x86, "direct")
    code.label("class_or_none")
    code.emit(b"\x58")  # pop eax
    code.jmp(0x40C882)
    code.label("direct")
    code.emit(b"\x58")  # pop eax
    code.jmp(0x40CB56)
    return code.finish()


def build_setup_state_helper() -> bytes:
    code = CodeBuilder(SETUP_STATE_HELPER)
    code.emit(b"\x80\xFF\x0E")  # cmp bh,14: all original valid values
    code.jcc(0x86, 0x40E55E)  # jbe: original accepted path
    code.emit(b"\x80\xFF\x10")  # cmp bh,16
    code.jcc(0x82, 0x40E528)  # jb: value 15 remains original None/reject path
    code.emit(b"\x80\xFF\x12")  # cmp bh,18
    code.jcc(0x86, 0x40E55E)  # jbe: new bonus values are accepted
    code.jmp(0x40E528)  # invalid values retain original rejection behavior
    return code.finish()


def build_summary_helper() -> bytes:
    code = CodeBuilder(SUMMARY_HELPER)
    code.emit(b"\x31\xC0")  # xor eax,eax
    code.emit(b"\xA0" + struct.pack("<I", SELECTED_OPPONENT))
    code.emit(b"\x3C\x10")  # cmp al,16
    code.jcc_label(0x82, "legacy")
    code.emit(b"\x3C\x12")  # cmp al,18
    code.jcc_label(0x87, "legacy")
    code.emit(b"\x2C\x04")  # sub al,4 -> actual car ID 12-14
    code.emit(bytes.fromhex("66 89 84 24 92 01 00 00"))
    code.jmp(0x40BA3D)
    code.label("legacy")
    code.jmp(0x40BF14)
    return code.finish()


def build_icon_lookup_helper() -> bytes:
    code = CodeBuilder(ICON_LOOKUP_HELPER)
    code.emit(b"\x8B\x04\x85" + struct.pack("<I", ICON_TABLE_VA))
    code.jmp(0x405ED0)  # tail-call the original renderer
    return code.finish()


ICON_POINTERS = (
    0x4B9320, 0x4B9328, 0x4B9330, 0x4B9338,
    0x4B9340, 0x4B9348, 0x4B9350, 0x4B9358,
    0x4B9360, 0x4B9368, 0x4B9370, 0x4B9378,
    0x4B9398, 0x4B93A0, 0x4B93A8,  # original Class A/B/C values 12-14
    0,                              # original None value 15
    0x4B9380, 0x4B9388, 0x4B9390,  # bonus values 16-18
)


def build_cave() -> bytes:
    end_va = ICON_TABLE_VA + 4 * len(ICON_POINTERS)
    cave = bytearray(end_va - CAVE_VA)

    def place(va: int, payload: bytes) -> None:
        start = va - CAVE_VA
        end = start + len(payload)
        if any(cave[start:end]):
            raise RuntimeError(f"overlapping injected code at 0x{va:X}")
        cave[start:end] = payload

    place(FULL_GRID_HELPER, build_full_grid_helper())
    place(ONE_OPPONENT_HELPER, build_one_opponent_helper())
    place(VALID_CAR_FLAGS_HELPER, build_valid_car_flags_helper())
    place(NORMALIZE_HELPER, build_normalize_helper())
    place(CAR_UI_HELPER, build_car_ui_helper())
    place(SETUP_STATE_HELPER, build_setup_state_helper())
    place(SUMMARY_HELPER, build_summary_helper())
    place(ICON_LOOKUP_HELPER, build_icon_lookup_helper())
    place(
        ICON_TABLE_VA,
        b"".join(struct.pack("<I", pointer) for pointer in ICON_POINTERS),
    )
    return bytes(cave)


CAVE_BYTES = build_cave()

HUNKS = (
    # Translate new bonus menu values only at the two AI-car assignment paths.
    Hunk(
        0x5976,
        bytes.fromhex("8A 35 15 01 4E 00"),
        jump_patch(0x406576, FULL_GRID_HELPER, 6),
    ),
    Hunk(
        0x66CE,
        bytes.fromhex("8A 25 15 01 4E 00"),
        jump_patch(0x4072CE, ONE_OPPONENT_HELPER, 6),
    ),
    # Map bonus values for the opponent summary without touching class values.
    Hunk(
        0xB30D,
        bytes.fromhex("31 C0 A0 15 01 4E 00"),
        jump_patch(0x40BF0D, SUMMARY_HELPER, 7),
    ),
    # Keep car-specific UI enabled for the three bonus selections.
    Hunk(
        0xBF49,
        bytes.fromhex("80 3D 15 01 4E 00 0B 0F 87 2C FD FF FF"),
        jump_patch(0x40CB49, CAR_UI_HELPER, 13),
    ),
    # Render all 19 choices through the expanded icon table.
    Hunk(
        0xC7D3,
        bytes.fromhex("8B 04 84 E8 F5 8A FF FF"),
        call_patch(0x40D3D3, ICON_LOOKUP_HELPER, 8),
    ),
    # Accept bonus values in copied setup state while value 15 remains None.
    Hunk(
        0xD923,
        bytes.fromhex("80 FF 0E 76 36"),
        jump_patch(0x40E523, SETUP_STATE_HELPER, 5),
    ),
    # One-opponent validation accepts regular cars or bonus values, not classes.
    Hunk(
        0xE363,
        bytes.fromhex("80 3D 15 01 4E 00 0B"),
        call_patch(0x40EF63, VALID_CAR_FLAGS_HELPER, 7),
    ),
    # Bonus values no longer force the class-only full-grid behavior.
    Hunk(
        0xE6EA,
        bytes.fromhex("3C 0B 0F 86 A4 FC FF FF"),
        jump_patch(0x40F2EA, NORMALIZE_HELPER, 8),
    ),
    # Preserve original class/None IDs; append bonus IDs 16-18 and terminator.
    Hunk(
        0xC1330,
        bytes.fromhex("7C 00 7D 00 7E 00 78 00 00 00 5A 01 5A 01 5A 01"),
        bytes.fromhex("7C 00 7D 00 7E 00 78 00 6C 00 6D 00 6E 00 00 00"),
    ),
    # Previously unreferenced executable padding: helpers + expanded icon table.
    Hunk(CAVE_OFFSET, bytes(len(CAVE_BYTES)), CAVE_BYTES),
)


def sha256(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def verify_hunks(data: bytes | bytearray, patched: bool) -> None:
    mismatches = []
    for hunk in HUNKS:
        expected = hunk.patched if patched else hunk.original
        actual = bytes(data[hunk.offset:hunk.offset + len(expected)])
        if actual != expected:
            mismatches.append(f"0x{hunk.offset:X}")
    if mismatches:
        raise RuntimeError("unexpected bytes at " + ", ".join(mismatches))


def patched_copy(original: bytes | bytearray) -> bytearray:
    result = bytearray(original)
    verify_hunks(result, patched=False)
    for hunk in HUNKS:
        result[hunk.offset:hunk.offset + len(hunk.patched)] = hunk.patched
    return result


def original_copy(patched: bytes | bytearray) -> bytearray:
    result = bytearray(patched)
    verify_hunks(result, patched=True)
    for hunk in HUNKS:
        result[hunk.offset:hunk.offset + len(hunk.original)] = hunk.original
    return result


def state(data: bytes | bytearray) -> str:
    digest = sha256(data)
    if digest == ORIGINAL_SHA256:
        return "original"
    if digest == PATCHED_SHA256:
        return "patched"
    return "unknown"


def atomic_write(path: Path, data: bytes | bytearray) -> None:
    temporary = path.with_name(path.name + ".bonus-ai-cars.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def apply_patch(path: Path) -> str:
    data = path.read_bytes()
    current = state(data)
    if current == "patched":
        verify_hunks(data, patched=True)
        return "already patched"
    if current != "original":
        raise RuntimeError(f"unsupported SHA-256: {sha256(data)}")

    result = patched_copy(data)
    if sha256(result) != PATCHED_SHA256:
        raise RuntimeError("patched bytes did not produce the expected SHA-256")

    backup = path.with_name(path.name + ".bonus-ai-cars.bak")
    if backup.exists():
        if sha256(backup.read_bytes()) != ORIGINAL_SHA256:
            raise RuntimeError(f"refusing to replace unexpected backup: {backup}")
    else:
        shutil.copy2(path, backup)
    atomic_write(path, result)
    return f"patched (backup: {backup.name})"


def revert_patch(path: Path) -> str:
    data = path.read_bytes()
    current = state(data)
    if current == "original":
        verify_hunks(data, patched=False)
        return "already original"
    if current != "patched":
        raise RuntimeError(f"unsupported SHA-256: {sha256(data)}")

    result = original_copy(data)
    if sha256(result) != ORIGINAL_SHA256:
        raise RuntimeError("restored bytes did not produce the expected SHA-256")
    atomic_write(path, result)
    return "reverted"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "apply", "revert"))
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    args = parser.parse_args()
    path = args.game_dir / EXE_NAME

    try:
        if not path.is_file():
            raise RuntimeError(f"file not found: {path}")
        if args.action == "status":
            result = state(path.read_bytes())
        elif args.action == "apply":
            result = apply_patch(path)
        else:
            result = revert_patch(path)
        print(f"{EXE_NAME}: {result}")
        return 0
    except (OSError, RuntimeError) as error:
        print(f"{EXE_NAME}: ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
