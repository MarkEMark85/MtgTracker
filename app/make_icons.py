"""Writes icon-192.png and icon-512.png (the diamond logo) with only the standard library."""
import struct
import zlib
from pathlib import Path

BG = (0x14, 0x16, 0x1C)
GOLD = (0xE0, 0xB6, 0x4A)


def pixel(x: float, y: float) -> tuple:
    d = abs(x - 0.5) + abs(y - 0.5)  # diamond distance from centre
    return GOLD if 0.14 < d <= 0.28 else BG  # same proportions as icon.svg


def write_png(path: Path, size: int) -> None:
    rows = b"".join(
        b"\x00" + b"".join(bytes(pixel((x + 0.5) / size, (y + 0.5) / size)) for x in range(size))
        for y in range(size)
    )

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


if __name__ == "__main__":
    static = Path(__file__).resolve().parent / "static"
    for s in (192, 512):
        write_png(static / f"icon-{s}.png", s)
