// Ported from generate_dashboard.py's chart-geometry helpers.

export function niceTicks(vmin: number, vmax: number, count = 5): number[] {
  if (vmin === vmax) {
    vmin -= 1
    vmax += 1
  }
  let rawStep = (vmax - vmin) / count
  if (rawStep <= 0) rawStep = 1
  const mag = 10 ** Math.floor(Math.log10(rawStep))
  const residual = rawStep / mag
  const step = residual > 5 ? 10 * mag : residual > 2 ? 5 * mag : residual > 1 ? 2 * mag : mag
  const start = Math.floor(vmin / step) * step
  const ticks: number[] = []
  for (let v = start; v <= vmax + step * 0.5; v += step) {
    ticks.push(Math.round(v * 1e6) / 1e6)
  }
  return ticks
}

function hexToRgb01(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255,
  ]
}

function rgb01ToHex(rgb: [number, number, number]): string {
  return (
    '#' +
    rgb
      .map((c) => Math.round(Math.max(0, Math.min(1, c)) * 255).toString(16).padStart(2, '0'))
      .join('')
  )
}

/** Linear-interpolate a normalized magnitude t in [0,1] onto a sequential hex ramp. */
export function rampColor(ramp: string[], t: number): string {
  t = Math.max(0, Math.min(1, t))
  const pos = t * (ramp.length - 1)
  const i = Math.floor(pos)
  if (i >= ramp.length - 1) return ramp[ramp.length - 1]
  const frac = pos - i
  const c1 = hexToRgb01(ramp[i])
  const c2 = hexToRgb01(ramp[i + 1])
  return rgb01ToHex([
    c1[0] + (c2[0] - c1[0]) * frac,
    c1[1] + (c2[1] - c1[1]) * frac,
    c1[2] + (c2[2] - c1[2]) * frac,
  ])
}

export function textColorFor(hexColor: string): string {
  const [r, g, b] = hexToRgb01(hexColor)
  const brightness = 0.299 * r + 0.587 * g + 0.114 * b
  return brightness > 0.55 ? '#0b0b0b' : '#ffffff'
}

export function fmtCount(v: number): string {
  return v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(Math.round(v))
}

// dataviz skill: magnitude gets one hue, light->dark. Frequency and latency
// are two sequential contexts shown at once, so they take different hues:
// blue (the dashboard's default series color) and the next categorical
// slot, orange. Ported verbatim from generate_dashboard.py.
export const BLUE_RAMP = [
  '#cde2fb', '#b7d3f6', '#9ec5f4', '#86b6ef', '#6da7ec', '#5598e7', '#3987e5',
  '#2a78d6', '#256abf', '#1c5cab', '#184f95', '#104281', '#0d366b',
]
export const ORANGE_RAMP = [
  '#fadbce', '#f7c8b5', '#f4b59c', '#f1a283', '#ee8f6a', '#ec7c50', '#e96937',
  '#e6561e', '#d14c17', '#b74214', '#9e3912', '#85300f', '#6c270c',
]
