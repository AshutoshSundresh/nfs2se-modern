"""Encode a PNG into the NFS2SE class-label FSH format (8-bit idx + 24-bit RGB pal, 123x44)."""
import struct
from PIL import Image

# exact A5/B5/C5 entry header (rec 0x7B, blkNext 0x1534, W123 H44, positioning) and palette header (0x24)
LBL_HDR = bytes.fromhex("7b3415007b002c000100e8ffe7012b00")
PAL_HDR = bytes.fromhex("24000000000101000001000000000000")
W, H = 123, 44

def encode(png_path):
    im = Image.open(png_path).convert("RGB").resize((W, H), Image.LANCZOS)
    q = im.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
    idx = q.tobytes()
    pal = q.getpalette()[:256*3]; pal += [0]*(256*3-len(pal))
    coldata = bytes(pal)                       # 24-bit R,G,B (label palette order)
    entry = LBL_HDR + idx + PAL_HDR + coldata
    assert len(idx) == W*H
    assert 16 + len(idx) == 0x1534             # blkNext matches header
    return entry

def render_entry(entry):
    """Round-trip: decode our own entry back to a PIL image."""
    W2,H2 = struct.unpack_from("<HH", entry, 4)
    blk = entry[1]|(entry[2]<<8)|(entry[3]<<16)
    pix = entry[16:16+W2*H2]; pb = blk+16
    pal = [(entry[pb+i*3],entry[pb+i*3+1],entry[pb+i*3+2]) for i in range(256)]
    im = Image.new("RGB",(W2,H2)); im.putdata([pal[p] for p in pix]); return im

if __name__ == "__main__":
    import sys
    e = encode(sys.argv[1])
    render_entry(e).resize((W*4,H*4),Image.NEAREST).save(sys.argv[2])
    print("encoded %s (%d bytes) -> round-trip %s"%(sys.argv[1], len(e), sys.argv[2]))
