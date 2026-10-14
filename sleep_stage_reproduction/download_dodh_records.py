"""Selectively download DOD-H records from the public Zenodo zip.

The 20.4 GB archive contains independent deflated H5 records. This helper uses
HTTP Range requests in parallel, reconstructs only selected compressed members,
and streams their decompression to disk. It does not bypass the dataset license.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from urllib.request import Request, urlopen


URL = "https://zenodo.org/api/records/15900394/files/dodh.zip/content"
# First five DOD-H entries from the zip central directory. Keeping this list
# explicit makes the provenance of a partial download auditable.
RECORDS = [
    ("1da3544e-dc5c-5795-adc3-f5068959211f.h5", 847617123, 882622232, 67),
    ("5bf0f969-304c-581e-949c-50c108f62846.h5", 842660565, 876315373, 847617531),
    ("a25b2296-343b-53f6-8792-ada2669d466e.h5", 896772402, 932613178, 1690278437),
    ("119f9726-eb4c-5a0e-a7bb-9e15256149a1.h5", 828759808, 862176942, 2587051180),
    ("0d79f4b1-e74f-5e87-8e42-f9dd7112ada5.h5", 856082090, 893082165, 3415811329),
]


def get_range(start: int, end: int) -> bytes:
    req = Request(URL, headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"})
    with urlopen(req, timeout=120) as r:
        data = r.read()
    expected = end - start + 1
    if len(data) != expected:
        raise RuntimeError(f"range {start}-{end}: expected {expected}, got {len(data)}")
    return data


def payload_start(local_offset: int) -> int:
    hdr = get_range(local_offset, local_offset + 4095)
    if hdr[:4] != b"PK\x03\x04":
        raise RuntimeError(f"bad local zip header at {local_offset}: {hdr[:8]!r}")
    _, _, _, _, _, _, _, _, _, name_len, extra_len = struct.unpack_from("<4s5H3L2H", hdr)
    return local_offset + 30 + name_len + extra_len


def download_member(name: str, csize: int, usize: int, offset: int, out_dir: Path, workers: int) -> Path:
    out = out_dir / name
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size == usize:
        print(f"exists {out.name} ({usize:,} bytes)")
        return out
    start = payload_start(offset)
    compressed = out.with_suffix(out.suffix + ".deflate")
    chunk = 8 * 1024 * 1024
    ranges = [(p, min(start + csize - 1, p + chunk - 1)) for p in range(start, start + csize, chunk)]
    print(f"download {name}: {csize/1e6:.1f} MB compressed in {len(ranges)} ranges")

    def one(r):
        return r[0], get_range(*r)

    with open(compressed, "wb") as f:
        f.truncate(csize)
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, r) for r in ranges]
        with open(compressed, "r+b") as f:
            for i, fut in enumerate(cf.as_completed(futures), 1):
                pos, data = fut.result()
                f.seek(pos - start)
                f.write(data)
                print(f"  {i}/{len(ranges)} ranges")

    dec = zlib.decompressobj(-15)
    with open(compressed, "rb") as src, open(out, "wb") as dst:
        while True:
            block = src.read(8 * 1024 * 1024)
            if not block:
                break
            dst.write(dec.decompress(block))
        dst.write(dec.flush())
    if out.stat().st_size != usize:
        raise RuntimeError(f"{out.name}: expected {usize}, got {out.stat().st_size}")
    compressed.unlink()
    print(f"saved {out} ({usize/1e6:.1f} MB)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("data/dodh"))
    ap.add_argument("--count", type=int, default=1, choices=range(1, len(RECORDS) + 1))
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for row in RECORDS[:args.count]:
        path = download_member(*row, args.out_dir, args.workers)
        manifest.append({"file": path.name, "archive": URL, "compressed_size": row[1], "uncompressed_size": row[2], "local_offset": row[3]})
    (args.out_dir / "download_manifest.json").write_text(__import__("json").dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

