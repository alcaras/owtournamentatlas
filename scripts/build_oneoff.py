#!/usr/bin/env python3
"""
build_oneoff.py — render + stat EVERY save in one-offs/ (one page each).
Reuses the calibration analyzer for the full metric set, draws a detailed
hex map with both original capitals marked. Emits src/data/oneoffs.json
(list) + public/img/oneoff/<slug>.png each.
"""
from __future__ import annotations
import glob, json, os, sys, tempfile, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ATLAS = Path(__file__).resolve().parent.parent
LAB = ATLAS.parent / "owmapgen-lab"
sys.path.insert(0, str(LAB / "scripts"))
sys.path.insert(0, str(ATLAS / "scripts"))
from build_tournament import analyze            # noqa: E402
from render_map import render                   # noqa: E402
from render_pretty import render_pretty          # noqa: E402

ONE = ATLAS / "one-offs"
IMG = ATLAS / "public" / "img" / "oneoff"

# Resources grouped by the IMPROVEMENT used to work them. Farm/Mine/
# Quarry/Lumbermill/Grove/Nets are authoritative from improvement.xml;
# Pasture/Camp/Urban curated (game doesn't tag those in improvement.xml).
# Display names match build_tournament's RESOURCE_*.replace().title().
RES_BY_IMP = {
    "Farm": ["Wheat", "Barley", "Sorghum"],
    "Pasture": ["Cattle", "Sheep", "Pig", "Goat", "Horse"],
    "Camp": ["Game", "Fur", "Elephant", "Ivory", "Camel", "Exotic_Fur",
             "Exotic_Animals"],
    "Grove": ["Wine", "Olive", "Citrus", "Honey", "Incense", "Lavender",
              "Silk", "Spices", "Tea"],
    "Nets": ["Fish", "Crab", "Pearl", "Dye"],
    "Mine": ["Ore", "Gem", "Gold", "Silver", "Salt", "Jade"],
    "Quarry": ["Marble"],
    "Lumbermill": ["Ebony"],
    "Urban (no tile improvement)": ["Literature", "Porcelain", "Perfume",
                                    "Wootz_Steel", "Silphium"],
}


def caps_and_cities(xbytes: bytes):
    r = ET.fromstring(xbytes)
    W = int(r.attrib["MapWidth"])
    names = {p.attrib.get("ID"): (p.attrib.get("Name") or "?")
             for p in r.findall("Player")}
    cap, cities = {}, []
    for c in r.findall("City"):
        tid = int(c.attrib["TileID"])
        cities.append((tid % W, tid // W))
        pl = c.attrib.get("Player")
        if pl not in names:
            continue
        first = c.findtext("FirstPlayer")
        founded = int(c.attrib.get("Founded", "999999"))
        is_cap = c.find("Capital") is not None
        score = (0 if (is_cap and first == pl) else 1, founded)
        if pl not in cap or score < cap[pl][0]:
            cap[pl] = (score, tid)
    pls = sorted(cap)
    A = (cap[pls[0]][1] % W, cap[pls[0]][1] // W)
    B = (cap[pls[1]][1] % W, cap[pls[1]][1] // W)
    return [A, B], cities, [names[p] for p in pls]


def slugify(s: str) -> str:
    s = "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s


def one(zp: str) -> dict | None:
    fn = os.path.basename(zp).replace(".zip", "")
    rec = analyze(zp)
    if rec is None:
        print(f"  skip (no analyze): {fn}")
        return None
    z = zipfile.ZipFile(zp)
    xbytes = z.read([n for n in z.namelist() if n.endswith(".xml")][0])
    caps, cities, pnames = caps_and_cities(xbytes)
    slug = slugify(fn)
    IMG.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", suffix=".xml", delete=False) as tf:
        tf.write(xbytes)
        tmp = tf.name
    # city SITES only (consistent with the sweep maps); founded cities
    # overlaid on top produced confusing "double" pips.
    render(tmp, IMG / f"{slug}.png", 9, caps=caps)
    render_pretty(tmp, IMG / f"{slug}-pretty.png", 26, caps=caps)
    os.unlink(tmp)
    rec.update({"slug": slug, "file": fn, "img": f"oneoff/{slug}.png",
                "imgPretty": f"oneoff/{slug}-pretty.png",
                "caps": caps, "players": pnames, "cityCount": len(cities)})
    print(f"  {fn}: {rec['matchup']} {rec['script']}/{rec['size']} "
          f"sites={rec['citySites']} land={rec['land']} "
          f"conn={rec['landConnected']}")
    return rec


def main():
    zps = sorted(glob.glob(str(ONE / "*.zip")),
                 key=os.path.getmtime, reverse=True)
    if not zps:
        print("no saves in one-offs/")
        return 1
    recs = [r for r in (one(z) for z in zps) if r]
    (ATLAS / "src" / "data" / "oneoffs.json").write_text(
        json.dumps({"maps": recs,
                    "resTax": list(RES_BY_IMP.items())},
                   indent=1, sort_keys=True) + "\n")
    print(f"→ oneoffs.json ({len(recs)} maps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
