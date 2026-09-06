#!/usr/bin/env python3
"""Quick Highlands probe: n=3 seeds × {smallest,tiny} × {square,wide}
× point-sym{on,off} = 8 configs. Generates into highlands/maps/, applies
the same connected-starts reselection as the real sweep, parses, and
prints a sites + land-distance summary comparable to the pool. Not part
of the pipeline — a scratch check (highlands/ is gitignored-style scratch).
"""
import statistics as st, subprocess, sys
from pathlib import Path

LAB = Path("/Users/dominik/Dropbox/cc/owmapgen-lab")
OW = LAB.parent / "owmapgen" / "owmapgen"
OUT = Path("/Users/dominik/Library/CloudStorage/Dropbox/cc/owtournamentatlas/highlands/maps")
sys.path.insert(0, str(LAB / "scripts"))
from parse_map import parse_map
from connected_starts import reselect_connected_starts

ENV = {"PATH": "/opt/homebrew/bin:/usr/bin:/bin"}
import os
ENV = {**os.environ, "PATH": "/opt/homebrew/bin:" + os.environ.get("PATH", "")}
SEEDS = [1, 2, 3]


def gen(size, aspect, sym, seed, td):
    cmd = [str(OW), "--script", "Highlands", "--size", size,
           "--players", "2", "--seed", str(seed),
           "--aspect-ratio", aspect, "--mirror", "--output", str(td)]
    if sym:
        cmd.append("--point-symmetry")
    subprocess.run(cmd, capture_output=True, text=True, env=ENV)
    xs = sorted(Path(td).glob("*.xml"), key=lambda p: p.stat().st_mtime)
    return xs[-1] if xs else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for size in ("smallest", "tiny"):
        for aspect in ("square", "wide"):
            for sym in (True, False):
                tag = (f"highlands-{ 'duel' if size=='smallest' else 'tiny'}"
                       f"-{aspect}-{'sym' if sym else 'nosym'}")
                sites, lands, conn, dropped = [], [], 0, 0
                for seed in SEEDS:
                    td = OUT / tag
                    td.mkdir(exist_ok=True)
                    xml = gen(size, aspect, sym, seed, td)
                    if not xml:
                        dropped += 1
                        continue
                    if not reselect_connected_starts(xml, sym):
                        dropped += 1          # no connected pair → split
                        continue
                    r = parse_map(xml)
                    sites.append(r["citySiteCount"])
                    lands.append(r["capitalLandPath"] or 0)
                    conn += 1 if r["capitalLandConnected"] else 0
                rows.append((tag, sites, lands, conn, dropped))

    def f(v):
        if not v:
            return "  —  "
        return (f"{st.mean(v):4.1f}±{(st.pstdev(v) if len(v)>1 else 0):.1f} "
                f"[{min(v)},{max(v)}]")
    print(f"Highlands quick check — n={len(SEEDS)} seeds/config "
          f"(connected-starts reselected, like the real sweep)\n")
    print(f"{'config':28} {'n':>2}  {'sites':16} {'land hex':16} drop")
    print("-" * 72)
    for tag, sites, lands, conn, dropped in rows:
        print(f"{tag:28} {len(sites):>2}  {f(sites):16} {f(lands):16} {dropped}")


if __name__ == "__main__":
    main()
