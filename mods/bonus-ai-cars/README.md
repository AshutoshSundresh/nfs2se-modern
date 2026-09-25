# Bonus cars for opponent AI

This experiment expands the `nfs2sen.exe` opponent-car picker with all three
bonus cars while retaining the original class and None choices:

- Bomber BFS (car ID 12)
- Tombstone (car ID 13)
- FZR 2000 (car ID 14)

The resulting order is 12 normal cars, Class A, Class B, Class C, None, and the
three bonus cars. The original class and None values are deliberately preserved
for saved settings, tournament/knockout state, and multiplayer synchronization:

- `12`, `13`, `14`: Class A, Class B, Class C (unchanged)
- `15`: None (unchanged)
- `16`, `17`, `18`: Bomber BFS, Tombstone, FZR 2000 (new)

Only the new values are translated to car IDs at AI spawning and rendering
boundaries. The expanded icon table lives in previously unused executable
padding.

The patch is version-locked to this project's original software-rendered
`nfs2sen.exe`. Other executables are not modified.

## Commands

Run these from the project root:

```powershell
python mods\bonus-ai-cars\patch_bonus_ai_cars.py status
python mods\bonus-ai-cars\patch_bonus_ai_cars.py apply
python mods\bonus-ai-cars\patch_bonus_ai_cars.py revert
```

`apply` verifies the complete SHA-256 and every expected patch region before
writing. It also creates an adjacent `*.bonus-ai-cars.bak` backup. Running
`apply` or `revert` repeatedly is safe.

The bonus cars still need to be unlocked in the current game profile before
they appear in the menu.

For multiplayer bonus-car selection, every participating game should use the
same patch. Unpatched peers do not understand the new values `16`-`18`; the
original class and None values remain compatible.
