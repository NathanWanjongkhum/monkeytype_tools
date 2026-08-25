import { ref, shallowRef } from 'vue'

export interface HoverPoint<T> {
  x: number
  y: number
  data: T
}

/** Port of attachLineHover/attachScatterHover: finds the nearest plotted
 * point to the pointer (in the SVG's viewBox coordinate space) and exposes
 * a fixed-position tooltip anchor for it. `mode: 'x'` searches by x-distance
 * only (line chart, "nearest test in time"), `'xy'` by Euclidean distance
 * (scatter chart). */
export function useNearestPointHover<T>(mode: 'x' | 'xy' = 'xy') {
  const visible = ref(false)
  const left = ref(0)
  const top = ref(0)
  const active = shallowRef<HoverPoint<T> | null>(null)

  function nearest(points: HoverPoint<T>[], px: number, py: number): HoverPoint<T> {
    let best = points[0]
    let bestDist = Infinity
    for (const p of points) {
      const dist = mode === 'x' ? Math.abs(p.x - px) : (p.x - px) ** 2 + (p.y - py) ** 2
      if (dist < bestDist) {
        best = p
        bestDist = dist
      }
    }
    return best
  }

  function onPointerMove(ev: PointerEvent, svg: SVGSVGElement, points: HoverPoint<T>[]) {
    if (!points.length) return
    const rect = svg.getBoundingClientRect()
    const scale = svg.viewBox.baseVal.width / rect.width
    const px = (ev.clientX - rect.left) * scale
    const py = (ev.clientY - rect.top) * scale
    const p = nearest(points, px, py)
    active.value = p
    visible.value = true
    left.value = rect.left + p.x / scale
    top.value = rect.top + p.y / scale
  }

  function onPointerLeave() {
    visible.value = false
    active.value = null
  }

  return { visible, left, top, active, onPointerMove, onPointerLeave }
}
