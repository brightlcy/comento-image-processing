"""Pinned public RDD2022 partial download."""

import argparse, hashlib, json, struct, urllib.request
from pathlib import Path
from .archive import parse_central, decode_member

URL = "https://ndownloader.figshare.com/files/38030910"
TOTAL = 13264172619
EXPECTED = {
    "India": "28eab0aa85638855e1907e63b175be2305a0accd018c54603037d3fb8cab963a",
    "China_MotorBike": "2acdc8b8527c9b36cce4ba97dfdd5be9090be32f588c31b769a08c1a41c0c274",
    "Czech": "94c65a4e6cfed187b193ba967f0a2b16bd4287dfe313d0962f3711afce75bf1d",
    "Japan": "76efe7acb4642da283891611670dac7e8866a1b1dd145b8a1540fd440b1328f7",
}


def fetch_range(url, start, length, total):
    if start < 0 or length <= 0 or start + length > total:
        raise ValueError("invalid byte range")
    end = start + length - 1
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"}),
        timeout=60,
    ) as r:
        if (
            r.status != 206
            or r.headers.get("Content-Range") != f"bytes {start}-{end}/{total}"
        ):
            raise ValueError("exact range not honored")
        data = r.read(length + 1)
    if len(data) != length:
        raise ValueError("range length mismatch")
    return data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--countries", nargs="+", choices=tuple(EXPECTED))
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    entries = None
    receipts = []
    for country in a.countries or EXPECTED:
        expected = EXPECTED[country]
        target = a.output / (country + ".zip")
        if target.exists():
            sha = hashlib.sha256(target.read_bytes()).hexdigest()
            if sha != expected:
                raise ValueError("existing archive mismatch; preserved")
            receipts.append(
                dict(country=country, sha256=sha, state="already_present_verified")
            )
            continue
        if entries is None:
            tail = fetch_range(URL, TOTAL - 65557, 65557, TOTAL)
            end = tail.rfind(b"PK\x05\x06")
            if end < 0:
                raise ValueError("ZIP end missing")
            h = struct.unpack_from("<4s4H2LH", tail, end)
            size, off = h[-3:-1]
            if off == 0xFFFFFFFF:
                loc = struct.unpack_from("<4sLQL", tail, end - 20)
                if loc[0] != b"PK\x06\x07":
                    raise ValueError("ZIP64 locator missing")
                z = struct.unpack("<4sQ2H2L4Q", fetch_range(URL, loc[2], 56, TOTAL))
                size, off = z[-2:]
            entries = {
                r["name"]: r for r in parse_central(fetch_range(URL, off, size, TOTAL))
            }
        e = entries[f"RDD2022/{country}.zip"]
        length = min(
            30 + len(e["name"].encode()) + 65535 + e["compressed"], TOTAL - e["offset"]
        )
        raw = decode_member(fetch_range(URL, e["offset"], length, TOTAL), e)
        sha = hashlib.sha256(raw).hexdigest()
        if sha != expected:
            raise ValueError("member SHA256 mismatch")
        temp = target.with_suffix(".zip.partial")
        temp.write_bytes(raw)
        temp.replace(target)
        receipts.append(
            dict(
                country=country,
                sha256=sha,
                crc32=e["crc32"],
                state="downloaded_verified",
            )
        )
    receipt = dict(
        source=URL, full_outer_archive_md5_verified=False, countries=receipts
    )
    (a.output / "download_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
