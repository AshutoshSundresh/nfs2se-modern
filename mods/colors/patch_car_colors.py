"""Give the FZR 2000 (FUTR) all of the Ferrari F50 (FF50) colors, and the Tombstone
(DAYT) all of the Jaguar XJ220 (JAGR) colors.

Car colors in NFS2SE = a global 24-entry HSV base palette (CARHSVT.SJH) plus a per-car
per-color HSV delta table (DELTA.SJH: 29 cars x 12 colors x 16 bytes, ordered by carType),
and a per-car color COUNT (int32 table at exe VA 0x4C56E4, indexed by carType) that limits
how many colors the car offers. Bonus cars ship with count=1 (FUTR, DAYT), which is why
they had almost no colors.

Two edits, both same-size / in-place (no structural change, fully reversible):
  1) EXE 0x4C56E4[dst] = 0x4C56E4[src]     -- copy the color count
  2) DELTA.SJH block[dst] = block[src]     -- copy the 192-byte color-delta block
So FUTR adopts FF50's count+deltas and DAYT adopts JAGR's -> same colors as those cars.

    python patch_car_colors.py apply | revert | status
"""
import struct, sys, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "Need For Speed II SE"
EXE  = ROOT / "nfs2sen.exe";                       EXE_BAK = EXE.with_suffix(".exe.colorbak")
DELTA= ROOT / "GAMEDATA/CarModel/pc/DELTA.SJH";    DEL_BAK = DELTA.with_suffix(".SJH.colorbak")

IMG=0x400000
SEC=[("AUTO",0x1000,0xb5e00,0x400),(".idata",0xb7000,0x1200,0xb6200),("DGROUP",0xb9000,0x1ae00,0xb7400)]
def v2f(v):
    r=v-IMG
    for _,rva,rs,raw in SEC:
        if rva<=r<rva+rs: return raw+(r-rva)
    raise SystemExit("no section for 0x%x"%v)

COUNT_TBL=0x4c56e4        # int32[16], per-carType color count
BLOCK=192                 # DELTA.SJH per-car block (12 colors * 16 bytes)
# carType indices
MCF1,FF50,F355,GT90,IDGO,MACH,JAGR,LGT1,ESPR,NAZC,CALA,ISDE,CHEV,DAYT,FUTR = range(15)
# (dst car, src car): FZR<-F50, Tombstone<-Jaguar
COPIES=[(FUTR,FF50,"FZR 2000 <- Ferrari F50"),(DAYT,JAGR,"Tombstone <- Jaguar XJ220")]

def _count(d,i): return struct.unpack("<i", d[v2f(COUNT_TBL)+4*i:v2f(COUNT_TBL)+4*i+4])[0]

def apply():
    if not EXE_BAK.exists(): shutil.copyfile(EXE,EXE_BAK)
    if not DEL_BAK.exists(): shutil.copyfile(DELTA,DEL_BAK)
    d=bytearray(EXE.read_bytes()); dl=bytearray(DELTA.read_bytes())
    for dst,src,desc in COPIES:
        # 1) color count
        fo=v2f(COUNT_TBL)
        d[fo+4*dst:fo+4*dst+4]=d[fo+4*src:fo+4*src+4]
        # 2) delta block
        dl[dst*BLOCK:(dst+1)*BLOCK]=dl[src*BLOCK:(src+1)*BLOCK]
    EXE.write_bytes(d); DELTA.write_bytes(dl)
    print("applied color copies:")
    for _,_,desc in COPIES: print("  "+desc)
    status()

def revert():
    ok=False
    if EXE_BAK.exists(): shutil.copyfile(EXE_BAK,EXE); ok=True
    if DEL_BAK.exists(): shutil.copyfile(DEL_BAK,DELTA); ok=True
    print("reverted from backups" if ok else "no backups found");
    if ok: status()

def status():
    d=EXE.read_bytes(); dl=DELTA.read_bytes()
    names={MCF1:"MCF1",FF50:"FF50",JAGR:"JAGR",DAYT:"DAYT",FUTR:"FUTR"}
    for i in sorted(names):
        blk=dl[i*BLOCK:(i+1)*BLOCK]
        print("  carType %2d %-5s  colorCount=%2d  deltaBlock[0:8]=%s"%(i,names[i],_count(d,i),blk[:8].hex()))

if __name__=="__main__":
    {"apply":apply,"revert":revert,"status":status}.get(sys.argv[1] if len(sys.argv)>1 else "status",status)()
