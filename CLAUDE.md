# CLAUDE.md — agent guide for owtournamentatlas

Empirical Old World **tournament map analysis** site. We headlessly
generate hundreds of maps per config, measure them, and render a
distribution view so the organisers can pick fair tournament settings
and vote on a pool.

**Live:** https://alcaras.github.io/owtournamentatlas/ ·
**Source:** https://github.com/alcaras/owtournamentatlas (Astro →
GH Actions → GH Pages)

---

## Repos & their roles (LOAD-BEARING)

| Repo (sibling dirs under `cc/`) | Role | Push? |
|---|---|---|
| `owtournamentatlas` | The Astro site + generated data + committed art | **push** (deploys) |
| `owmapgen-lab` | Data lab: sweep/aggregate scripts, XML cache, samples | **local only — never push** |
| `owmapgen` | Headless .NET/mono OW map generator (patched `Program.cs`) | **local only — never push** |
| `owreference` | Unrelated sibling project (its own CLAUDE.md) | n/a |

- **Git identity:** commit/push as `alcaras <alcaras@subcreation.net>`.
  **Never** commit as the personal Dominik identity / dominik@rabiej.com.
  Both repos already have this set locally.
- **Keep-local rule:** `owmapgen`, `owmapgen-lab`, and any ELO data stay
  on disk. Commit them *locally* (preserve work) but **do not push**.
  Only `owtournamentatlas` is pushed.
- `owtournamentatlas/one-offs/*.zip` are the user's private game saves —
  **never commit**. `notes/` is gitignored (kept local).

---

## Pipeline

```
owmapgen-lab/scripts/
  configs.py         single source of truth: BASE × {size,aspect,sym}
                     expansion, filtered by the KEEP allowlist
  sweep_all.py [N]   gen+parse+render each (config × seed); appends
                     data/samples/samples.jsonl; caches gz XML.
                     INCREMENTAL: keyed on (slug,seed,binary-stamp)
  build_gen_tiles.py cached gz XML → per-gen tile JSON
                     (owtournamentatlas/public/data/gen/<id>.json)
  build_dist.py      samples.jsonl → src/data/atlas-dist.json
                     + src/data/gens.json (pure aggregation, ms)
owtournamentatlas:  npx astro build → dist/ → push → GH Actions
```

Typical change → `build_dist.py` (+ `build_gen_tiles.py` if tile JSON
changed) → `npx astro build` → commit+push atlas, commit lab locally.

### The XML cache is the durable win

`sweep_all.py` keeps `owmapgen-lab/data/maps/<slug>-s<seed>.xml.gz`.
Visual/metric-only changes re-run `build_gen_tiles.py` in **minutes**,
not a ~70-min full sweep. **Maps are deterministic** in
`(script,size,aspect,sym,opts,seed)` — the slug is only a label/key.
So renaming a config's slug == regenerating it: rename the cache +
samples + gen JSON instead of re-running owmapgen (see the Desert
rename precedent).

`sweep_all.py` invokes owmapgen from `c["script"/size/aspect/sym/opts]`,
**not** the slug. It is incremental — only (slug,seed) pairs absent for
the current binary stamp are generated; stale-stamp lines are pruned.

---

## configs.py — the pool

`BASE` = list of `(group, variant, script, [opts], sizes)`. `_expand()`
crosses each over `ASPECTS × SYMS` (DOTA is locked `sym=True` in-game)
and `sizes` (`D`=Duel/smallest, `T`=Tiny, `DT`=both).

**`KEEP`** is a frozenset allowlist: only those slugs are surfaced.
After the organiser vote pass we dropped every "no" and kept the
like+maybe survivors (+ the canonical Duel/square/point-sym variant per
script). `_expand()` skips any slug not in `KEEP`. **Clear `KEEP`
(empty set) to vote on the full universe again.** Changing `KEEP`
needs no re-sweep — `build_dist.py` filters slugs not in `CONFIGS`;
dropped configs' samples/cache/gen JSON simply go unused. (`gens.json`
is *not* KEEP-filtered, so `/gen/<id>` pages still exist for dropped
configs via direct URL — harmless, just unlinked from `/recommended`.)

---

## Data model essentials (don't re-derive)

- **Game yields are ×10:** `YIELD_SCIENCE +10` → "+1". Divide for display.
- **Yield model** (`yield_model.py`): considers ALL `IMPROVEMENT_*`,
  multi-yield, with a resource-reveal floor for resource improvements
  (Pasture/Camp/Nets/Grove have no base). Mountain/volcano are
  **un-improvable** (excluded — a Quarry there was phantom stone).
  Nets work on water (don't exclude water tiles).
- **Resource→improvement taxonomy:** `owmapgen-lab/scripts/res_tax.py`
  `RES_BY_IMP` is the *single source*. Both `build_dist.py` and the
  atlas `build_oneoff.py` import it (`from res_tax import RES_BY_IMP`).
  A prior cross-package import failed silently → empty pills; don't
  reintroduce that.
- **Capital placement:** owmapgen `Program.cs` exports player starts =
  deterministic west-most valid city-site anchor + the game's exact
  symmetric transform. Verified east-west symmetric. (Don't call
  MirrorPlayerStarts — it threw IndexOutOfRange and aborted export.)
- **Pool is connected-only by construction.** owmapgen never checks
  anchor↔partner land connection and `--connected-starts` is a no-op
  headless (spot-tested: byte-identical maps off/on). The sweep applies
  `connected_starts.reselect_connected_starts()` — picks the west-most
  city-site anchor whose *exact owmapgen symmetric partner* is land-
  connected, using `parse_map`'s own `_odd_r_neighbors` + walkable rule
  (selection oracle == measurement oracle → connPct 100, not hoped-for),
  and rewrites `<PlayerStarts>` before parse/render/cache. Seeds with no
  connected pair at any city site are genuinely split → dropped (no
  sample line; incremental sweep tolerates absent (slug,seed)). Don't
  reimplement that BFS in C# — drift would make connPct unverifiable.
- **`connPct` is now ~100 everywhere; use `dropPct` as the split
  signal.** `dropPct` (atlas-dist, from `build_dist`) = % of attempted
  seeds genuinely split (no connected sym pair) — the split-proneness
  metric that *replaces* the old as-dealt connPct. As-dealt pool is
  recoverable from owmapgen-lab git (`f4185e9:data/samples/samples.jsonl`).
  `render_recs.py` applies the same gate too, so `recommendations.json`
  + `public/img/rec/` previews are connected-only as well. The
  /recommended page shows `dropPct` (Split-dropped % pill, `dropClass`
  colour) instead of the now-constant connPct. `calibration.astro` is
  intentionally untouched — it's real `tournament-games.json` outcomes,
  not the synthetic pool, so its per-game Conn stays meaningful.
- **`reachPct` / `split`:** BFS from `caps[0]` over walkable land
  (water + mountain/volcano + lake + boundary impassable). `split` =
  reachPct < 85. **Split is a separate signal from land-connected** —
  a map can be land-connected between capitals yet still split (a big
  unreachable landmass). Split must NOT override "land-connected".
- **`capPath`:** shortest cap→cap land-hex path, same adjacency/land
  rules as the reach BFS (so it stays coherent). `[]` if none.
- **owmapgen has no `HEIGHT_OCEAN`** — all sea is `HEIGHT_COAST`.
  Derive ocean/coast/lake by land-adjacency for rendering.
- **River borders:** a tile a river *borders* counts as a river tile
  (own W/SW/SE edge OR a neighbour's) — OW only stores W/SW/SE edges.
- **even-r vs odd-r:** the lab model uses `_odd_r_neighbors`
  consistently; any new path/adjacency code must reuse it so it stays
  coherent with `reachPct`. (owreference is the project that uses
  even-r — different codebase, don't conflate.)
- Yield buckets are exact (5..12, index 0..7; ≥12 in the last). The
  table is cumulative-readable: "6+" includes 8, etc.

---

## Vote system

- Client-side only. `localStorage` key `ow_votes_v1`, per config slug.
- Side nav (`/recommended`): pinned, full-width content, `voted X / N`,
  colour-coded like/maybe/no tally pills, ✓ on a category heading when
  all its maps are voted, "✓ all in" when every config is voted.
- **COPY VOTES → clipboard, format `OW-VOTES v3`:**
  ```
  OW-VOTES v3
  n: 52
  like: slugA,slugB,…
  maybe: …
  no: …
  OW-VOTES END
  ```
  One line per non-empty category, comma-joined **slugs** (the stable
  join key — labels dropped, derive from slug). Sentinels let 6 pasted
  ballots concatenate unambiguously. No voter name (attribute via the
  Discord message author). When aggregating: split on the sentinels,
  map slug→label from `atlas-dist.json`, tally per slug.
- **Aggregation tool: `scripts/tally_votes.py`** (committed; generic, no
  private data). Reads `notes/ballots.txt` (gitignored) — paste every
  voter's whole Discord block in, any order; sentinels delimit ballots so
  names/timestamps between them are ignored. Rerun on each new ballot;
  no rebuild. Scoring **like=3 / maybe=1 / no=0**; tiebreakers
  score→likes→maybes→slug. Prints scored ranking (`=` marks tied
  scores), per-config `L/M/N` tally, unanimous-LIKE list, and
  like-vs-no conflict list. A config a voter omits counts as a
  flagged no-vote (don't let partial ballots silently skew scores).
  Pool is 6 voters → max score 18; with few ballots expect flat
  score tiers (don't draw a hard top-N line until the spread emerges).

---

## UX / rendering rules (don't relitigate)

1. **DOTA** is grouped by subtype headings (`DOTA · Jungle/Mountain/
   Water/Sand`); **Desert** by coast (`Desert: Lush/Dry/No Coast`).
   See `dg()` in `recommended.astro`.
2. The map name is **"Desert"**, not "Lush Desert" — *Lush* is the
   coast map-option, encoded in the variant.
3. **Astro scoped `<style>` does not match JS-built DOM.** The resource
   panel + anything built via `createElement`/`set:html` needs
   `:global(...)` selectors or it renders unstyled. (This bit us twice:
   the /recommended pills and the /gen resource pills.)
4. Resource pills = one-off look: rounded, resource **icon inside**,
   grouped by improvement, grey = absent. Icons at
   `public/img/icons/resources/<slug>.png`; yields at
   `…/yields/<food|iron|stone|wood>.png`. Marble→stone, Ore→iron
   icon aliases (game uses `RESOURCE_STONE/IRON` zIcon for them).
5. `/gen/<id>` canvas: water by land-adjacency (ocean deep / coast /
   lake distinct); hover a hex → tooltip + highlight; hover a resource
   hex → highlight all of that type (respects a pinned resource);
   hover a **capital** → draw `capPath` + path length in tooltip;
   wheel zoom + drag pan; reset-view button.
6. Calibration page: plain table, **no** ideal/acceptable highlighting
   or legend (the criteria are targets, not gates — see below).

---

## Tournament criteria — TARGETS, not gates

Ideal **18–22** city sites (15–25 acceptable); capitals
land-connected; land-hex distance **~45–65** (40–70 tolerable). These
are settings we tuned toward, *not* pass/fail — of 52 real games only
~35% hit all three. **Hard reroll triggers only:** no land connection;
SPLIT (significant land unreachable); absurd sites (<12 / >30).
Everything else: play as dealt. Prize **consistency** (low sd) for a
blind, no-screen tournament.

---

## Pitfalls already discovered (don't re-debug)

- **Bash cwd resets** between tool calls — use `git -C <path>` /
  absolute paths; don't rely on a prior `cd`.
- `build_dist.py` writes `atlas-dist.json` only **after** reach/split
  aggregation (was writing it before → null reachMean/splitPct).
- `render_pretty.py` had a dangling `@lru_cache` above a comment+assign
  → SyntaxError that crashed the whole sweep. Decorator goes on the
  function, not a bare assignment.
- Renaming a slug means renaming **4 artifact sets** consistently:
  `samples.jsonl` (slug/label/group/img), `data/maps/*.xml.gz`,
  `public/img/atlas/<slug>/`, `public/data/gen/<id>.json` (delete stale
  — `build_gen_tiles.py` does not clean output).
- Don't add yield aliases for combat words; mountain/volcano are not
  improvable; honest "misc" beats a wrong colour. (Same spirit as the
  owreference rules.)

---

## Source-of-truth rules

1. **XML/samples win on facts.** The site is a deterministic projection
   of generated maps. `atlas-dist.json` / per-gen JSON are generated —
   never hand-edit; change the script and rebuild.
2. `configs.py` is the only place the pool is defined. `res_tax.py` is
   the only place the resource taxonomy is defined.
3. The `xlsx`/legacy calibration is read-only history.
