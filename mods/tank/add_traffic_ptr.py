"""Add physics files for physics-less traffic carTypes by APPENDING to CARDATA.VIV.

North Country traffic spawns as carType 16 (OPP). carTypes 15/16/17 have no ptr%02d
physics file (only 18..36 ship) -> default featherweight. We clone the school bus tune
(PTR20.DAT, mass field[0]=6000, the heaviest) into new members PTR16.DAT (+PTR17.DAT).

CRITICAL: we APPEND the new members at the END of the member list. An earlier attempt
inserted PTR17 in the middle, which shifted every later member's ORDINAL position and
corrupted traffic (the described-data engine can index VIV members by position). Append
keeps all existing members at their original indices; new members get the highest indices.
Data offsets all shift (the TOC grows) but those are read from the TOC, so that's fine.

BIGF: 'BIGF', totalSize(BE)@4, count(BE)@8, dataStart(BE)@12, then count TOC entries
{offset(BE), size(BE), name\0}, then member data packed in TOC order.

    python add_traffic_ptr.py apply | revert | status
"""
import struct, sys, shutil
from pathlib import Path

VIV = Path("GAMEDATA/Sim/CarData/CARDATA.VIV")
BAK = VIV.with_suffix(".VIV.tankbak")     # pristine stock
SRC = "PTR20.DAT"                          # school bus physics to clone
NEW = ["PTR16.DAT"]                        # new physics-less traffic slots to give weight

def _parse(raw):
    assert raw[:4]==b"BIGF"
    count=struct.unpack(">I",raw[8:12])[0]; off=16; ent=[]
    for _ in range(count):
        o,s=struct.unpack(">II",raw[off:off+8]); off+=8
        e=raw.index(b"\0",off); ent.append((raw[off:e].decode("latin1"),o,s)); off=e+1
    return ent

def _build(members):
    toc_size=sum(8+len(n)+1 for n,_ in members)
    data_start=(16+toc_size+3)&~3
    toc=bytearray(); data=bytearray(); cur=data_start
    for n,b in members:
        toc+=struct.pack(">II",cur,len(b))+n.encode("latin1")+b"\0"; data+=b; cur+=len(b)
    pad=data_start-(16+len(toc)); total=data_start+len(data)
    out=b"BIGF"+struct.pack(">I",total)+struct.pack(">I",len(members))+struct.pack(">I",data_start)+bytes(toc)+b"\0"*pad+bytes(data)
    assert len(out)==total
    return out

def apply():
    if not BAK.exists(): shutil.copyfile(VIV,BAK)
    raw=BAK.read_bytes(); ent=_parse(raw)
    have={n.upper() for n,_,_ in ent}
    src=next((o,s) for n,o,s in ent if n.upper()==SRC)
    src_data=raw[src[0]:src[0]+src[1]]
    members=[(n, raw[o:o+s]) for n,o,s in ent]     # all stock members, ORIGINAL order
    added=[]
    for name in NEW:
        if name.upper() in have: continue
        members.append((name, src_data))            # APPEND at end
        added.append(name)
    out=_build(members)
    VIV.write_bytes(out)
    print("appended %s (clone of %s); members %d -> %d; VIV %d -> %d bytes"
          %(added,SRC,len(ent),len(members),len(raw),len(out)))

def revert():
    if BAK.exists(): shutil.copyfile(BAK,VIV); print("CARDATA.VIV restored from stock backup")
    else: print("no backup")

def status():
    ent=_parse(VIV.read_bytes()); names=[n.upper() for n,_,_ in ent]
    want={x.upper() for x in NEW} | {SRC}
    for i,(n,o,s) in enumerate(ent):
        if n.upper() in want:
            print("  %-12s off=%d size=%d idx=%d"%(n,o,s,i))
    print("  total members:",len(ent))

if __name__=="__main__":
    {"apply":apply,"revert":revert,"status":status}.get(sys.argv[1] if len(sys.argv)>1 else "status",status)()
