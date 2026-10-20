"""Force NFS2SE debug mode ON so the built-in debug camera activates.

Debug mode is a boolean at [0x4E00F1]. It is only ever ZEROED (at the state-init
site 0x4091B9: `mov [0x4e00f1], dh`, dh=0) and then read by ~6 gates that enable the
debug free-camera handler (0x40CE50) on its screen contexts. Nothing sets it to 1 in
the retail build, so it's always off (Space just brakes).

This installs a trampoline at 0x4091B9 that sets [0x4E00F1]=1 instead of 0, then
continues the rest of the init normally (the other vars still get zeroed at 0x4091BF+).

  6-byte hook @0x4091B9:  E9 <rel32 -> cave>  90
  cave:  C6 05 F1 00 4E 00 01   (mov byte [0x4e00f1],1)
         E9 <rel32 -> 0x4091BF> (jmp back, resuming the init)

Reversible: revert restores the original 6 bytes and zeroes the cave.

    python patch_debugcam.py apply | revert | status
"""
import struct, sys, shutil
from pathlib import Path

EXE = Path("nfs2sen.exe"); BAK = EXE.with_suffix(".exe.dbgbak")
IMG=0x400000
SEC=[("AUTO",0x1000,0xb5e00,0x400),(".idata",0xb7000,0x1200,0xb6200),("DGROUP",0xb9000,0x1ae00,0xb7400)]
def v2f(v):
    r=v-IMG
    for _,rva,rs,raw in SEC:
        if rva<=r<rva+rs: return raw+(r-rva)
    raise SystemExit("no sec 0x%x"%v)
def f2v(fo):
    for _,rva,rs,raw in SEC:
        if raw<=fo<raw+rs: return IMG+rva+(fo-raw)

HOOK=0x4091b9
ORIG=bytes.fromhex("8835f1004e00")   # mov [0x4e00f1],dh
RESUME=0x4091bf                        # continue init here (zeroes the other vars)
FLAG=0x4e00f1

def find_cave(d, need=16):
    auto0,autosz=0x400,0xb5e00
    run=0; start=0
    for p in range(auto0,auto0+autosz):
        if d[p]==0:
            if run==0: start=p
            run+=1
            if run>=need+2: return start   # a couple bytes margin
        else: run=0
    raise SystemExit("no cave")

def apply():
    if not BAK.exists(): shutil.copyfile(EXE,BAK)
    d=bytearray(BAK.read_bytes())          # from pristine
    fo=v2f(HOOK)
    assert bytes(d[fo:fo+6])==ORIG, "unexpected bytes: %s"%d[fo:fo+6].hex()
    cave_fo=find_cave(d,16); cave_va=f2v(cave_fo)
    # cave body
    cave =bytes.fromhex("c605")+struct.pack("<I",FLAG)+b"\x01"   # mov byte[FLAG],1  (7)
    back = RESUME-(cave_va+len(cave)+5)
    cave+=b"\xe9"+struct.pack("<i",back)                          # jmp back (5)
    d[cave_fo:cave_fo+len(cave)]=cave
    # hook: jmp cave + nop
    rel=cave_va-(HOOK+5)
    d[fo:fo+6]=b"\xe9"+struct.pack("<i",rel)+b"\x90"
    EXE.write_bytes(d)
    print("debug mode forced ON.")
    print("  hook @0x%x -> cave @0x%x (sets [0x%x]=1, resumes 0x%x)"%(HOOK,cave_va,FLAG,RESUME))

def revert():
    if BAK.exists(): shutil.copyfile(BAK,EXE); print("reverted debug-cam patch (exe restored)")
    else: print("no backup")

def status():
    d=EXE.read_bytes(); fo=v2f(HOOK)
    cur=bytes(d[fo:fo+6])
    print("hook site 0x%x:"%HOOK, cur.hex(), "(patched)" if cur[0]==0xe9 else "(stock)")

if __name__=="__main__":
    {"apply":apply,"revert":revert,"status":status}.get(sys.argv[1] if len(sys.argv)>1 else "status",status)()
