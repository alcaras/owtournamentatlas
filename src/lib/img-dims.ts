// Build-time image dimension probe, shared by the gallery pages.
//
// Gallery images are `loading="lazy"`; without an intrinsic size their box
// is 0px tall until loaded, so lazy loads above a #anchor target shift it
// off-screen — cold deep-links miss in Chrome/Safari (PR #1). Stamping
// width/height on each <img> reserves the box up front (the pages keep
// width:100%/height:auto, so the attributes act only as an aspect-ratio
// hint, never a fixed size).
//
// Resolution is anchored at process.cwd() (the project root during both
// `astro build` and dev) — NOT import.meta.url, which at build time points
// into dist/pages/ and only matched src/pages/'s depth by coincidence.
// imageMetadata (Astro's vendored image-size) validates the file, so a
// truncated or re-encoded image fails the build loudly instead of stamping
// garbage dimensions.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { imageMetadata } from 'astro/assets/utils';

export type Dim = { w: number; h: number };

// rel is a path under public/img/, e.g. "atlas/<slug>/seed-1.png".
export async function imgSize(rel: string): Promise<Dim> {
  const abs = join(process.cwd(), 'public', 'img', rel);
  const m = await imageMetadata(readFileSync(abs), abs);
  return { w: m.width, h: m.height };
}

// One entry per config slug, probed from its first gallery image. Maps
// render at a fixed pixel size per config (uniform across seeds — verified
// over every config dir under public/img/atlas/), so one probe per config
// covers its whole gallery.
export async function imgDimsBySlug(
  cfgs: { slug: string; imgs?: string[] }[],
): Promise<Record<string, Dim>> {
  const out: Record<string, Dim> = {};
  for (const c of cfgs) if (c.imgs?.length) out[c.slug] = await imgSize(c.imgs[0]);
  return out;
}
