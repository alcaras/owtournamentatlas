#!/usr/bin/env python3
"""
build_oneoff.py — render + stat a single save dropped in one-offs/.
Reuses the calibration analyzer (analyze) for the full metric set, then
draws a detailed hex map with both original capitals marked. Emits
src/data/oneoff.json + public/img/oneoff/<slug>.png.
"""
from __future__ import annotations
import glob, json, os, sys, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ATLAS = Path(__file__).resolve().parent.parent
LAB = ATLAS.parent / "owmapgen-lab"
sys.path.insert(0, str(LAB / "scripts"))
sys.path.insert(0, str(ATLAS / "scripts"))
from build_tournament import analyze            # noqa: E402
from render_map import render                   # noqa: E402

ONE = ATLAS / "one-offs"
IMG = ATLAS / "public" / "img" / "oneoff"


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


def main():
    zps = sorted(glob.glob(str(ONE / "*.zip")),
                 key=os.path.getmtime, reverse=True)
    if not zps:
        print("no save in one-offs/")
        return 1
    zp = zps[0]
    fn = os.path.basename(zp).replace(".zip", "")
    rec = analyze(zp)
    if rec is None:
        print(f"could not analyze {fn}")
        return 1
    xbytes = zipfile.ZipFile(zp).read(
        [n for n in zipfile.ZipFile(zp).namelist() if n.endswith(".xml")][0])
    caps, cities, pnames = caps_and_cities(xbytes)

    slug = "".join(c if c.isalnum() else "-" for c in fn.lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    IMG.mkdir(parents=True, exist_ok=True)
    import tempfile
    with tempfile.NamedTemporaryFile("wb", suffix=".xml", delete=False) as tf:
        tf.write(xbytes)
        tmp = tf.name
    png = IMG / f"{slug}.png"
    render(tmp, png, 9, caps=caps, cities=cities)
    os.unlink(tmp)

    rec.update({
        "slug": slug, "file": fn,
        "img": f"oneoff/{slug}.png",
        "caps": caps, "players": pnames,
        "cityCount": len(cities),
    })
    (ATLAS / "src" / "data" / "oneoff.json").write_text(
        json.dumps(rec, indent=1, sort_keys=True) + "\n")
    print(f"→ oneoff.json + {png.name}  ({fn})")
    print(f"  {rec['matchup']}  {rec['script']}/{rec['size']}/{rec['aspect']}"
          f"  sites={rec['citySites']} crow={rec['crow']} land={rec['land']}"
          f" conn={rec['landConnected']} scout={rec['scout']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
