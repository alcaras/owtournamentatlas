#!/usr/bin/env python3
"""
build_atlas_data.py — turn the owmapgen-lab Continent sweep into this
site's data + preview renders.

  1. read the newest owmapgen-lab/data/atlas/*/atlas.json
  2. emit src/data/continent-atlas.json (recommended variant + all cells)
  3. regenerate N preview maps of the recommended variant and render
     them to public/img/continent/seed-*.png

Run from the owtournamentatlas repo root.
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

ATLAS = Path(__file__).resolve().parent.parent          # owtournamentatlas/
CC = ATLAS.parent
LAB = CC / "owmapgen-lab"
OWMAPGEN = CC / "owmapgen" / "owmapgen"
RENDER = LAB / "scripts" / "render_map.py"
ENV = {**os.environ, "PATH": "/opt/homebrew/bin:" + os.environ.get("PATH", "")}
N_PREVIEW = int(sys.argv[1]) if len(sys.argv) > 1 else 30


def newest_atlas() -> Path:
    files = sorted(glob.glob(str(LAB / "data" / "atlas" / "*" / "atlas.json")))
    if not files:
        sys.exit("no owmapgen-lab atlas.json found — run atlas_sweep.py first")
    return Path(files[-1])


def main() -> int:
    aj = newest_atlas()
    data = json.loads(aj.read_text())
    cont = next((s for s in data["scripts"] if s["label"] == "Continent"), None)
    if cont is None:
        sys.exit("Continent not in atlas.json")
    best = cont["best"]
    w, h = (int(x) for x in best["dims"].split("x"))
    best = {**best, "tiles": w * h}

    out_img = ATLAS / "public" / "img" / "continent"
    out_img.mkdir(parents=True, exist_ok=True)
    for old in out_img.glob("*.png"):
        old.unlink()

    # Regenerate + render N maps of the recommended variant.
    previews = []
    px = 7 if best["size"] == "smallest" else 5
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        for seed in range(1, N_PREVIEW + 1):
            cmd = [str(OWMAPGEN), "--script", "Continent", "--size", best["size"],
                   "--players", "2", "--seed", str(seed),
                   "--aspect-ratio", best["aspect"], "--mirror",
                   "--output", str(tdp)]
            if best["pointSymmetry"]:
                cmd.append("--point-symmetry")
            subprocess.run(cmd, capture_output=True, text=True, env=ENV)
            xmls = sorted(tdp.glob("*.xml"), key=lambda p: p.stat().st_mtime)
            if not xmls:
                continue
            png = out_img / f"seed-{seed}.png"
            subprocess.run(["python3", str(RENDER), str(xmls[-1]), str(png), str(px)],
                           capture_output=True, env=ENV)
            for x in xmls:
                x.unlink(missing_ok=True)
            if png.exists():
                previews.append(f"continent/seed-{seed}.png")

    payload = {
        "generatedAt": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "owmapgenSha": data["owmapgenSha"],
        "atlasId": data["atlasId"],
        "seedsPerCell": data["seedsPerCell"],
        "target": data["target"], "accept": data["accept"],
        "script": "Continent",
        "recommended": best,
        "cells": cont["cells"],
        "previews": previews,
    }
    dst = ATLAS / "src" / "data" / "continent-atlas.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"✓ {dst.relative_to(ATLAS)} — best {best['sizeLabel']}/"
          f"{best['aspect']}/sym{int(best['pointSymmetry'])} "
          f"target {best['pctTarget']}%, {len(previews)} previews")
    return 0


if __name__ == "__main__":
    sys.exit(main())
