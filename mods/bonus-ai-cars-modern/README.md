# Bonus opponent cars — modern (Glide) build

Ports the retail `mods/bonus-ai-cars/patch_bonus_ai_cars.py` feature (pick the 3
bonus cars — Bomber BFS / Tombstone / FZR 2000 — as opponents) to
`nfs2se-modern.exe`.

## Why this is a source edit, not a byte patch

The retail patch targets `nfs2sen.exe` (the 1997 **software** renderer). The
modern exe is built from `NFSIISE-source/src/Asm/NFS2SE.asm`, a disassembly of
the **3dfx/Glide** build — a *different* binary. Verified: none of the retail
patch's absolute addresses (`SELECTED_OPPONENT 0x4E0115`, code sites, cave
`0x482D06`, picker table `0x4C1330`, icon table `0x4B93xx`) exist at the same
places in the modern exe, and the modern exe relocates under ASLR (`.reloc`).
So the feature is **re-implemented** against the Glide build's own structures
and the game is rebuilt.

## Glide-build equivalents (found by RE)

| role | retail global/site | Glide equivalent |
|---|---|---|
| selection (live/display) | `0x4E0115` | `byte_512DF5` (widget `off_4D3204`) |
| selection (stored config) | — | `byte_512F42` |
| picker string list | table `0x4C1330` | `dword_4D3138` (terminator-scanned) |

Value convention is shared for protocol compat: `0-11` cars, `12-14` class
A/B/C, `15` None, **`16-18` bonus** → mapped to car ids `12/13/14`.

## Edits applied to `NFS2SE.asm` (backup: `NFS2SE.asm.bonusbak`)

1. **`dword_4D3138`** — append car-name IDs `6Ch/6Dh/6Eh` at list indices
   16-18, move the `0` terminator to index 19 (mirrors the retail table edit).
   This is what surfaces the 3 bonus entries in the picker.
2. **`loc_406209`** (full-grid assign, reads `dh`) — values 16-18 → `eax=val-4`
   → `loc_406243` (place car 12-14 directly).
3. **`loc_406F9C`** (one-opponent assign, reads `ah`) — 16-18 → `ah-4` direct car.
4. **`loc_40C851`** (car-specific UI gate) — 16-18 use the direct-car UI path
   (`loc_40C866`).
5. **`loc_40E39D`** (`sub_40E370`, derive live from stored) — accept stored
   16-18 as mode-2 direct cars via `loc_40E3F8`.
6. **`loc_40BB7D`** (race summary index) — 16-18 summarize as mapped car 12-14.

All injected labels are prefixed `bonus_`.

## AI driving

The bonus cars drive well because `mods/ai-bonus-cars/swap_ai_cardata.py` was
already applied — it edits shared `GAMEDATA/Sim/CarData` that **both** exes
read, so no porting was needed for that half.

## Revert

```
cp "NFSIISE-source/src/Asm/NFS2SE.asm.bonusbak" "NFSIISE-source/src/Asm/NFS2SE.asm"
bash _toolchain/build.sh
```

## Open items (pending in-game test)

- Confirm the 3 bonus entries are reachable in the opponent spinner (expected:
  after "None"), and that racing one spawns the correct car.
- Watch for a crash when a bonus value is highlighted in the picker: the picker
  render at `512DF5` read-site ~L16106 does `mov eax,[esp+eax*4]` (array indexed
  by the value). If that local array is sized 0-15, selecting 16-18 reads OOB.
  If it crashes there, extend that array's build loop. (Unverified; test first.)
- Bonus cars may need to be unlocked in the save profile to be selectable.
