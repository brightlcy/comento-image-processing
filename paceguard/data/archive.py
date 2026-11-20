"""ZIP64 and per-member CRC verification."""

from pathlib import PurePosixPath
import struct, zlib


def parse_central(data):
    rows = []
    p = 0
    while p < len(data):
        if data[p : p + 4] != b"PK\x01\x02":
            raise ValueError("invalid central signature")
        h = struct.unpack_from("<4s6H3L5H2L", data, p)
        n, x, c = h[10:13]
        name = data[p + 46 : p + 46 + n].decode("utf-8" if h[3] & 0x800 else "cp437")
        if (
            PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or "\\" in name
        ):
            raise ValueError("unsafe path")
        values = [h[9], h[8], h[-1]]
        extra = data[p + 46 + n : p + 46 + n + x]
        k = 0
        while k + 4 <= len(extra):
            tag, size = struct.unpack_from("<HH", extra, k)
            v = extra[k + 4 : k + 4 + size]
            k += 4 + size
            if tag == 1:
                q = 0
                for i in range(3):
                    if values[i] == 0xFFFFFFFF:
                        values[i] = struct.unpack_from("<Q", v, q)[0]
                        q += 8
        rows.append(
            dict(
                name=name,
                method=h[4],
                crc32=h[7],
                size=values[0],
                compressed=values[1],
                offset=values[2],
            )
        )
        p += 46 + n + x + c
    return rows


def decode_member(data, entry):
    h = struct.unpack_from("<4s5H3L2H", data)
    n, x = h[-2:]
    if h[0] != b"PK\x03\x04" or h[2] & 1:
        raise ValueError("unsupported local header")
    if data[30 : 30 + n].decode("utf-8" if h[2] & 0x800 else "cp437") != entry["name"]:
        raise ValueError("name mismatch")
    payload = data[30 + n + x : 30 + n + x + entry["compressed"]]
    if entry["method"] == 8:
        raw = zlib.decompress(payload, -15)
    elif entry["method"] == 0:
        raw = payload
    else:
        raise ValueError("unsupported compression")
    if len(raw) != entry["size"] or zlib.crc32(raw) & 0xFFFFFFFF != entry["crc32"]:
        raise ValueError("member size/CRC mismatch")
    return raw
