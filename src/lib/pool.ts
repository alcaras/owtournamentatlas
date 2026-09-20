// The 18-map tournament pool and its labels, shared by pages that need
// the same maps in the same order. index.astro / rankings.astro still
// carry their own copies (predating this file); keep the three in sync
// until they import from here.
export const POOL: string[] = [
  'archipelago-land-lg-water-sm-smallest-square-sym',
  'archipelago-land-lg-water-sm-smallest-wide-nosym',
  'arid-plateau-small-seas-smallest-square-sym',
  'arid-plateau-large-seas-smallest-square-sym',
  'coastal-rain-basin-smallest-wide-nosym',
  'coastal-rain-basin-smallest-square-sym',
  'continent-smallest-wide-sym',
  'desert-lush-std-tiny-square-nosym',
  'desert-none-std-tiny-square-sym',
  'donut-irreg-low-smallest-square-sym',
  'dota-jungle-smallest-square-sym',
  'dota-sand-smallest-square-sym',
  'dota-water-smallest-square-sym',
  'hardwood-forest-smallest-wide-nosym',
  'inland-sea-smallest-square-sym',
  'inland-sea-smallest-wide-nosym',
  'mountain-pass-smallest-wide-sym',
  'wetlands-smallest-square-sym',
];

export const sizeOf = (c: any) =>
  (c.setting || '').split(' · ')[0] === 'Tiny' ? 'Tiny' : 'Duel';
export const aspOf = (c: any) => {
  const a = (c.setting || '').split(' · ')[1] || '';
  return a ? a[0].toUpperCase() + a.slice(1) : '';
};
export const symOf = (c: any) =>
  ((c.setting || '').split(' · ')[2] || '').includes('on') ? 'Sym' : 'No-Sym';

const SCRIPT_SHORT: Record<string, string> = {
  'Archipelago': 'Arch', 'Arid Plateau': 'AridP',
  'Coastal Rain Basin': 'CRB', 'Continent': 'Cont', 'Desert': 'Desert',
  'Donut': 'Donut', 'DOTA': 'DOTA', 'Hardwood Forest': 'Hardwood',
  'Highlands': 'Highlands', 'Inland Sea': 'InlSea',
  'Mountain Pass': 'MtnPass', 'Wetlands': 'Wetlands',
};

// Group heading as on the pool page: DOTA by subtype, Desert by coast.
export const dg = (c: any) => {
  if (c.group === 'DOTA') return `DOTA · ${c.variant}`;
  if (c.group === 'Desert') {
    const coast = (c.variant || '').split(' · ')[0];
    return `Desert: ${coast === 'None' ? 'No' : coast} Coast`;
  }
  return c.group;
};

// "[Sq|Wide] [Duel|Tiny] [trait] [Script] [PS]" — same rules as the
// pool page's short label (trait only where the pool has >1 variant of
// the script; PS implied for DOTA).
export function labelsFor(pool: any[]) {
  const seen: Record<string, Set<string>> = {};
  for (const c of pool) (seen[c.group] ??= new Set()).add(c.variant || '');
  const multi = new Set(Object.keys(seen).filter((g) => seen[g].size > 1));
  const opt = (c: any) => {
    if (!multi.has(c.group)) return '';
    if (c.group === 'Desert') {
      const coast = (c.variant || '').split(' · ')[0];
      return coast === 'None' ? 'NoCst' : coast;
    }
    if (c.group === 'Arid Plateau')
      return /large/i.test(c.variant) ? 'Lg Seas' : /small/i.test(c.variant) ? 'Sm Seas' : '';
    return c.variant || '';
  };
  const short: Record<string, string> = {};
  for (const c of pool) {
    const ps = (symOf(c) === 'Sym' && c.group !== 'DOTA') ? 'PS' : '';
    short[c.slug] = [aspOf(c) === 'Wide' ? 'Wide' : 'Sq', sizeOf(c), opt(c),
      SCRIPT_SHORT[c.group] || c.group, ps].filter(Boolean).join(' ');
  }
  return short;
}

// Pool in pool-page order: sections alphabetical, configs by short label.
export function orderedPool(configs: any[]) {
  const by: Record<string, any> = {};
  for (const c of configs) by[c.slug] = c;
  const pool = POOL.map((s) => by[s]).filter(Boolean);
  const short = labelsFor(pool);
  const groups: Record<string, any[]> = {};
  for (const c of pool) (groups[dg(c)] ??= []).push(c);
  const out: any[] = [];
  for (const k of Object.keys(groups).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase())))
    for (const c of groups[k].sort((a: any, b: any) => short[a.slug].localeCompare(short[b.slug])))
      out.push(c);
  return { pool: out, short };
}
