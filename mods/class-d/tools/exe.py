"""VA<->file mapping + capstone disasm for nfs2sen.exe (imagebase 0x400000)."""
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
# sections: AUTO code raw0x400 va0x401000 ; DGROUP raw0xB7400 va0x4B9000
def va2off(va):
    if 0x401000<=va<0x4B7000: return va-0x400C00          # AUTO
    if 0x4B9000<=va<0x4D4000: return va-0x401C00          # DGROUP
    if 0x4B7000<=va<0x4B9000: return va-0x400E00          # .idata (raw0xB6200 va0x4B7000)
    raise ValueError("VA 0x%X not in a raw section (maybe .bss)"%va)
def off2va(off):
    if 0x400<=off<0xB6200: return off+0x400C00
    if 0xB7400<=off<0xD2200: return off+0x401C00
    raise ValueError("off 0x%X"%off)
_md=Cs(CS_ARCH_X86,CS_MODE_32); _md.detail=True
def disasm(exe,va,n=20,count=None):
    off=va2off(va); code=exe[off:off+n*16]; out=[]
    for ins in _md.disasm(code,va):
        out.append((ins.address,ins.mnemonic,ins.op_str,ins.bytes.hex()))
        if count and len(out)>=count: break
        if len(out)>=n: break
    return out
def refs_to(exe,va):
    t=struct.pack("<I",va); i=0;res=[]
    while True:
        i=exe.find(t,i)
        if i<0:break
        res.append(i);i+=1
    return res
