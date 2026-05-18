#!/usr/bin/env python3
"""Tally concatenated OW-VOTES v3 ballots into a scored ranking.

Reads notes/ballots.txt (gitignored) — paste every voter's Discord block in,
one after another; the OW-VOTES v3 / OW-VOTES END sentinels let the blocks
concatenate unambiguously (see CLAUDE.md "Vote system"). Slugs are the stable
join key; labels come from src/data/atlas-dist.json.

Scoring: like=3, maybe=1, no=0. Usage: python3 scripts/tally_votes.py
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BALLOTS = ROOT / "notes" / "ballots.txt"
DIST = ROOT / "src" / "data" / "atlas-dist.json"
PTS = {"like": 3, "maybe": 1, "no": 0}

BLOCK = re.compile(r"OW-VOTES v3(.*?)OW-VOTES END", re.S)
CAT = re.compile(r"^\s*(like|maybe|no)\s*:\s*(.*)$", re.M)


def parse_ballots(text):
    """-> list of (cat_map, raw_block). cat_map: slug -> like|maybe|no."""
    out = []
    for m in BLOCK.finditer(text):
        body = m.group(1)
        cm = {}
        for cat, rest in CAT.findall(body):
            for slug in (s.strip() for s in rest.split(",")):
                if slug:
                    cm[slug] = cat
        if cm:
            out.append(cm)
    return out


def main():
    if not BALLOTS.exists():
        sys.exit(f"missing {BALLOTS} — paste the Discord OW-VOTES blocks there")
    ballots = parse_ballots(BALLOTS.read_text())
    if not ballots:
        sys.exit("no OW-VOTES v3 blocks found in ballots.txt")

    labels = {c["slug"]: c["label"] for c in json.loads(DIST.read_text())["configs"]}

    slugs = sorted({s for b in ballots for s in b})
    rows = []
    for s in slugs:
        votes = [b.get(s) for b in ballots]
        score = sum(PTS.get(v, 0) for v in votes if v)
        tally = {k: sum(1 for v in votes if v == k) for k in PTS}
        missing = sum(1 for v in votes if v is None)
        rows.append((score, tally["like"], tally["maybe"], s, tally, missing))
    # rank: score, then likes, then maybes as tiebreakers
    rows.sort(key=lambda r: (-r[0], -r[1], -r[2], r[3]))

    n = len(ballots)
    print(f"{n} ballot(s) · {len(slugs)} configs · max score {3*n}\n")
    print(f"{'#':>3} {'pts':>3} {'L/M/N':>7}  config")
    print("-" * 78)
    prev = None
    for i, (sc, lk, mb, s, t, miss) in enumerate(rows, 1):
        tie = " " if sc != prev else "="
        prev = sc
        lmn = f"{t['like']}/{t['maybe']}/{t['no']}"
        miss_s = f"  ({miss} no-vote)" if miss else ""
        lab = labels.get(s, "?")
        print(f"{i:>3}{tie}{sc:>3} {lmn:>7}  {s}")
        print(f"             {lab}{miss_s}")

    # consensus / conflict summary
    unan_like = [s for sc, lk, mb, s, t, m in rows if t["like"] == n]
    conflict = [
        (s, t) for sc, lk, mb, s, t, m in rows if t["like"] and t["no"]
    ]
    print(f"\nUnanimous LIKE ({len(unan_like)}): {', '.join(unan_like) or '—'}")
    print(f"Like-vs-No conflicts ({len(conflict)}):")
    for s, t in sorted(conflict, key=lambda x: -x[1]['no']):
        print(f"  {s}  (like {t['like']} / maybe {t['maybe']} / no {t['no']})")


if __name__ == "__main__":
    main()
