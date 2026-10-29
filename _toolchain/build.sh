#!/usr/bin/env bash
# Build NFSIISE (nfs2se.exe) with the local winlibs i686 toolchain.
# Output goes to nfs2se-modern.exe so the user's working exe is never clobbered.
set -e
TC="/c/Users/ashut/Ashutosh-ZenbookDuo2020Transfer/Documents/NFS 2 SE Online Multiplayer/_toolchain"
MINGW="$TC/mingw32"
SDL="$TC/SDL2-2.32.10/i686-w64-mingw32"
SRC="/c/Users/ashut/Ashutosh-ZenbookDuo2020Transfer/Documents/NFS 2 SE Online Multiplayer/NFSIISE-source/src"
GAMEDIR="/c/Users/ashut/Ashutosh-ZenbookDuo2020Transfer/Documents/NFS 2 SE Online Multiplayer/Need For Speed II SE"
OUT="$GAMEDIR/nfs2se-modern.exe"
export PATH="$MINGW/bin:$PATH"

CF="-Wall -m32 -std=gnu89 -O2 -mno-sse2 -mno-sse -mno-mmx"

cd "$SRC"
echo "== clean =="
rm -f *.o
echo "== windres (icon) =="
windres Windows/nfs2se.rc icon.o || { echo "windres failed (continuing without icon)"; rm -f icon.o; }
echo "== gcc compile C (*.c) =="
gcc $CF -I"$SDL/include" -c *.c
echo "== yasm assemble game (NFS2SE.asm) =="
yasm -f win32 Asm/NFS2SE.asm -o NFS2SE.Win32.o --prefix=_
echo "== link -> $OUT =="
ld --enable-stdcall-fixup -o "$OUT" -Map="$GAMEDIR/nfs2se-modern.map" *.o \
   --stack=0x7D00,0x7D00 --heap=0x2000,0x1000 \
   -L"$MINGW/i686-w64-mingw32/lib" -L"$MINGW/lib" -L"$SDL/lib" \
   -lws2_32 -lwinmm -lmingwex -lmsvcrt -lkernel32 -lopengl32 -lSDL2 \
   -subsystem=windows -s -e _start
rm -f *.o
echo "== post-build: FZR 2000 colour palette =="
python "$SRC/../../mods/fzr-colors/patch_fzr_colors.py" apply --exe "$OUT" || echo "WARN: fzr-colours patch failed"
echo "== post-build: tyre particle effects (smoke/dust/snow) =="
# The freshly-linked exe IS the baseline, so drop any stale cross-build .partbak first --
# otherwise patch_particles.py would restore the old backup over this build (clobbering the
# newly-assembled asm) before applying the particle bytes.
rm -f "$OUT.partbak"
python "$SRC/../../mods/particles/patch_particles.py" apply --exe "$OUT" || echo "WARN: particles patch failed"
echo "== DONE: $(stat -c %s "$OUT" 2>/dev/null) bytes =="
