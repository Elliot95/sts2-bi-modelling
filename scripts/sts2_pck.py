"""
Minimal reader for Slay the Spire 2's Godot resource pack (SlayTheSpire2.pck).

Used to pull reference data (localization JSON, card pools, event art) from
the player's OWN game install instead of scraping third-party sites. Read-only:
nothing in the game folder is modified.

Godot 4 PCK, format version 3:
    "GDPC" | u32 pack_format | u32 major, minor, patch | u32 flags
    | u64 file_base | u64 directory_offset | 16 x u32 reserved
    directory: u32 file_count, then per file:
        u32 path_len | path (UTF-8, NUL-padded) | u64 offset | u64 size | 16B md5 | u32 flags
    flags bit 0 = encrypted directory (not supported), bit 1 = offsets are
    relative to file_base.
"""

import os
import struct
from dataclasses import dataclass

DEFAULT_PCK = os.environ.get(
    "STS2_PCK", r"N:\SteamLibrary\steamapps\common\Slay the Spire 2\SlayTheSpire2.pck")


@dataclass
class Entry:
    path: str
    offset: int
    size: int


class Pck:
    def __init__(self, path: str = DEFAULT_PCK):
        self.path = path
        self.entries: dict[str, Entry] = {}
        with open(path, "rb") as f:
            magic, fmt, *_ver, flags = struct.unpack("<4sIIIII", f.read(24))
            if magic != b"GDPC":
                raise ValueError("Not a Godot PCK file")
            if fmt < 3:
                raise ValueError(f"Unsupported PCK format {fmt}")
            if flags & 1:
                raise ValueError("Encrypted PCK directory is not supported")
            file_base, dir_offset = struct.unpack("<QQ", f.read(16))
            base = file_base if flags & 2 else 0
            f.seek(dir_offset)
            (count,) = struct.unpack("<I", f.read(4))
            for _ in range(count):
                (plen,) = struct.unpack("<I", f.read(4))
                p = f.read(plen).rstrip(b"\0").decode("utf-8")
                offset, size = struct.unpack("<QQ", f.read(16))
                f.read(16 + 4)  # md5 + per-file flags
                p = p if p.startswith("res://") else "res://" + p
                self.entries[p] = Entry(p, base + offset, size)

    def read(self, path: str) -> bytes:
        e = self.entries[path if path.startswith("res://") else "res://" + path]
        with open(self.path, "rb") as f:
            f.seek(e.offset)
            return f.read(e.size)

    def find(self, contains: str) -> list[str]:
        return sorted(p for p in self.entries if contains in p)


if __name__ == "__main__":
    pck = Pck()
    print(f"{len(pck.entries)} files in {pck.path}")
    for p in pck.find("localization/eng/")[:40]:
        print(" ", p, pck.entries[p].size)
