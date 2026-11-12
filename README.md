# Need For Speed II SE mods

Reverse-engineered mods for *Need For Speed II SE* (1997), a 32-bit x86 PE game
(imagebase `0x400000`). Three targets:

- **retail** `nfs2sen.exe`: the software-renderer exe (run on modern Windows through the
  `DDNFS.dll` DDraw-to-SDL2 shim), patched directly.
- **modern** `nfs2se-modern.exe`: rebuilt from the [NFSIISE](https://github.com/zaps166/NFSIISE)
  source port (OpenGL + SDL2), then patched post-build.
- **game data**: shared `GAMEDATA` files (`CARDATA.VIV`, `MAIN.QFS`) used by both exes.

`CURRENT-WORK.md` is the full RE log.

## Layout

```
mods/                     one directory per mod (Python byte-patchers + assets)
_toolchain/build.sh       builds nfs2se-modern.exe and applies the post-build patches
NFSIISE-source/src/
    mclaren_palette.c     relocated 144-entry car-colour palette (compiled into the build)
    Asm/NFS2SE.asm        reassembled game code (carries the opponent-picker edits)
```

Not tracked (external, see `.gitignore`): the game install, the `_toolchain`
compiler/SDL drop, the NFSIISE upstream tree, and build output (`*.exe`, `*.map`).

## Build

```
bash _toolchain/build.sh
```

Compiles `src/*.c`, assembles `NFS2SE.asm`, links `nfs2se-modern.exe`, then runs the
post-build patchers (particles, then McLaren colours). Each patcher is idempotent on a
fresh link and reversible via its own `.bak`.

## Mods

| Mod | Target | Effect |
|-----|--------|--------|
| `mclaren-colors` | modern exe | Car-colour system: relocates the HSV palette to read-only `.rdata`, expands it to 144 slots, and recolours the McLaren F1 (35), Ferrari F50 (5), Ferrari F355 (20), Mustang Mach III (2); forces the Ford GT90 to one colour; points the FZR 2000 at the Isdera palette. |
| `bonus-ai-cars` / `-modern` | retail exe / modern | Let the opponent picker field the three bonus cars. |
| `ai` | game data | Round-robin the mid/back grid AI personalities into the top three. |
| `ai-bonus-cars` | game data | Fix AI driving of the FZR 2000, Tombstone and Bomber by swapping their AI blobs in `CARDATA.VIV` for physics-matched donors (McLaren, Lotus GT1, GT90). |
| `class-d` | retail exe + game data | Add a Class D opponent tier (picker entry + card/label art in `MAIN.QFS`). |
| `particles` | modern exe | Denser tyre smoke / dust / snow. |
| `tank` | retail exe + game data | Give the traffic tank the semi's heavy physics. |
| `hi-res` | DDNFS shim | Render the DDraw-to-SDL2 shim (`DDNFS.dll`) at native resolution. |
| `draw-distance` | retail exe | Extend view distance; drop LOD/cull popping. |
| `debug-cam` | retail exe | Force debug mode for the built-in free camera. |
| `textures` | tool | FSH texture unpack/repack. |
| `colors` | retail exe | Recolour bonus cars from existing in-game palettes. |

Run a mod standalone with `python mods/<mod>/<script>.py apply --exe <path>`
(`revert` / `status` where supported).

## The car-colour system

The engine keys a car's paint by a byte slot index shared across several 89-entry
tables: the HSV palette (`0x4AF473`, one bounds-free accessor at `0x45980A`), a per-car
`{base,count}` table (`0x4ADD2F`), and a packed-RGBA minimap table. Pushing a car past
slot 88 means expanding every slot-keyed table in lockstep. The palette and minimap
table are relocated to larger arrays; the minimap builder's loop bound, a signed `imm8`
capped at 127, is widened past 144 with a `.text` trampoline. See
`mods/mclaren-colors/patch_mclaren_colors.py`.
