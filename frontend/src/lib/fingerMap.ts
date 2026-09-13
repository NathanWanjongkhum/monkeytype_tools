// Ported from generate_dashboard.py's FINGER_MAP + finger-mechanics glyph
// geometry. hand, finger rank (1=index..4=pinky), row (0=top,1=home,2=bottom).
export type FingerEntry = readonly ['L' | 'R', number, number]

export const FINGER_MAP: Record<string, FingerEntry> = {
  q: ['L', 4, 0], w: ['L', 3, 0], e: ['L', 2, 0], r: ['L', 1, 0], t: ['L', 1, 0],
  a: ['L', 4, 1], s: ['L', 3, 1], d: ['L', 2, 1], f: ['L', 1, 1], g: ['L', 1, 1],
  z: ['L', 4, 2], x: ['L', 3, 2], c: ['L', 2, 2], v: ['L', 1, 2], b: ['L', 1, 2],
  y: ['R', 1, 0], u: ['R', 1, 0], i: ['R', 2, 0], o: ['R', 3, 0], p: ['R', 4, 0],
  h: ['R', 1, 1], j: ['R', 1, 1], k: ['R', 2, 1], l: ['R', 3, 1], ';': ['R', 4, 1],
  n: ['R', 1, 2], m: ['R', 1, 2], ',': ['R', 2, 2], '.': ['R', 3, 2], '/': ['R', 4, 2],
}

export type Point = [number, number]

export interface GlyphCurve {
  pathD: string
  chevronD: string
  anchor: Point | null
}

function chevronPath(x: number, y: number, dx: number, dy: number, size = 4.2): string {
  const ang = Math.atan2(dy, dx)
  const a1 = ang + (150 * Math.PI) / 180
  const a2 = ang - (150 * Math.PI) / 180
  const x1 = x + size * Math.cos(a1)
  const y1 = y + size * Math.sin(a1)
  const x2 = x + size * Math.cos(a2)
  const y2 = y + size * Math.sin(a2)
  return `M${x1.toFixed(1)},${y1.toFixed(1)} L${x.toFixed(1)},${y.toFixed(1)} L${x2.toFixed(1)},${y2.toFixed(1)}`
}

/** Curved arrow from `frm` to `to`, plus an arrowhead chevron at the end.
 * Shared geometry behind both the fixed category glyphs and the per-bigram
 * glyphs. */
export function glyphCurve(frm: Point, to: Point, anchor: Point | null = null): GlyphCurve {
  const [fx, fy] = frm
  const [tx, ty] = to
  const ctrl: Point =
    Math.abs(fx - tx) < 0.5
      ? [fx + 13, (fy + ty) / 2]
      : [(fx + tx) / 2, Math.max(2.0, Math.min(fy, ty) - 9)]
  const dx = tx - ctrl[0]
  const dy = ty - ctrl[1]
  const norm = Math.hypot(dx, dy) || 1
  return {
    pathD: `M${fx},${fy} Q${ctrl[0].toFixed(1)},${ctrl[1].toFixed(1)} ${tx},${ty}`,
    chevronD: chevronPath(tx, ty, dx / norm, dy / norm),
    anchor,
  }
}

// category glyphs: one abstract 4-finger x 3-row grid, four fixed diagrams

export const GLYPH_COLS = [8, 24, 40, 56]
export const GLYPH_ROWS = [8, 23, 38]

export function glyphPt(col: number, row: number): Point {
  return [GLYPH_COLS[col], GLYPH_ROWS[row]]
}

export const CATEGORY_GLYPH_VIEWBOX_W = 68

interface CategoryGlyphDef {
  frm: Point
  to: Point
  anchor: Point | null
  dashed: boolean
}

// same finger (ring), adjacent rows / same finger (index), top->bottom row /
// middle-home to pinky-bottom against the natural curl / index reaches into
// the stretch column while the middle finger holds home (hollow ring)
export const CATEGORY_GLYPH_DEFS: Record<string, CategoryGlyphDef> = {
  sfb: { frm: glyphPt(2, 1), to: glyphPt(2, 0), anchor: null, dashed: false },
  row_skip: { frm: glyphPt(0, 0), to: glyphPt(0, 2), anchor: null, dashed: false },
  awkward_roll: { frm: glyphPt(1, 1), to: glyphPt(3, 2), anchor: null, dashed: true },
  lsb: { frm: glyphPt(0, 1), to: [16, 8], anchor: glyphPt(1, 1), dashed: false },
}

// per-bigram glyphs: real two-hand grid (4 columns per hand x 3 rows)

export const BIGRAM_GLYPH_COLS = [4, 16, 28, 40, 54, 66, 78, 90] // L pinky..index | R index..pinky
export const BIGRAM_GLYPH_VIEWBOX_W = 98

export function bigramKeyPt(key: string): Point | null {
  const entry = FINGER_MAP[key]
  if (!entry) return null
  const [hand, rank, row] = entry
  const col = hand === 'L' ? 4 - rank : 3 + rank
  return [BIGRAM_GLYPH_COLS[col], GLYPH_ROWS[row]]
}

export function isSameFinger(a: string, b: string): boolean {
  const ea = FINGER_MAP[a]
  const eb = FINGER_MAP[b]
  if (!ea || !eb) return false
  return ea[0] === eb[0] && ea[1] === eb[1]
}
