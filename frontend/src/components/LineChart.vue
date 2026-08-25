<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { useNearestPointHover, type HoverPoint } from '../composables/useNearestPointHover'
import { niceTicks } from '../lib/chartMath'
import type { SeriesPoint } from '../types/dashboard'

const props = defineProps<{ series: SeriesPoint[] }>()

const width = 860
const height = 300
const padL = 48
const padR = 16
const padT = 16
const padB = 28
const plotW = width - padL - padR
const plotH = height - padT - padB

const wpm = computed(() => props.series.map((s) => s.wpm))

function xOf(i: number) {
  return padL + (i / Math.max(wpm.value.length - 1, 1)) * plotW
}

const yTicks = computed(() => niceTicks(0, Math.max(...wpm.value) * 1.1, 5))
const yMin = computed(() => yTicks.value[0])
const yMax = computed(() => yTicks.value[yTicks.value.length - 1])

function yOf(v: number) {
  return padT + (1 - (v - yMin.value) / (yMax.value - yMin.value)) * plotH
}

const points = computed<HoverPoint<SeriesPoint>[]>(() =>
  props.series.map((s, i) => ({ x: xOf(i), y: yOf(s.wpm), data: s })),
)

const pathD = computed(
  () => 'M ' + points.value.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' L '),
)

const gridLines = computed(() => yTicks.value.map((t) => ({ t, y: yOf(t) })))

const endPoint = computed(() => points.value[points.value.length - 1])

const svgRef = useTemplateRef<SVGSVGElement>('svg')
const hover = useNearestPointHover<SeriesPoint>('x')

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
      <line v-for="g in gridLines" :key="g.t" :x1="padL" :y1="g.y" :x2="width - padR" :y2="g.y" class="gridline" />
      <text v-for="g in gridLines" :key="'lbl' + g.t" :x="padL - 8" :y="g.y" class="tick-label" text-anchor="end" dominant-baseline="middle">{{ Math.round(g.t) }}</text>
      <line :x1="padL" :y1="padT + plotH" :x2="width - padR" :y2="padT + plotH" class="axis-line" />
      <path :d="pathD" class="series-line" fill="none" />
      <template v-if="endPoint">
        <circle :cx="endPoint.x" :cy="endPoint.y" r="4" class="series-dot" />
        <text :x="endPoint.x" :y="endPoint.y - 12" class="end-label" text-anchor="end">{{ endPoint.data.wpm.toFixed(0) }} wpm</text>
      </template>
      <g class="crosshair" :style="{ opacity: hover.visible.value ? 1 : 0 }">
        <line v-if="hover.active.value" :x1="hover.active.value.x" :y1="padT" :x2="hover.active.value.x" :y2="padT + plotH" class="crosshair-line" />
        <circle v-if="hover.active.value" :cx="hover.active.value.x" :cy="hover.active.value.y" r="5" class="crosshair-dot" />
      </g>
      <rect :x="padL" :y="padT" :width="plotW" :height="plotH" fill="transparent" @pointermove="onMove" @pointerleave="hover.onPointerLeave" />
    </svg>
  </div>
</template>
