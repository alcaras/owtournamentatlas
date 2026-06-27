# Map config label spec (owtournamentatlas)

Canonical, copy-pasteable spec for naming a tournament map config. Use
this so **every page** (`index.astro`, `rankings.astro`, `round-2.astro`,
`recommended.astro`, `[script].astro`, `/gen`, `/oneoff`, etc.) shows the
**same** label for the same config.

Reference implementation lives in `src/pages/index.astro` (the
`cfgLabel()` function + `SCRIPT_FULL`/`SCRIPT_SHORT` tables). If you
change the rules, change them there first and update this file.

---

## 1. Format

```
[Aspect] [Size] [Map Script] [Option] [PS]
```

Two forms per config:

- **Full** — card titles, anywhere with room. Script spelled out, aspect
  spelled out. e.g. `Square Duel Coastal Rain Basin PS`
- **Compressed** — sidebars, chips/tags, narrow columns, Discord. Script
  abbreviated, `Square`→`Sq`. e.g. `Sq Duel CRB PS`

Only the **Map Script abbreviation** and **`Square`→`Sq`** differ between
the two forms. Everything else (Size, Option, PS) is identical.

---

## 2. Inputs (normalize your data source to these)

Each config has these axes (this is what `configs.py` emits; `slug` is the
stable join key across pages):

| field | values |
|---|---|
| `slug` | stable id, e.g. `coastal-rain-basin-smallest-square-sym` |
| `group` | map-script family name, e.g. `Coastal Rain Basin`, `DOTA` |
| `variant` | option string, e.g. `Large Seas`, `Jungle`, `Lush · Std`, `Land Lg · Water Sm`, or `''` |
| `size` | `smallest` (=Duel) or `tiny` (=Tiny) |
| `aspect` | `square` or `wide` |
| `sym` | boolean — point symmetry on/off (mirror is always on, separately) |

If your data only has the `setting` string
(`"Duel · square · point-sym off · mirror"`), derive:
`size` = part[0] (`Duel`/`Tiny`), `aspect` = part[1] (`square`/`wide`),
`sym` = part[2].includes('on'). (`index.astro` does this via the
`sizeOf` / `aspOf` / `symOf` helpers.)

---

## 3. Rules

1. **Aspect** → `Square`/`Wide` (full), `Sq`/`Wide` (compressed). Always
   shown.
2. **Size** → `Duel` (size `smallest`) or `Tiny` (size `tiny`). Always
   shown, same in both forms.
3. **Map Script** → from the lookup tables in §4. Full vs compressed
   picks the column.
4. **Option** — shown **only when it varies across the pool** for that
   script (so single-variant scripts like Archipelago and Donut omit it
   as noise). Mapping:
   - **DOTA** → the boundary terrain: `Jungle` / `Sand` / `Water` / `Mountain`.
   - **Arid Plateau** → `Large Seas` / `Small Seas`.
   - **Desert** → the coast only: `Lush` / `Dry` / `No Coast` (the
     `variant` is `Lush · Std` etc — take the part before ` · `, and map
     `None` → `No Coast`).
   - everything else → omit.
   "Varies across the pool" = more than one distinct `variant` exists
   among the surfaced configs of that `group`. Compute it from the data,
   don't hardcode, so it stays correct if the pool changes.
5. **PS** — append `PS` **iff** `sym === true` **AND** `group !== 'DOTA'`.
   - DOTA is point-sym-locked in-game (it's a default, not a toggle), so
     PS is implied and **omitted** for DOTA.
   - **Mirror is always on** and is **never** shown.
6. Join the non-empty parts with single spaces.

---

## 4. Map Script lookup tables

```js
const SCRIPT_FULL = {
  'Archipelago': 'Archipelago', 'Arid Plateau': 'Arid Plateau',
  'Coastal Rain Basin': 'Coastal Rain Basin', 'Continent': 'Continent',
  'Desert': 'Desert', 'Donut': 'Donut', 'DOTA': 'DOTA',
  'Hardwood Forest': 'Hardwood Forest', 'Highlands': 'Highlands',
  'Inland Sea': 'Inland Sea', 'Mountain Pass': 'Mountain Pass',
  'Wetlands': 'Wetlands',
};
const SCRIPT_SHORT = {
  'Archipelago': 'Arch', 'Arid Plateau': 'AridP',
  'Coastal Rain Basin': 'CRB', 'Continent': 'Cont', 'Desert': 'Desert',
  'Donut': 'Donut', 'DOTA': 'DOTA', 'Hardwood Forest': 'Hardwood',
  'Highlands': 'Highlands', 'Inland Sea': 'InlSea',
  'Mountain Pass': 'MtnPass', 'Wetlands': 'Wetlands',
};
```

Unknown `group` → fall back to the `group` string verbatim (and log it,
so the table gets updated). Keep both tables in sync when a new script is
added.

---

## 5. Reference implementation (JS/TS, source-agnostic)

```js
// `pool` = the array of surfaced configs (each with group/variant and
// either size/aspect/sym fields or a `setting` string you parsed).
function buildLabeler(pool) {
  // which groups have >1 variant in the pool → their option is meaningful
  const multiVariant = new Set();
  const seen = {};
  for (const c of pool) (seen[c.group] ??= new Set()).add(c.variant || '');
  for (const g in seen) if (seen[g].size > 1) multiVariant.add(g);

  const optionLabel = (c) => {
    if (!multiVariant.has(c.group)) return '';
    if (c.group === 'Desert') {
      const coast = (c.variant || '').split(' · ')[0];
      return coast === 'None' ? 'No Coast' : coast;     // Lush / Dry / No Coast
    }
    return c.variant || '';                              // Large Seas / Jungle / …
  };

  return (c, short = false) => {
    const asp  = c.aspect === 'wide' ? 'Wide' : (short ? 'Sq' : 'Square');
    const size = c.size === 'tiny' ? 'Tiny' : 'Duel';
    const tbl  = short ? SCRIPT_SHORT : SCRIPT_FULL;
    const script = tbl[c.group] || c.group;
    const opt = optionLabel(c);
    const ps  = (c.sym && c.group !== 'DOTA') ? 'PS' : '';
    return [asp, size, script, opt, ps].filter(Boolean).join(' ');
  };
}

// usage:
// const label = buildLabeler(pool);
// label(cfg)        -> full     "Square Duel Coastal Rain Basin PS"
// label(cfg, true)  -> compressed "Sq Duel CRB PS"
```

Notes:
- `multiVariant` is computed from the data, not hardcoded — pass the same
  config set a page surfaces so "option shown?" stays correct.
- Labels are **descriptive, not positional**: derived purely from the
  config's axes. Two configs only collide if they share
  group+size+aspect+sym+variant — none do in the current pool.
- The `slug` remains the stable join key; the label is for display only.

---

## 6. The 18-config pool (golden output — verify against this)

| slug | Full | Compressed |
|---|---|---|
| `archipelago-land-lg-water-sm-smallest-square-sym` | Square Duel Archipelago PS | Sq Duel Arch PS |
| `archipelago-land-lg-water-sm-smallest-wide-nosym` | Wide Duel Archipelago | Wide Duel Arch |
| `arid-plateau-large-seas-smallest-square-sym` | Square Duel Arid Plateau Large Seas PS | Sq Duel AridP Large Seas PS |
| `arid-plateau-small-seas-smallest-square-sym` | Square Duel Arid Plateau Small Seas PS | Sq Duel AridP Small Seas PS |
| `coastal-rain-basin-smallest-wide-nosym` | Wide Duel Coastal Rain Basin | Wide Duel CRB |
| `coastal-rain-basin-smallest-square-sym` | Square Duel Coastal Rain Basin PS | Sq Duel CRB PS |
| `continent-smallest-wide-sym` | Wide Duel Continent PS | Wide Duel Cont PS |
| `desert-lush-std-tiny-square-nosym` | Square Tiny Desert Lush | Sq Tiny Desert Lush |
| `desert-none-std-tiny-square-sym` | Square Tiny Desert No Coast PS | Sq Tiny Desert No Coast PS |
| `donut-irreg-low-smallest-square-sym` | Square Duel Donut PS | Sq Duel Donut PS |
| `dota-jungle-smallest-square-sym` | Square Duel DOTA Jungle | Sq Duel DOTA Jungle |
| `dota-sand-smallest-square-sym` | Square Duel DOTA Sand | Sq Duel DOTA Sand |
| `dota-water-smallest-square-sym` | Square Duel DOTA Water | Sq Duel DOTA Water |
| `hardwood-forest-smallest-wide-nosym` | Wide Duel Hardwood Forest | Wide Duel Hardwood |
| `inland-sea-smallest-square-sym` | Square Duel Inland Sea PS | Sq Duel InlSea PS |
| `inland-sea-smallest-wide-nosym` | Wide Duel Inland Sea | Wide Duel InlSea |
| `mountain-pass-smallest-wide-sym` | Wide Duel Mountain Pass PS | Wide Duel MtnPass PS |
| `wetlands-smallest-square-sym` | Square Duel Wetlands PS | Sq Duel Wetlands PS |

---

## 7. Edge cases / gotchas

- **Ultrawide aspect** isn't in the pool (dropped 2026-05-21) but real
  games exist on it — if you ever label one, render `Ultrawide` (full) /
  `UW` (compressed) for aspect. Not currently surfaced anywhere.
- **Highlands** is in `configs.py` but not in the surfaced pool; tables
  include it so direct `/gen` URLs still label correctly.
- **Astro scoped `<style>` does not match JS-built DOM** — if you inject
  a label via `createElement`/`set:html`, style it with `:global(...)`.
- Don't invent new abbreviations ad hoc — add them to §4 here and to
  `SCRIPT_FULL`/`SCRIPT_SHORT` in `index.astro` so all pages agree.
</content>
