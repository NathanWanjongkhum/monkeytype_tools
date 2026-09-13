<script setup lang="ts">
import { computed, ref, useTemplateRef } from 'vue'
import { useNearestPointHover, type HoverPoint } from '../composables/useNearestPointHover'
import { niceTicks, rollingMean, runningMax } from '../lib/chartMath'
import { fmtDelta } from '../lib/format'
import type { SeriesPoint } from '../types/dashboard'

const props = defineProps<{ series: SeriesPoint[]; wpmPerHourTyping: number }>()

const width = 860
const height = 300
const padL = 48
const padR = 16
const padT = 16
const padB = 28
const plotW = width - padL - padR
const plotH = height - padT - padB

// filters

type TriState = 'all' | 'on' | 'off'
type WindowChoice = '50' | '100' | '200' | 'all'

const modeFilter = ref<string>('all')
const dictFilter = ref<string>('all')
const punctuationFilter = ref<TriState>('all')
const numbersFilter = ref<TriState>('all')
const windowFilter = ref<WindowChoice>('all')

const distinctModes = computed(() =>
  [...new Set(props.series.map((s) => s.mode))].sort(),
)
const distinctLanguages = computed(() =>
  [...new Set(props.series.map((s) => s.language).filter((l): l is string => !!l))].sort(),
)

function matchesTri(value: boolean, filter: TriState): boolean {
  if (filter === 'all') return true
  return value === (filter === 'on')
}

// Mode/dictionary/modifier filters narrow the point set; the rolling-window
// lookback then trims that filtered set to its last N entries. Trend lines
// recompute against this same filtered+windowed set, not the raw series, so
// e.g. filtering to "words" mode only shows/averages "words" attempts.
const filteredAll = computed(() =>
  props.series.filter(
    (s) =>
      (modeFilter.value === 'all' || s.mode === modeFilter.value) &&
      (dictFilter.value === 'all' || s.language === dictFilter.value) &&
      matchesTri(s.punctuation, punctuationFilter.value) &&
      matchesTri(s.numbers, numbersFilter.value),
  ),
)

const filtered = computed(() => {
  const arr = filteredAll.value
  if (windowFilter.value === 'all') return arr
  const n = Number(windowFilter.value)
  return arr.slice(Math.max(0, arr.length - n))
})

// trend line toggles

const showBest = ref(false)
const showAvg10 = ref(true)
const showAvg100 = ref(false)

// scales

// X is cumulative hours of typing practice, not wall-clock time - matches
// backend/dashboard_data.py's compute_insights, which regresses wpm against
// this exact same cumulative-hours basis for "speed change per hour spent
// typing" above. Idle days between sessions cost zero x-width this way,
// instead of a linear-time axis crushing every burst of back-to-back tests
// into a near-vertical smear and wasting most of the plot on empty gaps.
const cumHours = computed(() => {
  let sum = 0
  return filtered.value.map((s) => {
    sum += (s.test_duration ?? 0) / 3600
    return sum
  })
})
const hoursSpan = computed(() => {
  const arr = cumHours.value
  return Math.max(arr.length ? arr[arr.length - 1] : 0, 1e-6)
})

function xOf(hours: number) {
  return padL + (hours / hoursSpan.value) * plotW
}

const wpmValues = computed(() => filtered.value.map((s) => s.wpm))
const yTicks = computed(() => {
  const vals = wpmValues.value
  const vmax = vals.length ? Math.max(...vals) * 1.1 : 100
  return niceTicks(0, vmax, 5)
})
const yMin = computed(() => yTicks.value[0])
const yMax = computed(() => yTicks.value[yTicks.value.length - 1])

function yOf(v: number) {
  const denom = yMax.value - yMin.value || 1
  return padT + (1 - (v - yMin.value) / denom) * plotH
}

const gridLines = computed(() => yTicks.value.map((t) => ({ t, y: yOf(t) })))

// One marker per real calendar-day boundary, instead of 5 fixed fractions of
// plot width: since x no longer tracks elapsed time, this is both the axis's
// date labels and the "a break happened here" cue, at zero extra x-cost.
const dayBoundaries = computed(() => {
  const out: { x: number; label: string }[] = []
  let prevDate: string | null = null
  filtered.value.forEach((s, i) => {
    const d = new Date(s.timestamp).toDateString()
    if (d !== prevDate) {
      out.push({ x: xOf(cumHours.value[i]), label: fmtTickDate(s.timestamp) })
      prevDate = d
    }
  })
  return out
})

function fmtTickDate(ts: string) {
  return new Date(ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

// Every real day boundary gets a divider line (dayBoundaries above), but two
// boundaries can land only a few pixels apart when little practice time
// separated them (e.g. one test late one night, one early two days later,
// with an idle day of zero width in between) - labeling both garbles into
// overlapping text. Greedily drop a label if it's too close to the last one
// actually kept; the divider line itself is still drawn for every boundary.
const MIN_LABEL_SPACING = 36
const dayLabels = computed(() => {
  const out: { x: number; label: string }[] = []
  let lastX = -Infinity
  for (const b of dayBoundaries.value) {
    if (b.x - lastX >= MIN_LABEL_SPACING) {
      out.push(b)
      lastX = b.x
    }
  }
  return out
})

// per-mode color, dots, PB rings

const MODE_COLORS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)']

const modeColor = computed(() => {
  const map: Record<string, string> = {}
  distinctModes.value.forEach((m, i) => {
    map[m] = MODE_COLORS[i % MODE_COLORS.length]
  })
  return map
})

interface Point extends HoverPoint<SeriesPoint> {
  color: string
}

const points = computed<Point[]>(() =>
  filtered.value.map((s, i) => ({
    x: xOf(cumHours.value[i]),
    y: yOf(s.wpm),
    data: s,
    color: modeColor.value[s.mode] ?? 'var(--text-muted)',
  })),
)

const pbPoints = computed(() => points.value.filter((p) => p.data.is_pb))

// trend lines

function pathFor(values: number[]): string {
  if (!values.length) return ''
  return (
    'M ' +
    values.map((v, i) => `${points.value[i].x.toFixed(1)},${yOf(v).toFixed(1)}`).join(' L ')
  )
}

// Step-after path for the running-max envelope: holds the previous best flat
// until the moment a new best is set, instead of sloping smoothly toward it.
function stepPathFor(values: number[]): string {
  if (!values.length) return ''
  const xs = points.value.map((p) => p.x)
  let d = `M ${xs[0].toFixed(1)},${yOf(values[0]).toFixed(1)}`
  for (let i = 1; i < values.length; i++) {
    d += ` L ${xs[i].toFixed(1)},${yOf(values[i - 1]).toFixed(1)}`
    d += ` L ${xs[i].toFixed(1)},${yOf(values[i]).toFixed(1)}`
  }
  return d
}

const bestPath = computed(() => stepPathFor(runningMax(wpmValues.value)))
const avg10Path = computed(() => pathFor(rollingMean(wpmValues.value, 10)))
const avg100Path = computed(() => pathFor(rollingMean(wpmValues.value, 100)))

// hover

const svgRef = useTemplateRef<SVGSVGElement>('svg')
const hover = useNearestPointHover<SeriesPoint>('xy')

function onMove(ev: PointerEvent) {
  if (svgRef.value) hover.onPointerMove(ev, svgRef.value, points.value)
}

function tooltipDate(ts: string) {
  return ts.replace('T', ' ').slice(0, 16)
}

// speed-per-hour stat

const speedGood = computed(() => props.wpmPerHourTyping > 0)
</script>

<template>
  <div>
    <div class="speed-stat" :class="speedGood ? 'good' : 'muted'">
      Speed change per hour spent typing: {{ fmtDelta(wpmPerHourTyping) }} wpm/hour
    </div>

    <div class="filter-bar">
      <div class="filter-group">
        <label>Mode</label>
        <select v-model="modeFilter" class="select-control">
          <option value="all">All modes</option>
          <option v-for="m in distinctModes" :key="m" :value="m">{{ m }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Dictionary</label>
        <select v-model="dictFilter" class="select-control">
          <option value="all">All dictionaries</option>
          <option v-for="l in distinctLanguages" :key="l" :value="l">{{ l }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Punctuation</label>
        <div class="toggle-group">
          <button
            type="button"
            class="toggle-btn"
            :class="{ active: punctuationFilter === 'all' }"
            @click="punctuationFilter = 'all'"
          >
            Both
          </button>
          <button
            type="button"
            class="toggle-btn"
            :class="{ active: punctuationFilter === 'on' }"
            @click="punctuationFilter = 'on'"
          >
            On
          </button>
          <button
            type="button"
            class="toggle-btn"
            :class="{ active: punctuationFilter === 'off' }"
            @click="punctuationFilter = 'off'"
          >
            Off
          </button>
        </div>
      </div>
      <div class="filter-group">
        <label>Numbers</label>
        <div class="toggle-group">
          <button
            type="button"
            class="toggle-btn"
            :class="{ active: numbersFilter === 'all' }"
            @click="numbersFilter = 'all'"
          >
            Both
          </button>
          <button
            type="button"
            class="toggle-btn"
            :class="{ active: numbersFilter === 'on' }"
            @click="numbersFilter = 'on'"
          >
            On
          </button>
          <button
            type="button"
            class="toggle-btn"
            :class="{ active: numbersFilter === 'off' }"
            @click="numbersFilter = 'off'"
          >
            Off
          </button>
        </div>
      </div>
      <div class="filter-group">
        <label>Rolling window</label>
        <select v-model="windowFilter" class="select-control">
          <option value="50">Last 50</option>
          <option value="100">Last 100</option>
          <option value="200">Last 200</option>
          <option value="all">All tests</option>
        </select>
      </div>
    </div>

    <div class="trend-pills">
      <button type="button" class="trend-pill best" :class="{ active: showBest }" @click="showBest = !showBest">
        <span class="pill-dot" />All-time best
      </button>
      <button type="button" class="trend-pill avg10" :class="{ active: showAvg10 }" @click="showAvg10 = !showAvg10">
        <span class="pill-dot" />Avg of 10
      </button>
      <button type="button" class="trend-pill avg100" :class="{ active: showAvg100 }" @click="showAvg100 = !showAvg100">
        <span class="pill-dot" />Avg of 100
      </button>
    </div>

    <div class="chart-card">
      <div
        class="tooltip"
        :style="{ opacity: hover.visible.value ? 1 : 0, left: hover.left.value + 'px', top: hover.top.value + 'px' }"
      >
        <template v-if="hover.active.value">
          <div>{{ tooltipDate(hover.active.value.data.timestamp) }}</div>
          <div>
            <span class="tt-value">{{ hover.active.value.data.wpm.toFixed(1) }} wpm</span> &middot;
            {{ hover.active.value.data.acc.toFixed(1) }}% acc
          </div>
          <div style="color: #999">
            {{ hover.active.value.data.mode }} {{ hover.active.value.data.mode2 }}
            <template v-if="hover.active.value.data.is_pb"> &middot; PB</template>
          </div>
        </template>
      </div>

      <p v-if="!filtered.length" class="empty-chart-note">No tests match the current filters.</p>

      <svg ref="svg" :viewBox="`0 0 ${width} ${height}`" class="chart-svg">
        <line v-for="g in gridLines" :key="g.t" :x1="padL" :y1="g.y" :x2="width - padR" :y2="g.y" class="gridline" />
        <text
          v-for="g in gridLines"
          :key="'lbl' + g.t"
          :x="padL - 8"
          :y="g.y"
          class="tick-label"
          text-anchor="end"
          dominant-baseline="middle"
        >{{ Math.round(g.t) }}</text>
        <line
          v-for="b in dayBoundaries"
          :key="'div' + b.x"
          :x1="b.x"
          :y1="padT"
          :x2="b.x"
          :y2="padT + plotH"
          class="day-divider"
        />
        <text
          v-for="b in dayLabels"
          :key="'lbl' + b.x"
          :x="b.x"
          :y="padT + plotH + 20"
          class="tick-label"
          text-anchor="middle"
        >{{ b.label }}</text>
        <line :x1="padL" :y1="padT + plotH" :x2="width - padR" :y2="padT + plotH" class="axis-line" />

        <circle
          v-for="(p, i) in points"
          :key="i"
          :cx="p.x"
          :cy="p.y"
          r="4"
          class="mode-dot"
          :style="{ fill: p.color }"
        />
        <circle v-for="(p, i) in pbPoints" :key="'pb' + i" :cx="p.x" :cy="p.y" r="4" class="pb-ring" />

        <path v-if="showBest" :d="bestPath" class="trend-line-best" />
        <path v-if="showAvg100" :d="avg100Path" class="trend-line-avg100" />
        <path v-if="showAvg10" :d="avg10Path" class="trend-line-avg10" />

        <g class="crosshair" :style="{ opacity: hover.visible.value ? 1 : 0 }">
          <circle v-if="hover.active.value" :cx="hover.active.value.x" :cy="hover.active.value.y" r="8" class="scatter-hover-ring" />
        </g>

        <rect :x="padL" :y="padT" :width="plotW" :height="plotH" fill="transparent" @pointermove="onMove" @pointerleave="hover.onPointerLeave" />
      </svg>

      <div class="legend-row">
        <span v-for="m in distinctModes" :key="m" class="legend-item">
          <span class="legend-swatch" :style="{ background: modeColor[m] }" />{{ m }}
        </span>
        <span class="legend-item"><span class="legend-swatch pb" />PB</span>
      </div>
    </div>
  </div>
</template>
