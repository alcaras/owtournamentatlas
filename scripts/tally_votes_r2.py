#!/usr/bin/env python3
"""Tally concatenated OW-VOTES-R2 ballots into a scored ranking.

Round 2 replaces Round 1: the /round-2 page emits its own
`OW-VOTES-R2 v1 … OW-VOTES-R2 END` block (separate sentinel + separate
localStorage, so Round 1 and Round 2 ballots never mix). This is the
Round 2 counterpart of tally_votes.py.

Reads notes/ballots-r2.txt (gitignored) — paste every voter's Discord
block in, one after another; the sentinels let the blocks concatenate
unambiguously. Slugs are the stable join key; labels come from
src/data/gens.json (covers all 53 configs, not just the voted pool).

Scoring (Round 2): like=+2, maybe=0, no=-1. "maybe" is a true neutral;
a "no" actively costs the config; an omitted config scores 0 (neutral)
but is still flagged separately — so "rejected" and "didn't vote" stay
distinct. Usage: python3 scripts/tally_votes_r2.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BALLOTS = ROOT / "notes" / "ballots-r2.txt"
GENS = ROOT / "src" / "data" / "gens.json"
PTS = {"like": 2, "maybe": 0, "no": -1}

BLOCK = re.compile(r"OW-VOTES-R2 v\d+(.*?)OW-VOTES-R2 END", re.S)
CAT = re.compile(r"^\s*(like|maybe|no)\s*:\s*(.*)$", re.M)


def parse_ballots(text):
    """-> list of cat_map. cat_map: slug -> like|maybe|no."""
    out = []
    for m in BLOCK.finditer(text):
        cm = {}
        for cat, rest in CAT.findall(m.group(1)):
            for slug in (s.strip() for s in rest.split(",")):
                if slug:
                    cm[slug] = cat
        if cm:
            out.append(cm)
    return out


def main():
    if not BALLOTS.exists():
        sys.exit(f"missing {BALLOTS} — paste the Discord OW-VOTES-R2 blocks there")
    text = BALLOTS.read_text()
    ballots = parse_ballots(text)
    if not ballots:
        hint = ""
        if "OW-VOTES v3" in text:
            hint = ("\n  (found Round 1 'OW-VOTES v3' blocks — those go "
                    "through tally_votes.py, not this script)")
        sys.exit(f"no OW-VOTES-R2 blocks found in {BALLOTS.name}{hint}")

    labels = {}
    for g in json.loads(GENS.read_text())["gens"]:
        labels.setdefault(g["cslug"], g["label"])

    slugs = sorted({s for b in ballots for s in b})
    rows = []
    for s in slugs:
        votes = [b.get(s) for b in ballots]
        score = sum(PTS.get(v, 0) for v in votes if v)
        tally = {k: sum(1 for v in votes if v == k) for k in PTS}
        missing = sum(1 for v in votes if v is None)
        rows.append((score, tally["like"], tally["maybe"], s, tally, missing))
    # rank: score, then likes, then maybes as tiebreakers, then slug
    rows.sort(key=lambda r: (-r[0], -r[1], -r[2], r[3]))

    n = len(ballots)
    print(f"ROUND 2 · {n} ballot(s) · {len(slugs)} configs · "
          f"score range {-n}..{2*n}  (like +2 / maybe 0 / no -1)\n")
    print(f"{'#':>3} {'pts':>3} {'L/M/N':>7}  config")
    print("-" * 78)
    prev = None
    for i, (sc, lk, mb, s, t, miss) in enumerate(rows, 1):
        tie = " " if sc != prev else "="
        prev = sc
        lmn = f"{t['like']}/{t['maybe']}/{t['no']}"
        miss_s = f"  ({miss} no-vote)" if miss else ""
        print(f"{i:>3}{tie}{sc:>3} {lmn:>7}  {s}")
        print(f"             {labels.get(s, '?')}{miss_s}")

    unan_like = [s for sc, lk, mb, s, t, m in rows if t["like"] == n]
    conflict = [(s, t) for sc, lk, mb, s, t, m in rows
                if t["like"] and t["no"]]
    print(f"\nUnanimous LIKE ({len(unan_like)}): {', '.join(unan_like) or '—'}")
    print(f"Like-vs-No conflicts ({len(conflict)}):")
    for s, t in sorted(conflict, key=lambda x: -x[1]["no"]):
        print(f"  {s}  (like {t['like']} / maybe {t['maybe']} / no {t['no']})")


if __name__ == "__main__":
    main()
