"""
Builds dbt/seeds/card_catalog.csv: reference data for every Slay the Spire 2
card (owning character, rarity, type, energy cost, card colour).

The .run files only carry card IDs (CARD.BATTLE_TRANCE), so card attributes
come from a second source: the community database at slaythespire2.gg, which
embeds its card records in the /cards page's Next.js payload. Each record's
`localizationKey` matches the game's card ID exactly (BATTLE_TRANCE ->
CARD.BATTLE_TRANCE), so the join needs no fuzzy matching.

Re-run after game patches, then `dbt seed`. The dbt test
`assert_cards_in_catalog` warns when runs contain cards the catalog doesn't
know (new cards, or cards retired from the current game version).

Usage:
    python scripts/fetch_card_catalog.py            # writes dbt/seeds/card_catalog.csv
"""

import csv
import re
import urllib.request
from collections import Counter
from pathlib import Path

URL = "https://slaythespire2.gg/cards"
OUT = Path(__file__).resolve().parent.parent / "dbt" / "seeds" / "card_catalog.csv"

BS = chr(92)

# "Any text that doesn't start a new record": stops a record with missing
# fields (e.g. a retired card with no localizationKey) from matching on into
# the NEXT record and borrowing its key.
WITHIN = r'(?:(?!\{"id":").)*?'
RECORD = re.compile(
    r'"name":"(?P<name>[^"]*)","category":"CARD"'
    + WITHIN + r'"iconColor":"(?P<color>#[0-9a-fA-F]{6})"'
    + WITHIN + r'"character":"(?P<character>[^"]*)"'
    r',"rarity":"(?P<rarity>[^"]*)"'
    r',"localizationKey":"(?P<key>[^"]*)"'
    r'(?:,"energy":(?P<energy>-?\d+|"[^"]*"|null))?'
    r'(?:,"cardType":"(?P<type>[^"]*)")?',
    re.S,
)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (sts2-bi-modelling)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def parse(html: str) -> list[dict]:
    # The payload is streamed in self.__next_f.push([1,"..."]) chunks that can
    # split a record mid-field: stitch them back together, then undo one level
    # of string escaping.
    html = re.sub(r'"\]\)</script><script>self\.__next_f\.push\(\[1,"', "", html)
    html = html.replace(BS + '"', '"')

    rows = {}
    for m in RECORD.finditer(html):
        d = m.groupdict()
        if d["key"] in rows:
            continue
        energy = (d["energy"] or "").strip('"')
        rows[d["key"]] = {
            "card_id": f"CARD.{d['key']}",
            "card_name": d["name"],
            "card_character": d["character"].removeprefix("The "),
            "rarity": d["rarity"],
            "card_type": d["type"] or "",
            "energy_cost": energy if energy not in ("", "null") else "",
            "card_color": d["color"].lower(),
        }
    return sorted(rows.values(), key=lambda r: (r["card_character"], r["card_id"]))


def main():
    rows = parse(fetch(URL))
    if len(rows) < 400:
        raise SystemExit(f"Only parsed {len(rows)} cards - page format may have changed")
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} cards to {OUT}")
    print(Counter(r["card_character"] for r in rows))


if __name__ == "__main__":
    main()
