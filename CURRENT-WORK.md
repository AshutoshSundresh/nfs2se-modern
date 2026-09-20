# NFS II SE — Reverse Engineering & Binary Patching (Work Log / Resume Source)

Solo reverse-engineering and binary-modding of **Need For Speed II SE** (1997), a 32-bit
x86 PE software-renderer game (`nfs2sen.exe`, imagebase `0x400000`) plus its SDL2 render
shim (`DDNFS.dll`). Static disassembly + live debugging, no source, no symbols.

> Format note: bullets are written as extractable resume lines — each leads with a verb and
> packs the technology / technique / tool / concrete result.

---

## Technologies, tools & techniques demonstrated (tag index for resume mining)

- **Reverse engineering:** x86 (IA-32) disassembly, static + dynamic analysis, control-flow
  and data-flow tracing, calling-convention/register analysis, function/xref discovery.
- **Binary instrumentation:** in-place opcode patching, **trampoline hooks via code caves**,
  jump-relocation (`E9 rel32`) with NOP padding, immediate/branch flipping, table relocation
  + pointer repointing, register-clamp injection.
- **PE / executable internals:** PE section table parsing (`AUTO`/`.idata`/`DGROUP`/`.bss`),
  RVA↔file-offset mapping, zero-init `.bss` vs file-backed data, import-table inspection.
- **Dynamic analysis:** **Cheat Engine** — unknown-initial-value & exact/increased/decreased
  scans, "find out what writes/accesses this address," access-violation triage via **Windows
  Event Viewer fault offsets** (`0xC0000005`), byte/word/dword typing of live state.
- **Tooling built:** Python + **Capstone** disassembly harnesses; custom VA↔file mappers;
  automated code-cave finders (zero-run scanners); parameterized, reversible patch scripts
  with pre-write verification and backup/restore.
- **File formats parsed:** EA **BIGF/VIV** archive (`CARDATA.VIV`, 127 entries), **QFS**
  (RefPack-compressed) + **FSH** textures, EA **GEO** geometry, `.DES`/`.DAT`/`.QDA`
  described-data schema pairs, `.BNK` audio banks, EA front-end text tables.
- **Graphics / systems:** software rasterization pipeline (8-bit palettized framebuffer →
  palette→RGB blit → **SDL2** `SDL_CreateTexture`/`SDL_RenderCopy` upscale), DirectDraw
  surface/DDSURFACEDESC vtable layout, `ChangeDisplaySettingsEx`/`MoveWindow`/DPI-awareness,
  **16.16 fixed-point** math.
- **Concepts:** "described-data" runtime-schema engine, dual-purpose state (cursor vs index),
  null-terminated table iteration, fixed-size pool/array bounds, buffer-overflow root-cause.

---

## Environment / target facts (reference)

- `nfs2sen.exe` sections: `AUTO` (code, RVA `0x1000` / raw `0x400`), `.idata` (RVA `0xB7000`),
  `DGROUP` (data, RVA `0xB9000`), `.bss` (VA `0x4D4000–0x54A000`, runtime-only, zero-init),
  `.reloc`. Derived code shortcut: `file_off = VA − 0x400C00`.
- Render path: game rasterizes an 8-bit palettized buffer → `DDNFS.dll` (~15 KB MinGW/GCC
  **SDL2** shim, preferred base `0x689C0000`) does palette→RGB copy into an SDL texture and
  upscales. **Not `ddraw.dll`/dxwrapper** (all dxwrapper edits proven inert).
- "Described-data" engine: gameplay fields resolved via runtime schema offsets, not fixed
  code addresses — the recurring wall for AI/skill/car-data patching.

---

## September 21

### Bonus AI opponents / "Class D" class
- Reverse-engineered the front-end car/opponent tables to expose the 3 hidden SE bonus cars
  (**Bomber BFS=12, Tombstone=13, FZR 2000=14**) as selectable AI opponents ("Class D").
- Root-caused and killed a UI crash by **repointing a label to text id `0x15A`** and blanking
  it; patched EA text tables (`TEXT.ENG`/`TEXT.MET`) and front-end art (`MAIN.QFS`); kept
  reversible byte-exact backups.

### AI behavior decode (`PRSONAL.DAT`/`.DES`)
- Decoded the AI **personality + grid-assignment** binary: first 48 bytes = **four 12-slot
  grid tables** (1 ASCII personality letter per slot) for KnockOut/Tournament/Single-One
  (`m*12`)/Single-Multi; personalities **A–M** with per-car glue curves.
- **Root-caused the "AI pussyfoots" bug**: the per-personality **Speed Factor** table is
  `1.0` (`0x00010000`) for every car — opponents differ only in "glue" (positioning), never
  top speed — explaining why the player can trivially out-run the field.

### Aggressive round-robin opponent grid (shipped)
- Wrote a reversible byte-patcher (`patch_grid_rr.py`) remapping personalities **d e f g h →
  a b c a b** across the 3 multi-car grid tables (48-byte region only, parameter block
  preserved) → field runs only the 3 aggressive profiles (`a b c a b c a b i j k l`).

### Draw distance ×5 (shipped)
- Located and multiplied 16.16 view-distance immediates in code; e.g. VA `0x434F6B`/`0x434FD8`
  `0x1B80000 → 0x8980000` (exact ×5). **Isolated a rendering regression** (splotching /
  stretched near-geometry / lost lane markings from ×40 LOD-cull scaling) and pinned it to the
  334/338 LOD immediates — left those at stock, shipping a clean ×5 draw distance.

### Renderer identification
- Traced imports + the palette→RGB copy loop to prove **`DDNFS.dll` (SDL2) is the real
  renderer**, not `ddraw.dll` — invalidating multiple inert `dxwrapper.ini` approaches.
- Mapped DirectDraw surface internals: vtable `+0x58` GetSurfaceDesc / `+0x64` Lock;
  DDSURFACEDESC `+0x08 dwHeight / +0x0C dwWidth / +0x10 lPitch / +0x24 lpSurface`; DDNFS Lock
  `0x689C1BC0`; surface obj `+0xA4` texture / `+0xA8` 8-bit buffer / `+0xAC` palette.

### Native-resolution fullscreen + crisp scaling (shipped)
- Patched 4 hardcoded 640/480 immediates in `DDNFS.dll` (DEVMODE `dmPelsWidth/Height`,
  `MoveWindow` w/h at `0x689C186B/1876/18D9/18D1`) → **2880×1800** native fill.
- Set the **HIGHDPIAWARE** PE-compat flag to defeat Windows 200% DPI blur; drove SDL linear
  filtering via `SDL_RENDER_SCALE_QUALITY=1` (launcher `.bat`), since the shim reads env-vars
  (no `SDL_SetHint`).

### Internal render-res 1024×768 (attempted → root-caused → reverted)
- Forced the resolution setup (`0x47E6D0`) down its `-1→1024/768` path by NOPing 2 branches
  (`0x47E72B/0x47E737`) writing render-dim globals `0x51D384/0x51D388`; patched **12 values in
  `DDNFS.dll`** (`SDL_CreateTexture` ×2, 8-bit buffer malloc `0x4B000`, palette→RGB copy count,
  **both template DDSURFACEDESCs** incl. `lPitch`).
- **Diagnosed the failure precisely**: the 3D rasterizer carries its own stride independent of
  the surface pitch, **and the entire 2D UI is hardcoded to 640×480 coordinates** (renders as a
  top-left box) — a clean fix requires rebuilding the UI coordinate system. Reverted.

### "Settings…" car-setup screen — analyzed
- Identified the grayed picker button as the **Sim-only car-tuning screen** (steering
  sensitivity, front/rear downforce, brake bias, gear ratios); read the style enum
  (`kSimStyle=0`, `kArcadeStyle=2`) and the **`carClass` bitmask** (Human=1/AI=2/Traffic=4/
  Cop=8) directly from the exe.

### Traffic + full grid — root-caused as infeasible (reverted)
- Established the shared `numCars` budget (engine array sized 16 per the symbol default) and
  that the **front-end menu is authoritative over `DEFAULT.TXT` at race start**, with car-setup
  fields carrying **zero static code xrefs** (described-data) — no clean patch point.

---

## September 22

### Roster / car-data mapping
- Located the **roster table** (`0x4C5FE0`, 8-byte model-code slots: 15 playable then traffic)
  and the **hardcoded "15 playable" gate** (`cmp reg,0xF`, e.g. `0x43E35E`) — shown to be an
  inlined literal duplicated across ~200 indistinguishable sites (no single count variable).
- Inventoried the full per-car asset pipeline: `.QFS` textures, `.GEO` geometry inside the EA
  **BIGF** archive `CARDATA.VIV` (127 files), `P*.DAT/.DES/.QDA` physics, `.BNK` audio,
  front-end art, name text id, roster slot.
- Parsed a 3rd-party add-on car (Porsche 911 GT1, CarEditor 0.52) and confirmed the community
  install method is **slot replacement** (from its own `install.txt`), not addition.

### Additive 16th car slot — deep RE marathon (drivable slot achieved)

**Cursor + picker-count crack (via Cheat Engine + static confirm)**
- Identified the live car-select cursor as **byte `0x4E00DF`** (mirrored to `0x4D4928` at
  `0x40D178`) using CE unknown-value/exact-value scans + "find what writes."
- Reverse-engineered the picker as **null-terminated table iteration** (not modulo): index
  step reads `word[table + idx*2]`, `0x0000` = end-of-list. Bonus table `0x4C2D10` = 15
  entries + terminator; widget list-pointer loaded at `0x40F37E`.
- **Relocated** the packed 15-entry table into a DGROUP code-cave (`0x4C51D1`) as a 16-entry
  table and repointed `0x40F37E` → produced a genuine, cycle-able **16th picker slot** on a
  roster hardcoded to 15.
- Caught + fixed a self-inflicted **array-overflow corruption**: an init-loop bound bump
  (`cmp eax,0xF@0x4091FA → 0x10`) overran two 15-wide arrays into state bytes
  `0x4E00F0`/`0x4E010B`, corrupting *all* cars — removed after root-causing a "normal car
  crashes too" report.

**Data-subsystem analysis + register-clamp instrumentation**
- Proved via CE that the live index has **only 3 homes** (`0x4E00DF` cursor, `0x4D4928`,
  `0x4D493A`) but is re-read **raw at 41 static sites** across display + race, each indexing a
  15-entry structure → slot-15 reads garbage (no choke point; index is **dual-purpose**:
  cursor must be 15, data needs ≤14).
- Built a family of **trampoline "index-clamp" hooks** (`if idx≥15 → 0`) via auto-allocated
  code caves (`0x439801/0x426F85/0x46BA1F/0x482E56/0x401007`), each fixing one subsystem:
  - model preview (mirror write `0x40D173`),
  - **color picker + car logo** (batch of 8 display reads),
  - **race load — made a full race run** (index stores `0x407708/0x407739` in the tagged
    info/command builder `0x4076E0`),
  - file-code lookup path (`0x4158D0` → tables `0x414C68`/`0x4B9C20`), plus commit-clamp
    candidates (`0x40E883/0x41272A/0x42613D`).
- Mapped supporting structures: `RegisterCar`=`0x441230`, car-list builder=`0x43DBD0` (from
  car-select init `0x45F491`), reg counters (`0x4DF19C`…) zeroed by `0x4414A0`, the per-car
  **object array** (`0x684`-byte blocks, indexed `base + type*0x684` at 20+ sites), the
  race-property table (`[0x4CE388]→0x49D8A1→[0x544FD0]`, an in-exe pointer, not the closed
  `eacnfs.dll`), and the carousel-redraw loop (`0x40BFE5`).

**Result**
- ✅ Delivered a **selectable AND drivable additive 16th car** — cycles in the picker, renders
  a car (body/color/logo) and **completes a full race** — exceeding the engine's documented
  fixed-15 roster.
- ❌ Honestly scoped the remainder as blocked: car name ("none"), carousel respawn/lag, and a
  **post-race string-buffer overflow** all read slot-15's data through the runtime
  **described-data object layer** (no static allocation, no choke point, unalignable data
  xrefs) — a full per-car data-model rebuild, not a patch.

### Nuke / restore (current state)
- Cleanly reverted **all additive patches** and verified restoration (every hook site stock,
  every code-cave zeroed, picker pointer + roster restored, config + `CARDATA.VIV` stock);
  removed additive scripts/backups.
- **Retained shipped mods:** draw distance ×5, native-res fullscreen + smooth scaling,
  aggressive round-robin AI grid, Class D bonus-AI edits.

---

## Quantified highlights (for resume bullets)
- Reverse-engineered a **1997 32-bit x86 PE** software renderer + its **SDL2** shim with **zero
  source/symbols**, using Capstone-based static disassembly and Cheat Engine dynamic analysis.
- Authored **10+ reversible, self-verifying binary patch scripts** (immediate flips, branch
  NOPs, table relocation, and trampoline code-cave hooks).
- Shipped 4 working mods (5× draw distance; 2880×1800 native fullscreen + crisp SDL scaling;
  aggressive AI grid; bonus-car opponents), each byte-exact reversible.
- Cracked a **hardcoded 15-car roster limit** to produce a **selectable, drivable additive
  16th car** by relocating a null-terminated table + injecting index-clamp trampolines.
- Root-caused multiple failures precisely (framebuffer stride vs UI coordinate system;
  Speed-Factor-pinned AI; `.bss` array overflow; described-data runtime schema) — scoping each
  as fixable-vs-architecturally-blocked.
