#!/usr/bin/env python3
"""vm.ps1 peek が出す RGB565 の生データ（800x600）を PNG にする。外部ライブラリは使わない。
  python3 harness/sandbox/hyperv/peek.py <peek.rgb565> [<出力.png>]
"""
import struct, sys, zlib
from pathlib import Path

src = Path(sys.argv[1]); dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".png")
raw = src.read_bytes(); w, h = 800, 600
if len(raw) < w * h * 2:
    raise SystemExit(f"大きさが違う: {len(raw)} バイト（{w*h*2} が要る）")
rows = []
for y in range(h):
    row = bytearray([0])
    for x in range(w):
        v = raw[2 * (y * w + x)] | (raw[2 * (y * w + x) + 1] << 8)
        row += bytes((((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31))
    rows.append(bytes(row))
def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
dst.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
print(dst)
