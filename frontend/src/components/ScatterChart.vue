<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { useNearestPointHover, type HoverPoint } from '../composables/useNearestPointHover'
import { niceTicks } from '../lib/chartMath'
import type { SeriesPoint } from '../types/dashboard'

const props = defineProps<{ series: SeriesPoint[]; slope: number; intercept: number }>()

const width = 860
const height = 300
const padL = 48
const padR = 16
const padT = 16
const padB = 28
const plotW = width - padL - padR
const plotH = height - padT - padB

const wpm = computed(() => props.series.map((s) => s.wpm))
const acc = computed(() => props.series.map((s) => s.acc))

// Fit to the actual wpm spread instead of anchoring at 0 - real wpm values
// cluster in a narrow band (e.g. 40-95), so a 0-start axis wastes roughly
// half the plot on a range with no data in it. Mirrors how the y-axis
// (acc) already floors near the real data instead of at 0.
const xTicks = computed(() => niceTicks(Math.min(...wpm.value) - 2, Math.max(...wpm.value) * 1.05, 5))
const xMin = computed(() => xTicks.value[0])
const xMax = computed(() => xTicks.value[xTicks.value.length - 1])
const yTicks = computed(() => niceTicks(Math.min(80, Math.min(...acc.value) - 2), 100, 4))
const yMin = computed(() => yTicks.value[0])
const yMax = computed(() => yTicks.value[yTicks.value.length - 1])

function xOf(v: number) {
  return padL + ((v - xMin.value) / (xMax.value - xMin.value)) * plotW
}
function yOf(v: number) {
  return padT + (1 - (v - yMin.value) / (yMax.value - yMin.value)) * plotH
}

// Regression line (acc = slope*wpm + intercept) clipped to the visible
// plot rectangle, so it terminates cleanly at the axis edges instead of
// running off the top/bottom when the fitted line exits the acc domain
// before it exits the wpm domain.
const trendLine = computed(() => {
  const { slope, intercept } = props
  let x0 = xMin.value
  let x1 = xMax.value
  let y0 = slope * x0 + intercept
  let y1 = slope * x1 + intercept

  if (slope !== 0) {
    if (y0 > yMax.value) { y0 = yMax.value; x0 = (yMax.value - intercept) / slope }
    else if (y0 < yMin.value) { y0 = yMin.value; x0 = (yMin.value - intercept) / slope }
    if (y1 > yMax.value) { y1 = yMax.value; x1 = (yMax.value - intercept) / slope }
    else if (y1 < yMin.value) { y1 = yMin.value; x1 = (yMin.value - intercept) / slope }
  }

  return { x1: xOf(x0), y1: yOf(y0), x2: xOf(x1), y2: yOf(y1) }
})

const points = computed<(HoverPoint<SeriesPoint> & { opacity: number })[]>(() => {
  const n = props.series.length
  return props.series.map((s, i) => ({
    x: xOf(s.wpm),
    y: yOf(s.acc),
    data: s,
    opacity: 0.35 + 0.65 * (i / Math.max(n - 1, 1)),
  }))
})

const svgRef = useTemplateRef<SVGSVGElement>('svg')
const hover = useNearestPointHover<SeriesPoint>('xy')

function onMove(ev: PointerEvent) {
  if (svgRef.value) hover.onPointerMove(ev, svgRef.value, points.value)
}

function tooltipDate(ts: string) {
  return ts.replace('T', ' ').slice(0, 16)
}
</script>

<template>
  <div class="chart-card">
    <div class="tooltip" :style="{ opacity: hover.visible.value ? 1 : 0, left: hover.left.value + 'px', top: hover.top.value + 'px' }">
      <template v-if="hover.active.value">
        <div>{{ tooltipDate(hover.active.value.data.timestamp) }}</div>
        <div><span class="tt-value">{{ hover.active.value.data.wpm.toFixed(1) }} wpm</span> &middot; {{ hover.active.value.data.acc.toFixed(1) }}% acc</div>
        <div style="color: #999">{{ hover.active.value.data.mode }} {{ hover.active.value.data.mode2 }}</div>
      </template>
    </div>
    <svg ref="svg" :viewBox="`0 0 ${width} ${height}`" class="chart-svg">
      <line v-for="t in yTicks" :key="t" :x1="padL" :y1="yOf(t)" :x2="width - padR" :y2="yOf(t)" class="gridline" />
      <text v-for="t in yTicks" :key="'ylbl' + t" :x="padL - 8" :y="yOf(t)" class="tick-label" text-anchor="end" dominant-baseline="middle">{{ Math.round(t) }}%</text>
      <text v-for="t in xTicks" :key="'xlbl' + t" :x="xOf(t)" :y="padT + plotH + 20" class="tick-label" text-anchor="middle">{{ Math.round(t) }}</text>
      <line :x1="padL" :y1="padT + plotH" :x2="width - padR" :y2="padT + plotH" class="axis-line" />
      <line
        :x1="trendLine.x1"
        :y1="trendLine.y1"
        :x2="trendLine.x2"
        :y2="trendLine.y2"
        class="trend-line-regression"
      />
      <circle
        v-for="(p, i) in points"
        :key="i"
        :cx="p.x"
        :cy="p.y"
        r="5"
        class="scatter-dot"
        :style="{ opacity: p.opacity }"
      />
      <circle
        class="scatter-hover-ring"
        r="9"
        :style="{ opacity: hover.visible.value ? 1 : 0 }"
        :cx="hover.active.value?.x ?? 0"
        :cy="hover.active.value?.y ?? 0"
      />
      <rect :x="padL" :y="padT" :width="plotW" :height="plotH" fill="transparent" @pointermove="onMove" @pointerleave="hover.onPointerLeave" />
    </svg>
  </div>
</template>
