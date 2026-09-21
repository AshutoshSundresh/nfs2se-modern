"""Build MAIN.QFS with the Class D assets appended: clsd card + D5/Dd labels.

Appends three SHPI entries to the original MAIN.QFS and writes MAIN.QFS.new
(stored-RefPack). Idempotent w.r.t. the original (always starts from the .bak).
"""
import sys, struct
sys.path.insert(0, "mods/class-d/tools")
from qfs import qfs_decompress
from label_encode import encode as encode_label
from PIL import Image

ORIG = "Need For Speed II SE/FEDATA/PC/ART/MAIN.QFS.class-d.bak"
OUT = "mods/class-d/MAIN.QFS.new"


def qfs_compress_stored(data: bytes) -> bytes:
    n = len(data)
    out = bytearray([0x10, 0xFB, (n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF])
    whole = n - (n % 4); pos = 0
    while pos < whole:
        take = min(112, whole - pos)
        out.append(0xE0 | ((take - 4) >> 2)); out += data[pos:pos + take]; pos += take
    rem = n - pos
    out.append(0xFC | rem); out += data[pos:pos + rem]
    return bytes(out)


def encode_card(png, ref_hdr, ref_palhdr, ref_alpha, W=306, H=146):
    im = Image.open(png).convert("RGB").resize((W, H), Image.LANCZOS)
    q = im.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    idx = q.tobytes(); pal = q.getpalette()[:256 * 3]; pal += [0] * (256 * 3 - len(pal))
    paloff = 16 + W * H
    hdr = bytearray(ref_hdr)
    hdr[1] = paloff & 0xFF; hdr[2] = (paloff >> 8) & 0xFF; hdr[3] = (paloff >> 16) & 0xFF
    struct.pack_into("<HH", hdr, 4, W, H)
    col = bytearray()
    for i in range(256):
        r, g, b = pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]
        col += bytes((b, g, r, ref_alpha))          # card palette is B,G,R,A
    entry = bytes(hdr) + idx + bytes(ref_palhdr) + bytes(col)
    if len(entry) % 16:
        entry += b"\x00" * (16 - len(entry) % 16)
    return entry


def parse_dir(fsh):
    total, num = struct.unpack_from("<II", fsh, 4)
    entries = [(fsh[16 + i * 8:16 + i * 8 + 4], struct.unpack_from("<I", fsh, 16 + i * 8 + 4)[0]) for i in range(num)]
    return total, num, fsh[12:16], entries


def append_entries(fsh, new):                       # new = list of (name4, bytes)
    total, num, tag, entries = parse_dir(fsh)
    k = len(new); shift = k * 8
    old_data_start = 16 + num * 8
    body = bytes(fsh[old_data_start:])
    out = bytearray(b"SHPI" + struct.pack("<I", 0) + struct.pack("<I", num + k) + tag)
    for name, off in entries:
        out += bytes(name) + struct.pack("<I", off + shift)
    # placeholder dir rows for new entries; fill offsets after we know positions
    newrows = []
    cur = old_data_start + shift + len(body)
    for name, data in new:
        newrows.append((name, cur)); cur += len(data)
    for name, off in newrows:
        nm = (name + b"\x00\x00\x00\x00")[:4]
        out += nm + struct.pack("<I", off)
    out += body
    for _, data in new:
        out += data
    struct.pack_into("<I", out, 4, len(out))
    return bytes(out)


def main():
    fsh = qfs_decompress(open(ORIG, "rb").read())
    _, _, _, entries = parse_dir(fsh)
    names = {bytes(n).rstrip(b"\x00 ").decode("latin1"): off for n, off in entries}
    co = names["clsa"]
    ref_hdr = bytes(fsh[co:co + 16])
    palrel = fsh[co + 1] | (fsh[co + 2] << 8) | (fsh[co + 3] << 16)
    ref_palhdr = bytes(fsh[co + palrel:co + palrel + 16])
    ref_alpha = fsh[co + palrel + 16 + 3]
    clsd = encode_card("mods/class-d/clsd_3car_preview.png", ref_hdr, ref_palhdr, ref_alpha)
    d5 = encode_label("mods/class-d/assets/label_D5.png")
    dd = encode_label("mods/class-d/assets/label_Dd.png")
    out = append_entries(fsh, [(b"clsd", clsd), (b"D5", d5), (b"Dd", dd)])
    open("mods/class-d/MAIN.fsh.new", "wb").write(out)
    qfs = qfs_compress_stored(out)
    open(OUT, "wb").write(qfs)
    print("built MAIN.QFS.new with clsd + D5 + Dd (fsh=%d, qfs=%d)" % (len(out), len(qfs)))


if __name__ == "__main__":
    main()
