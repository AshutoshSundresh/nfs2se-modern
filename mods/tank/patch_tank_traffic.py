"""Wire the unused TANK.geo model in as civilian traffic (mixed pool).

Roster table (VA 0x4C5FE0, 8-byte model-code slots): 0-14 = playable cars.
The moving-traffic pool the game spawns from is the civilian block, roster 16-23:

    16 OPP  17 TRAF  18 CITR  19 COMC  20 SBUS  21 SEMI  22 VANA  23 QUAT

Confirmed in-game: clamping all of 16-23 to TANK made every traffic car a tank.
Each slot overwritten with TANK removes that stock civilian model, so to keep the
normal traffic variety we only convert a FEW slots. apply() first restores the whole
roster from the stock backup, then rewrites just TANK_SLOTS -> 'TANK'.

PHYSICS: traffic mass/handling comes from PTR<N>.DAT in CARDATA.VIV, keyed by carType
NUMBER (PTR18..PTR36), not by model code. So a slot's physics is whatever PTR<slot>
holds, regardless of which model sits there. Slot 21 = PTR21 = the SEMI's heavy tune.
Putting TANK at slot 21 therefore gives the tank the semi's exact physics for free --
heavy enough to crash into -- at the cost of the semi truck no longer spawning.
(Slots 16/17 have no PTR file -> default featherweight physics; that's why the tank
felt too light at slot 17.)

Tune the mix by editing TANK_SLOTS (any subset of 16..36); each slot inherits its
PTR<slot> physics. TANK.geo (CARDATA.VIV) + TANK.QFS (loose) already ship.

    python patch_tank_traffic.py apply | revert | status
"""
import sys, shutil
from pathlib import Path

EXE = Path("nfs2sen.exe"); BAK = EXE.with_suffix(".exe.tankbak")
IMGBASE = 0x400000
SEC = [("AUTO",0x1000,0xb5e00,0x400),(".idata",0xb7000,0x1200,0xb6200),("DGROUP",0xb9000,0x1ae00,0xb7400)]
def v2f(v):
    r=v-IMGBASE
    for _,rva,rs,raw in SEC:
        if rva<=r<rva+rs: return raw+(r-rva)
    raise SystemExit("no section for 0x%x"%v)

ROSTER = 0x4c5fe0
TANK_SLOTS = [16,17,18,19,20,21,22,23]   # known-good: this set reliably shows tanks (from carType 16/17)
NEW = b"TANK"

def apply():
    if not BAK.exists(): raise SystemExit("no stock backup (nfs2sen.exe.tankbak); cannot restore-then-patch safely")
    shutil.copyfile(BAK, EXE)                 # start from stock roster every time
    d = bytearray(EXE.read_bytes())
    for i in TANK_SLOTS:
        fo = v2f(ROSTER + i*8)
        d[fo:fo+5] = NEW + b"\x00"
    EXE.write_bytes(d)
    print("tank traffic slots:", TANK_SLOTS, "(rest restored to stock)")
    status()

def revert():
    if BAK.exists(): shutil.copyfile(BAK, EXE); print("reverted roster to stock"); status()
    else: print("no backup")

def status():
    d = EXE.read_bytes()
    for i in range(12, 24):
        code = bytes(d[v2f(ROSTER+i*8):v2f(ROSTER+i*8)+8]).split(b"\0")[0].decode("latin1")
        tag = "  <- tank" if code == "TANK" else ""
        print("  roster[%2d] = %-4s%s"%(i, code, tag))

if __name__=="__main__":
    {"apply":apply,"revert":revert,"status":status}.get(sys.argv[1] if len(sys.argv)>1 else "status",status)()
