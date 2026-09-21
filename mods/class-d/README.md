# Class D opponent option

Adds a new **Class D** choice to the opponent-car picker in `nfs2sen.exe`
(software renderer). Picking Class D makes each AI opponent drive one of the
three bonus cars, cycled round-robin so all three appear:

- Bomber BFS (car ID 12)
- Tombstone (car ID 13)
- FZR 2000 (car ID 14)

Class D is menu value **19**, appended after the bonus-car entries. It behaves
like a class (shows the `clsd` preview card + "class D" label; assigns a car per
opponent) rather than a single car. It does **not** touch the native A/B/C class
rosters, so a car can effectively appear in Class D and its native class at once.

This supersedes and includes the earlier `bonus-ai-cars` mod (values 16-18 still
select Bomber/Tombstone/FZR individually).

## What it changes (all reversible, all backed up)

| File | Change | Backup |
|------|--------|--------|
| `Need For Speed II SE/nfs2sen.exe` | picker entry + selection logic (code cave at VA `0x482D06`, data at `0x4D3900`) | `nfs2sen.exe.preclassd.bak` |
| `FEDATA/PC/ART/MAIN.QFS` | new `clsd` 306x146 card | `MAIN.QFS.class-d.bak` |
| `FEDATA/PC/TEXT/TEXT.ENG` | new "class D" string (record 1498) | `TEXT.ENG.class-d.bak` |

The exe patch is SHA-guarded to this project's original `nfs2sen.exe`
(`467B2757...`); patched build is `46106CF4...`. Every helper was verified by
disassembly and the revert reproduces the original byte-for-byte.

## Commands (from project root)

```powershell
python mods\class-d\install.py status     # show state of all three files
python mods\class-d\install.py apply       # install everything
python mods\class-d\install.py revert      # uninstall everything
```

Individual pieces: `patch_class_d.py` (exe), `install_mainqfs.py` (card),
`tools\text_patch.py` (label).

## How it works

The opponent picker fetches each entry's preview card from `MAIN.QFS` by 4-char
name via an in-exe pointer table indexed by menu value. The prior mod expanded
that table (values 16-18 -> `carf/care/card`); Class D adds value 19 -> `clsd`.
The picker's "extra options" list (label string IDs, VA `0x4C2F30`) gets one more
entry (`class D`, text id 1501). Selection/validation/UI helpers in the code cave
treat 19 as a class everywhere except AI car assignment, where a round-robin
counter yields car 12/13/14.

## Tools

- `tools/qfs.py` - EA RefPack (QFS) decompress + SHPI/FSH parser
- `tools/fsh_inject.py` - build + append the `clsd` card
- `tools/exe.py` - VA<->file mapping + capstone disassembly for nfs2sen.exe
- `tools/text_patch.py` - TEXT.ENG record append
