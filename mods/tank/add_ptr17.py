"""Give traffic carType 17 (the tank's slot) heavy physics by cloning the semi's tune.

Traffic physics files are looked up as sprintf("ptr%02d", carType) -> ptr17, ptr18...
(format string at exe VA 0x4B9DE0). They live inside CARDATA.VIV as PTR18.DAT..PTR36.DAT.
carType 17 has NO ptr17 -> the tank spawned there falls back to default featherweight
physics. This clones PTR21.DAT (the SEMI's tune, 356 B) into a new member PTR17.DAT and
rebuilds the BIGF archive, so carType-17 traffic (our tank) becomes semi-heavy while the
real semi (carType 21) is untouched.

BIGF layout: 'BIGF', totalSize(BE u32)@4, count(BE u32)@8, dataStart(BE u32)@12,
then count TOC entries {offset(BE u32), size(BE u32), name\0}, then member data packed
contiguously in TOC order. Adding a member shifts every data offset, so we rebuild whole.

    python add_ptr17.py apply | revert | status
"""
import struct, sys, shutil
from pathlib import Path

VIV = Path("GAMEDATA/Sim/CarData/CARDATA.VIV")
BAK = VIV.with_suffix(".VIV.tankbak")
SRC_NAME = "PTR21.DAT"     # semi physics to clone
NEW_NAME = "PTR17.DAT"     # tank's carType-17 physics

def _parse(raw):
    assert raw[:4]==b"BIGF", "not BIGF"
    count=struct.unpack(">I",raw[8:12])[0]
    off=16; ent=[]
    for _ in range(count):
        o,s=struct.unpack(">II",raw[off:off+8]); off+=8
        e=raw.index(b"\0",off); name=raw[off:e].decode("latin1"); off=e+1
        ent.append((name,o,s))
    return ent

def _build(members):
    # members: list of (name, data_bytes) in desired order
    toc_size = sum(8+len(n)+1 for n,_ in members)
    data_start = 16+toc_size
    data_start = (data_start+3)&~3          # 4-byte align (matches stock)
    # lay out data contiguously, record offsets
    toc=bytearray(); data=bytearray(); cur=data_start
    for n,b in members:
        toc += struct.pack(">II",cur,len(b)) + n.encode("latin1") + b"\0"
        data += b; cur += len(b)
    pad = data_start-(16+len(toc))
    total = data_start+len(data)
    out = b"BIGF" + struct.pack(">I",total) + struct.pack(">I",len(members)) \
          + struct.pack(">I",data_start) + bytes(toc) + b"\0"*pad + bytes(data)
    assert len(out)==total, (len(out),total)
    return out

def apply():
    if not BAK.exists(): shutil.copyfile(VIV, BAK)
    raw = BAK.read_bytes()                    # always build from pristine stock
    ent = _parse(raw)
    if any(n.upper()==NEW_NAME for n,_,_ in ent):
        print(NEW_NAME,"already present in backup?? aborting"); return
    src = next((o,s) for n,o,s in ent if n.upper()==SRC_NAME)
    src_data = raw[src[0]:src[0]+src[1]]
    members=[]
    for n,o,s in ent:
        members.append((n, raw[o:o+s]))
        if n.upper()=="PTR18.DAT":            # insert PTR17 just before PTR18 (numeric order)
            members.insert(len(members)-1,(NEW_NAME, src_data))
    out=_build(members)
    VIV.write_bytes(out)
    print("added %s (clone of %s, %d B); VIV %d -> %d bytes, %d members"
          %(NEW_NAME,SRC_NAME,len(src_data),len(raw),len(out),len(members)))

def revert():
    if BAK.exists(): shutil.copyfile(BAK,VIV); print("CARDATA.VIV restored from backup")
    else: print("no backup")

def status():
    ent=_parse(VIV.read_bytes())
    for n,o,s in ent:
        if n.upper() in (NEW_NAME,SRC_NAME): print("  %-12s off=%d size=%d"%(n,o,s))
    print("  total members:",len(ent))

if __name__=="__main__":
    {"apply":apply,"revert":revert,"status":status}.get(sys.argv[1] if len(sys.argv)>1 else "status",status)()
