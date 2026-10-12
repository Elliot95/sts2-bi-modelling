"""
Extracts event artwork from the player's OWN Slay the Spire 2 install for the
report's Events page: one JPEG background per event, plus palette.csv with a
colour theme derived from each image (dark base, panel and accent colours).

The art is Mega Crit's; this script exists so it can be rebuilt by anyone who
owns the game, rather than redistributing the images themselves (the output
folder is gitignored). Power BI reads the folder at refresh time and embeds
each image as a data URI, split into chunks because a text value is capped at
32,766 characters (see docs/powerbi_setup.md, "Event artwork").

Godot stores the textures as .ctex ("GST2") files containing either an embedded
PNG/WebP or raw BC1/BC3/BC7 blocks; those are wrapped in a standard DDS header so
Pillow can decode it. Images are then cropped and downscaled.

Usage:
    python scripts/extract_event_images.py [--out powerbi/assets/events] [--width 1600]
"""

import argparse
import colorsys
import csv
import io
import struct
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sts2_pck import Pck  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CATALOG = REPO / "dbt" / "seeds" / "event_catalog.csv"
# Where an event's artwork lives, in order of preference: regular events have
# a dedicated illustration; Ancients have a timeline portrait or a room image.
CANDIDATES = ["res://images/events/{n}.png",
              "res://images/timeline/epoch_portraits/{n}_epoch.png",
              "res://animations/backgrounds/{n}_room/{n}.png",
              "res://animations/backgrounds/{n}/{n}.png",
              "res://images/ancients/{n}_placeholder.png"]
DATA_IMAGE, DATA_PNG, DATA_WEBP = 0, 1, 2   # Godot CompressedTexture2D data formats
# Godot Image::Format -> (DXGI format, bytes per 4x4 block) for block-compressed textures
BLOCK_FORMATS = {17: (71, 8),    # DXT1 -> BC1_UNORM
                 18: (74, 16),   # DXT3 -> BC2_UNORM
                 19: (77, 16),   # DXT5 -> BC3_UNORM
                 22: (98, 16)}   # BPTC_RGBA -> BC7_UNORM


def dds(width: int, height: int, dxgi: int, blocks: bytes) -> bytes:
    """Minimal DDS file (DX10 extended header) wrapping block-compressed data."""
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000          # caps|height|width|pixelformat|linearsize
    header = struct.pack("<4sIIIIIII44x", b"DDS ", 124, flags, height, width, len(blocks), 0, 1)
    pixel_format = struct.pack("<II4sIIIII", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
    caps = struct.pack("<IIIII", 0x1000, 0, 0, 0, 0)
    dx10 = struct.pack("<IIIII", dxgi, 3, 0, 1, 0)   # TEXTURE2D, 1 array slice
    return header + pixel_format + caps + dx10 + blocks


def decode_ctex(data: bytes) -> Image.Image:
    magic, _ver, width, height = struct.unpack("<4sIII", data[:16])
    if magic != b"GST2":
        raise ValueError("not a Godot CompressedTexture2D")
    data_format, pw, ph, _mips, img_format = struct.unpack("<IHHII", data[36:52])
    if data_format in (DATA_PNG, DATA_WEBP):               # lossless/lossy blob: u32 size + file
        (size,) = struct.unpack("<I", data[52:56])
        return Image.open(io.BytesIO(data[56:56 + size])).convert("RGB").crop((0, 0, width, height))
    if data_format != DATA_IMAGE or img_format not in BLOCK_FORMATS:
        raise ValueError(f"unsupported texture (data_format={data_format}, format={img_format})")
    dxgi, block = BLOCK_FORMATS[img_format]
    size = ((pw + 3) // 4) * ((ph + 3) // 4) * block    # first mip level only
    img = Image.open(io.BytesIO(dds(pw, ph, dxgi, data[52:52 + size])))
    return img.convert("RGB").crop((0, 0, width, height))


def hex_hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def palette(img: Image.Image) -> dict:
    """A dark base / panel / bright accent theme from the image's colours."""
    small = img.resize((96, 45))
    # base: the image's average hue, pushed very dark so light text reads on it
    r, g, b = (sum(c) / len(c) / 255 for c in zip(*small.getdata()))
    h, s, _ = colorsys.rgb_to_hsv(r, g, b)
    s = min(max(s * 1.3, 0.25), 0.7)
    # accent: the most vivid of the dominant colours, weighted by how much of the image it covers
    q = small.quantize(8)
    pal = q.getpalette()
    best, best_score = None, -1.0
    for count, idx in q.getcolors():
        cr, cg, cb = (pal[idx * 3 + i] / 255 for i in range(3))
        ch, cs, cv = colorsys.rgb_to_hsv(cr, cg, cb)
        score = cs * cv * (count / (96 * 45)) ** 0.5
        if score > best_score:
            best, best_score = (ch, cs, cv), score
    ah, as_, _ = best
    accent = hex_hsv(ah, max(as_, 0.55), 0.95) if as_ > 0.12 else "#f5b041"
    return {"bg": hex_hsv(h, s, 0.09), "panel": hex_hsv(h, s, 0.15), "accent": accent}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "powerbi" / "assets" / "events"))
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--only", help="extract a single event, e.g. EVENT.BYRDONIS_NEST")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pck = Pck()
    imported = {}                       # res:// source png -> imported .ctex
    for entry in pck.entries:
        if entry.endswith(".png.import"):
            imported[entry[:-len(".import")]] = entry
    ctex = {p.split("/")[-1].split(".png-")[0]: p for p in pck.entries
            if p.startswith("res://.godot/imported/") and p.endswith(".ctex")}

    with open(CATALOG, encoding="utf-8") as f:
        events = [row["event_id"] for row in csv.DictReader(f)]
    if args.only:
        events = [e for e in events if e == args.only]
    themes = []
    for event_id in events:
        name = event_id.split(".", 1)[1].lower()
        source = next((c.format(n=name) for c in CANDIDATES if c.format(n=name) in imported), None)
        stem = source and source.split("/")[-1][:-len(".png")]
        if not source or stem not in ctex:
            print(f"  no art: {event_id}")
            continue
        try:
            img = decode_ctex(pck.read(ctex[stem]))
        except ValueError as e:
            print(f"  skip {event_id}: {e}")
            continue
        h = round(img.height * args.width / img.width)
        img.resize((args.width, h), Image.LANCZOS).save(out / f"{name}.jpg", quality=72, optimize=True)
        themes.append({"event_id": event_id, **palette(img)})
    if not args.only:
        with open(out / "palette.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["event_id", "bg", "panel", "accent"])
            w.writeheader()
            w.writerows(themes)
    print(f"{len(themes)} event images + palette -> {out}")


if __name__ == "__main__":
    main()
