"""Give the tank-occupied traffic carTypes the semi's physics -- IN PLACE.

Traffic physics = ptr%02d.DAT in CARDATA.VIV, keyed by carType (verified at exe
0x43e5b4: carType 15-36 -> sprintf "ptr%02d"). Files exist only for 18..36. The semi
is carType 21 -> PTR21.DAT (356 B, heavy). Every PTR*.DAT is 356 B, so we copy PTR21's
bytes over each DST carType's PTR file directly in the archive: no member added, no
reorder, no offset/ordinal change (the described-data engine indexes VIV members by
position -- structural edits corrupt traffic loading, as a mid-insert rebuild proved).

Result: tanks that spawn as carTypes 18..23 load semi-weight physics. carTypes 16/17
have no PTR file (default light physics) and are left as-is. The real semi (PTR21) and
all other members are byte-identical to stock except the copied DST regions.

    python ptr_semi_swap.py apply | revert | status
"""
import struct, sys, shutil
from pathlib import Path

VIV = Path("GAMEDATA/Sim/CarData/CARDATA.VIV")
BAK = VIV.with_suffix(".VIV.tankbak")     # pristine stock (shared with add_ptr17)
SRC = "PTR20.DAT"                          # SCHOOL BUS physics (mass field[0]=6000, heaviest)
DST = ["PTR18.DAT","PTR19.DAT","PTR21.DAT","PTR22.DAT","PTR23.DAT"]  # tank slots w/ real PTR (20 is the source)

def _toc(raw):
    c=struct.unpack(">I",raw[8:12])[0]; off=16; d={}
    for _ in range(c):
        o,s=struct.unpack(">II",raw[off:off+8]); off+=8
        e=raw.index(b"\0",off); d[raw[off:e].decode("latin1").upper()]=(o,s); off=e+1
    return d

def apply():
    if not BAK.exists(): shutil.copyfile(VIV, BAK)
    raw = bytearray(BAK.read_bytes())          # build from pristine stock
    t=_toc(raw)
    so,ss=t[SRC]; assert ss==356,(SRC,ss)
    src=raw[so:so+ss]
    for name in DST:
        do,ds=t[name]; assert ds==356,(name,ds)
        raw[do:do+ds]=src
    VIV.write_bytes(raw)
    print("copied %s -> %s in place (356 B each); VIV len %d unchanged"%(SRC,DST,len(raw)))
    status()

def revert():
    if BAK.exists(): shutil.copyfile(BAK,VIV); print("CARDATA.VIV restored from stock backup")
    else: print("no backup")

def status():
    raw=VIV.read_bytes(); t=_toc(raw); so,ss=t[SRC]; src=raw[so:so+ss]
    for name in DST:
        do,ds=t[name]
        print("  %-10s == %s bytes: %s"%(name,SRC, raw[do:do+ds]==src))

if __name__=="__main__":
    {"apply":apply,"revert":revert,"status":status}.get(sys.argv[1] if len(sys.argv)>1 else "status",status)()
