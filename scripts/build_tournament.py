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
from parse_map import parse_map                                # noqa: E402
import tempfile                                                # noqa: E402

EXAMPLES = ATLAS / "examples" / "unpacked"
RT = ("RiverW", "RiverSW", "RiverSE", "RiverE", "RiverNW", "RiverNE")


def analyze(zp: str) -> dict | None:
    z = zipfile.ZipFile(zp)
    xn = [n for n in z.namelist() if n.endswith(".xml")][0]
    xbytes = z.read(xn)
    # reuse parse_map for terrain / resources / 5+ & 8+ yield / tribes
    with tempfile.NamedTemporaryFile("wb", suffix=".xml", delete=False) as tf:
        tf.write(xbytes)
        _tmp = tf.name
    try:
        pm = parse_map(_tmp)
    except Exception:
        pm = {}
    finally:
        try:
            os.unlink(_tmp)
        except OSError:
            pass
    r = ET.fromstring(xbytes)
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

    cs = pm.get("citySiteCount") or sum(
        1 for t in r.findall("Tile") if t.find("CitySite") is not None)
    tribes = [k.replace("TRIBE_", "").title() for k in pm.get("tribes", [])]
    pct = pm.get("pct", {})
    y5 = pm.get("yield5", {})
    y8 = pm.get("yield8", {})
    res = pm.get("resources", {})

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
    mc = re.match(r"match_(\d+)_(.+)", fn)        # Challonge bundle
    mn = re.match(r"(\d+)-(.+)", fn)              # legacy NN-a-b
    if mc:
        gid = mc.group(1); rest = mc.group(2)
    elif mn:
        gid = mn.group(1); rest = mn.group(2)
    else:
        gid = fn; rest = fn
    matchup = " v ".join(names[p] for p in pls)   # from save Player names
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
        "tribeCount": len(tribes),
        "tribes": tribes,
        "oceanPct": round(pct.get("ocean", 0) + pct.get("lake", 0), 1),
        "forestPct": round(pct.get("forest", 0) + pct.get("jungle", 0), 1),
        "hillPct": round(pct.get("hill", 0), 1),
        "mountainPct": round(pct.get("mountain", 0) + pct.get("volcano", 0), 1),
        "resourceCount": sum(res.values()),
        "resources": {k.replace("RESOURCE_", "").title(): v
                      for k, v in sorted(res.items(), key=lambda x: -x[1])},
        "yield5": y5, "yield8": y8,
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
    # prefer named files over generic (save.zip / *Auto* / Final save)
    def rank(p):
        b = os.path.basename(p).lower()
        return 1 if ("_save.zip" in b or "auto" in b or "final save" in b
                     or b.endswith("/save.zip")) else 0
    files.sort(key=rank)
    by_id = {}
    for f in files:
        try:
            g = analyze(f)
        except Exception as e:
            print(f"  ! {os.path.basename(f)}: {e}", file=sys.stderr)
            continue
        if not g:
            continue
        if g["id"] not in by_id:          # dedupe: 1 game per match id
            by_id[g["id"]] = g
    games = list(by_id.values())
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
