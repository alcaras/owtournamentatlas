#!/usr/bin/env python3
"""
build_atlas_data.py — owmapgen-lab atlas.json → src/data/atlas-all.json
(all 13 scripts, data only: city sites + capital-distance suite).
"""
from __future__ import annotations
import datetime, glob, json, sys
from pathlib import Path

ATLAS = Path(__file__).resolve().parent.parent
LAB = ATLAS.parent / "owmapgen-lab"


def slugify(s: str) -> str:
    return s.lower().replace(" ", "-")


def main() -> int:
    files = sorted(glob.glob(str(LAB / "data" / "atlas" / "*" / "atlas.json")))
    if not files:
        sys.exit("no atlas.json — run atlas_sweep.py")
    d = json.loads(Path(files[-1]).read_text())
    scripts = []
    for s in d["scripts"]:
        scripts.append({
            "label": s["label"],
            "slug": slugify(s["label"]),
            "cells": s["cells"],
        })
    scripts.sort(key=lambda x: x["label"])
    payload = {
        "generatedAt": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "owmapgenSha": d["owmapgenSha"],
        "atlasId": d["atlasId"],
        "seedsPerCell": d["seedsPerCell"],
        "target": d["target"], "accept": d["accept"],
        "scripts": scripts,
    }
    out = ATLAS / "src" / "data" / "atlas-all.json"
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"✓ {out.relative_to(ATLAS)} — {len(scripts)} scripts, "
          f"{sum(len(s['cells']) for s in scripts)} cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
