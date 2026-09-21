"""Build a 'clsd' class card and append it to MAIN.QFS (SHPI/QFS), reversibly."""
import sys, struct
sys.path.insert(0, "mods/class-d/tools")
from qfs import qfs_decompress
from PIL import Image

def qfs_compress_stored(data: bytes) -> bytes:
    n = len(data)
    out = bytearray([0x10, 0xFB, (n>>16)&0xFF, (n>>8)&0xFF, n&0xFF])
    whole = n - (n % 4)
    pos = 0
    while pos < whole:
        take = min(112, whole-pos)
        out.append(0xE0 | ((take-4)>>2))
        out += data[pos:pos+take]; pos += take
    rem = n - pos
    out.append(0xFC | rem); out += data[pos:pos+rem]
    return bytes(out)

def build_clsd_entry(png_path, ref_hdr, ref_palhdr, ref_alpha):
    im = Image.open(png_path).convert("RGB")
    assert im.size == (306,146), im.size
    q = im.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    idx = q.tobytes()                      # 306*146 index bytes
    pal = q.getpalette()[:256*3]
    pal += [0]*(256*3-len(pal))
    W,H = 306,146
    paloff = 16 + W*H                       # 0xAE94
    hdr = bytearray(ref_hdr)                # copy exact 16-byte header
    hdr[1]=paloff&0xFF; hdr[2]=(paloff>>8)&0xFF; hdr[3]=(paloff>>16)&0xFF
    struct.pack_into("<HH",hdr,4,W,H)       # ensure W,H
    palblk = bytearray(ref_palhdr)          # 16-byte palette header (0x2A ...)
    coldata = bytearray()
    for i in range(256):
        r,g,b = pal[i*3],pal[i*3+1],pal[i*3+2]
        coldata += bytes((b,g,r,ref_alpha))   # game palette byte order is B,G,R,A
    entry = bytes(hdr)+idx+bytes(palblk)+bytes(coldata)
    if len(entry)%16: entry += b"\x00"*(16-len(entry)%16)
    return entry

def main():
    src = "Need For Speed II SE/FEDATA/PC/ART/MAIN.QFS"
    raw = open(src,"rb").read()
    fsh = bytearray(qfs_decompress(raw))
    assert fsh[:4]==b"SHPI"
    total,num = struct.unpack_from("<II",fsh,4)
    tag = fsh[12:16]
    # read directory
    dir_entries=[]
    for i in range(num):
        o=16+i*8
        name=fsh[o:o+4]; off=struct.unpack_from("<I",fsh,o+8-4)[0]
        dir_entries.append([name,off])
    names={bytes(n).decode('latin1'):off for n,off in dir_entries}
    # reference header/palette from clsa
    co=names['clsa']
    ref_hdr=bytes(fsh[co:co+16])
    palrel=fsh[co+1]|(fsh[co+2]<<8)|(fsh[co+3]<<16)
    ref_palhdr=bytes(fsh[co+palrel:co+palrel+16])
    ref_alpha=fsh[co+palrel+16+3]           # alpha byte of clsa pal[0]
    if 'clsd' in names:
        print("clsd already present; aborting"); return 1
    clsd=build_clsd_entry("mods/class-d/clsd_3car_preview.png",ref_hdr,ref_palhdr,ref_alpha)
    # rebuild: dir grows by 8, all data shifts +8, clsd appended at end
    new_num=num+1
    shift=8
    data_start=16+new_num*8
    # existing data block is everything from old data_start to end
    old_data_start=16+num*8
    body=bytes(fsh[old_data_start:])         # all entry data
    new_off_for=lambda off: off+shift
    # assemble
    out=bytearray()
    out+=b"SHPI"
    out+=struct.pack("<I",0)                 # total placeholder
    out+=struct.pack("<I",new_num)
    out+=tag
    for name,off in dir_entries:
        out+=bytes(name)+struct.pack("<I",new_off_for(off))
    clsd_off=old_data_start+shift+len(body)  # after existing body
    out+=b"clsd"+struct.pack("<I",clsd_off)
    out+=body
    out+=clsd
    struct.pack_into("<I",out,4,len(out))    # total = full size
    # write outputs
    open("mods/class-d/MAIN.fsh.new","wb").write(out)
    qfs=qfs_compress_stored(bytes(out))
    open("mods/class-d/MAIN.QFS.new","wb").write(qfs)
    print("orig fsh=%d new fsh=%d clsd_entry=%d clsd_off=0x%X new_num=%d"%(len(fsh),len(out),len(clsd),clsd_off,new_num))
    print("qfs stored size=%d (orig qfs=%d)"%(len(qfs),len(raw)))
    print("ref_alpha=0x%02X"%ref_alpha)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
