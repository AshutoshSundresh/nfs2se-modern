"""EA RefPack (QFS) decompress/compress + SHPI (FSH) parser for NFS2SE assets."""
import struct

def qfs_decompress(data: bytes) -> bytes:
    # header: 0x10 0xFB, then 3-byte big-endian uncompressed size
    if data[0] != 0x10 or data[1] != 0xFB:
        raise ValueError("not a QFS/RefPack stream")
    i = 2
    outsize = (data[i] << 16) | (data[i+1] << 8) | data[i+2]; i += 3
    out = bytearray()
    while i < len(data):
        ctrl = data[i]; i += 1
        if ctrl < 0x80:
            a = data[i]; i += 1
            num = ctrl & 3
            out += data[i:i+num]; i += num
            off = ((ctrl & 0x60) << 3) + a + 1
            cnt = ((ctrl >> 2) & 7) + 3
            for _ in range(cnt): out.append(out[-off])
        elif ctrl < 0xC0:
            a = data[i]; b = data[i+1]; i += 2
            num = (a >> 6) & 3
            out += data[i:i+num]; i += num
            off = ((a & 0x3F) << 8) + b + 1
            cnt = (ctrl & 0x3F) + 4
            for _ in range(cnt): out.append(out[-off])
        elif ctrl < 0xE0:
            a = data[i]; b = data[i+1]; c = data[i+2]; i += 3
            num = ctrl & 3
            out += data[i:i+num]; i += num
            off = ((ctrl & 0x10) << 12) + (a << 8) + b + 1
            cnt = ((ctrl & 0x0C) << 6) + c + 5
            for _ in range(cnt): out.append(out[-off])
        elif ctrl < 0xFC:
            num = ((ctrl & 0x1F) << 2) + 4
            out += data[i:i+num]; i += num
        else:
            num = ctrl & 3
            out += data[i:i+num]; i += num
            break
    return bytes(out)

def parse_shpi(data: bytes):
    if data[:4] != b"SHPI":
        raise ValueError("not SHPI")
    total, num, tag = struct.unpack_from("<I I 4s", data, 4)
    entries = []
    off = 16
    for _ in range(num):
        name = data[off:off+4].decode("latin1"); o = struct.unpack_from("<I", data, off+4)[0]
        entries.append((name, o)); off += 8
    out = []
    for idx,(name,o) in enumerate(entries):
        code = data[o]
        w,h = struct.unpack_from("<H H", data, o+4) if o+8 <= len(data) else (0,0)
        out.append((name,o,code,w,h))
    return total,num,tag.decode("latin1"),out

if __name__ == "__main__":
    import sys
    raw = open(sys.argv[1],"rb").read()
    fsh = qfs_decompress(raw) if raw[:2]==b"\x10\xfb" else raw
    print("decompressed %d bytes; expected header says %d"%(len(fsh), (raw[2]<<16|raw[3]<<8|raw[4]) if raw[:2]==b"\x10\xfb" else -1))
    total,num,tag,entries = parse_shpi(fsh)
    print("SHPI total=%d num=%d tag=%s"%(total,num,tag))
    for name,o,code,w,h in entries:
        print("  %-4s off=0x%06X code=0x%02X  %dx%d"%(name,o,code,w,h))
