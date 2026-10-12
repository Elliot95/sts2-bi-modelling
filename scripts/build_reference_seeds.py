"""
Builds the dbt reference seeds from the player's OWN Slay the Spire 2 install:

    dbt/seeds/card_catalog.csv          card -> character pool, rarity, type, cost, colour
    dbt/seeds/event_catalog.csv         event -> name, opening description
    dbt/seeds/event_option_catalog.csv  event option -> title, description
    dbt/seeds/relic_catalog.csv         relic -> name, description
    dbt/seeds/ancient_dialogue.csv      Ancient x character x visit -> dialogue lines
    dbt/seeds/potion_catalog.csv        potion -> name, description

Sources (read-only, nothing in the game folder is modified):
  * sts2.dll  - card pools and each card's rarity / type / cost, read as
                metadata by tools/sts2_reference (a .NET metadata reader; the
                assembly is never loaded, executed or decompiled into the repo).
  * SlayTheSpire2.pck - the game's English localization JSON (card names,
                event and option text), via scripts/sts2_pck.py.

This replaces an earlier version that scraped a community wiki, whose terms
prohibit automated collection. Re-run after game patches, then `dbt seed`.

Usage:
    python scripts/build_reference_seeds.py [--game-dir "N:/.../Slay the Spire 2"]
"""

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sts2_pck import Pck  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SEEDS = REPO / "dbt" / "seeds"
TOOL = REPO / "tools" / "sts2_reference"

# Our own palette for each card pool (the report theme's colours).
POOL_COLORS = {
    "Ironclad": "#ef4444", "Silent": "#22c55e", "Defect": "#38bdf8", "Necrobinder": "#8b5cf6",
    "Regent": "#eab308", "Colorless": "#94a3b8", "Event": "#14b8a6", "Curse": "#a855f7",
    "Status": "#64748b", "Token": "#64748b", "Quest": "#f97316", "Deprecated": "#9ca3af",
}
MARKUP = re.compile(r"\[/?[a-z_]+(=[^\]]*)?\]")


def snake(name: str) -> str:
    """PerfectedStrike -> PERFECTED_STRIKE (the game's localization key form)."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name).upper()


def clean(text: str) -> str:
    """Strip the game's rich-text tags ([gold], [jitter]...) and tidy whitespace."""
    text = MARKUP.sub("", text or "")
    return re.sub(r"\s*\n\s*", " ", text).strip()


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows):4d} rows -> {path.relative_to(REPO)}")


def card_catalog(game_dir: Path, pck: Pck) -> None:
    dll = game_dir / "data_sts2_windows_x86_64" / "sts2.dll"
    out = subprocess.run(["dotnet", "run", "-c", "Release", "--project", str(TOOL), "--", str(dll)],
                         capture_output=True, text=True, check=True).stdout
    cards = json.loads(out)["cards"]
    loc = json.loads(pck.read("localization/eng/cards.json"))
    rows = []
    for c in cards:
        if not c["pool"] or c["pool"] == "Mock":
            continue
        key = snake(c["class"])
        rows.append({
            "card_id": f"CARD.{key}",
            "card_name": clean(loc.get(f"{key}.title", c["class"])),
            "card_character": c["pool"],
            "rarity": c["rarity"] or "",
            "card_type": c["card_type"] or "",
            "energy_cost": "" if c["energy_cost"] is None else c["energy_cost"],
            "card_color": POOL_COLORS.get(c["pool"], "#9ca3af"),
        })
    write_csv(SEEDS / "card_catalog.csv", sorted(rows, key=lambda r: (r["card_character"], r["card_id"])))


def event_catalogs(pck: Pck) -> None:
    # Regular events live in events.json; Neow and the other act-opening
    # "Ancients" use the same page/option structure in ancients.json.
    events, options = {}, []
    for source, kind in (("events", "Event"), ("ancients", "Ancient")):
        loc = json.loads(pck.read(f"localization/eng/{source}.json"))
        for key, value in loc.items():
            parts = key.split(".")
            event = parts[0]
            if len(parts) == 2 and parts[1] == "title":
                events.setdefault(event, {"event_id": f"EVENT.{event}", "event_kind": kind})["event_name"] = clean(value)
            elif parts[1:3] == ["pages", "INITIAL"] and parts[-1] == "description" and len(parts) == 4:
                events.setdefault(event, {"event_id": f"EVENT.{event}", "event_kind": kind})["description"] = clean(value)
            elif len(parts) == 6 and parts[1] == "pages" and parts[3] == "options" and parts[5] == "title":
                page, opt = parts[2], parts[4]
                options.append({
                    "event_id": f"EVENT.{event}",
                    "page": page,
                    "option": opt,
                    "option_key": ".".join(parts[:5]),
                    "option_title": clean(value),
                    "option_description": clean(loc.get(".".join(parts[:5]) + ".description", "")),
                })
    rows = [{"event_id": e["event_id"], "event_name": e.get("event_name", ""), "event_kind": e["event_kind"],
             "description": e.get("description", "")} for e in events.values() if e.get("event_name")]
    write_csv(SEEDS / "event_catalog.csv", sorted(rows, key=lambda r: r["event_id"]))
    write_csv(SEEDS / "event_option_catalog.csv", sorted(options, key=lambda r: r["option_key"]))


CHARACTERS = {"IRONCLAD": "Ironclad", "SILENT": "Silent", "DEFECT": "Defect",
              "NECROBINDER": "Necrobinder", "REGENT": "Regent", "ANY": "Any", "firstVisitEver": "First visit"}
TALK = re.compile(r"^(?P<ancient>[A-Z_]+)\.talk\.(?P<who>[A-Za-z]+)\.(?P<conv>\d+)-(?P<line>\d+)r?\.(?P<speaker>ancient|char)$")


def ancient_dialogue(pck: Pck) -> None:
    """What each Ancient says to each character, visit by visit (conversation 0 =
    first meeting). Player reply buttons (".next") are skipped."""
    loc = json.loads(pck.read("localization/eng/ancients.json"))
    rows = []
    for key, value in loc.items():
        m = TALK.match(key)
        if not m or m["who"] not in CHARACTERS:
            continue
        ancient = m["ancient"]
        rows.append({
            "event_id": f"EVENT.{ancient}",
            "character": CHARACTERS[m["who"]],
            "conversation": int(m["conv"]),
            "line": int(m["line"]),
            "speaker": clean(loc.get(f"{ancient}.title", ancient)) if m["speaker"] == "ancient" else CHARACTERS[m["who"]],
            "text": clean(value),
        })
    write_csv(SEEDS / "ancient_dialogue.csv",
              sorted(rows, key=lambda r: (r["event_id"], r["character"], r["conversation"], r["line"])))


def potion_catalog(pck: Pck) -> None:
    loc = json.loads(pck.read("localization/eng/potions.json"))
    rows = [{"potion_id": f"POTION.{k[:-len('.title')]}", "potion_name": clean(v),
             "description": clean(loc.get(k[:-len(".title")] + ".description", ""))}
            for k, v in loc.items() if k.endswith(".title") and k.count(".") == 1]
    write_csv(SEEDS / "potion_catalog.csv", sorted(rows, key=lambda r: r["potion_id"]))


def relic_catalog(pck: Pck) -> None:
    loc = json.loads(pck.read("localization/eng/relics.json"))
    rows = [{"relic_id": f"RELIC.{k[:-len('.title')]}", "relic_name": clean(v),
             "description": clean(loc.get(k[:-len(".title")] + ".description", ""))}
            for k, v in loc.items() if k.endswith(".title") and k.count(".") == 1]
    write_csv(SEEDS / "relic_catalog.csv", sorted(rows, key=lambda r: r["relic_id"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-dir", default=r"N:\SteamLibrary\steamapps\common\Slay the Spire 2")
    game_dir = Path(ap.parse_args().game_dir)
    pck = Pck(str(game_dir / "SlayTheSpire2.pck"))
    card_catalog(game_dir, pck)
    event_catalogs(pck)
    relic_catalog(pck)
    ancient_dialogue(pck)
    potion_catalog(pck)


if __name__ == "__main__":
    main()
