#!/usr/bin/env python3
"""
build_tournament.py — parse the completed tournament save files into
src/data/tournament-games.json for the calibration page.

For each save: ID (filename prefix), matchup, map script/size/aspect,
city-site count, and capital-to-capital distances using the SAME
even-r model as the atlas (crow-flies hex, land path, land-connected,
Scout orders, Slinger land/sea/Hatti).

Capital = each real player's *original* capital (the <Capital/> city
they founded, FirstPlayer == player) — robust to captures/relocations.
"""
from __future__ import annotations

import collections
import glob
import io
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ATLAS = Path(__file__).resolve().parent.parent
LAB = ATLAS.parent / "owmapgen-lab"
sys.path.insert(0, str(LAB / "scripts"))
from parse_map import hex_distance, _odd_r_neighbors          # noqa: E402
from movement_model import slinger_turns, _costs              # noqa: E402

EXAMPLES = ATLAS / "examples" / "unpacked"
RT = ("RiverW", "RiverSW", "RiverSE", "RiverE", "RiverNW", "RiverNE")


def analyze(zp: str) -> dict | None:
    z = zipfile.ZipFile(zp)
    xn = [n for n in z.namelist() if n.endswith(".xml")][0]
    r = ET.parse(io.BytesIO(z.read(xn))).getroot()
    W = int(r.attrib["MapWidth"])
    names = {p.attrib.get("ID"): (p.attrib.get("Name") or "?")
             for p in r.findall("Player")}

    grid = {}
    for t in r.findall("Tile"):
        tid = int(t.attrib["ID"])
        grid[(tid % W, tid // W)] = (
            t.findtext("Terrain") or "?", t.findtext("Height") or "",
            t.findtext("Vegetation") or "", t.findtext("Resource"),
            any(t.find(k) is not None for k in RT))

    # original capital per real player: <Capital/> with FirstPlayer==Player
    cap = {}
    for c in r.findall("City"):
        pl = c.attrib.get("Player")
        if pl not in names:
            continue
        first = c.findtext("FirstPlayer")
        founded = int(c.attrib.get("Founded", "999999"))
        is_cap = c.find("Capital") is not None
        tid = int(c.attrib["TileID"])
        score = (0 if (is_cap and first == pl) else 1, founded)
        if pl not in cap or score < cap[pl][0]:
            cap[pl] = (score, tid)
    pls = sorted(cap)
    if len(pls) < 2:
        return None
    a = cap[pls[0]][1]
    b = cap[pls[1]][1]
    A, B = (a % W, a // W), (b % W, b // W)

    cs = sum(1 for t in r.findall("Tile") if t.find("CitySite") is not None)

    landok, waterok = set(), set()
    for (x, y), (te, h, *_rest) in grid.items():
        if h in ("HEIGHT_MOUNTAIN", "HEIGHT_VOLCANO"):
            continue
        waterok.add((x, y))
        if te == "TERRAIN_WATER" or h in ("HEIGHT_OCEAN", "HEIGHT_COAST", "HEIGHT_LAKE"):
            continue
        landok.add((x, y))

    def bfs(ok):
        ok = ok | {A, B}
        seen = {A}
        q = collections.deque([(A, 0)])
        while q:
            cur, d = q.popleft()
            if cur == B:
                return d
            for nb in _odd_r_neighbors(*cur):
                if nb in ok and nb not in seen:
                    seen.add(nb)
                    q.append((nb, d + 1))
        return None

    mv = _costs()

    def turns(**kw):
        v, _ = slinger_turns(grid, A, B, **kw)
        return v

    fn = os.path.basename(zp).replace(".zip", "")
    m = re.match(r"(\d+)-(.+)", fn)
    gid = m.group(1) if m else fn
    matchup = (m.group(2) if m else fn).replace("_", " ").replace("-", " v ", 1)
    land = bfs(landok)
    return {
        "id": gid,
        "file": fn,
        "matchup": " v ".join(names[p] for p in pls),
        "label": matchup,
        "script": r.attrib.get("MapClass", "").replace("MAPCLASS_MapScript", "").replace("MAPCLASS_", ""),
        "size": r.attrib.get("MapSize", "").replace("MAPSIZE_", ""),
        "aspect": r.attrib.get("MapAspectRatio", "").replace("MAPASPECTRATIO_", ""),
        "citySites": cs,
        "crow": hex_distance(A, B),
        "land": land,
        "landConnected": land is not None,
        "sea": bfs(waterok),
        "scout": turns(move=mv["scout"]),
        "slingerLand": turns(move=mv["slinger"]),
        "slingerSea": turns(move=mv["slinger"], allow_water=True),
        "slingerHatti": turns(move=mv["slinger"], ignore_hill=True),
    }


def main() -> int:
    files = sorted(glob.glob(str(EXAMPLES / "**" / "*.zip"), recursive=True))
    games = []
    for f in files:
        try:
            g = analyze(f)
            if g:
                games.append(g)
        except Exception as e:
            print(f"  ! {os.path.basename(f)}: {e}", file=sys.stderr)
    games.sort(key=lambda g: (len(g["id"]), g["id"]))
    out = ATLAS / "src" / "data" / "tournament-games.json"
    out.write_text(json.dumps({"count": len(games), "games": games}, indent=2) + "\n")
    print(f"✓ {out.relative_to(ATLAS)} — {len(games)} games")
    for g in games:
        print(f"  {g['id']:>3} {g['matchup'][:24]:24} {g['script']:14}/{g['size']:8}/{g['aspect']:9} "
              f"sites={g['citySites']:<3} crow={g['crow']:<3} land={g['land']} "
              f"conn={'Y' if g['landConnected'] else 'N'} scout={g['scout']} slL={g['slingerLand']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
