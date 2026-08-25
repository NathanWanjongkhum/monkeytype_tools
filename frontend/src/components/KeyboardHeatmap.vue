<script setup lang="ts">
import { computed } from 'vue'
import { useElementTooltip } from '../composables/useElementTooltip'
import { rampColor, textColorFor } from '../lib/chartMath'
import { KEYBOARD_ROWS, SPACE_KEY, SPACE_ROW_OFFSET, SPACE_WIDTH_UNITS } from '../lib/keyboardLayout'

const props = withDefaults(
  defineProps<{
    values: Record<string, number>
    ramp: string[]
    fmt: (v: number) => string
    scaleFn?: (v: number) => number
    emptyNote?: string
  }>(),
  { scaleFn: (v: number) => v, emptyNote: 'not enough samples' },
)

const unit = 50
const gap = 5
const pad = 14
const nRows = KEYBOARD_ROWS.length + 1
const rowSpan = Math.max(...KEYBOARD_ROWS.map(([offset, row]) => offset + row.length))
const width = 2 * pad + rowSpan * unit
const height = 2 * pad + nRows * unit

interface Cell {
  key: string
  x: number
  y: number
  w: number
  h: number
  label: string
  shifted: string | null
  hasValue: boolean
  tip: string
  style: Record<string, string>
}

const cells = computed<Cell[]>(() => {
  const present = Object.values(props.values).filter((v) => v !== undefined && v !== null)
  const scaled = present.map(props.scaleFn)
  const lo = scaled.length ? Math.min(...scaled) : 0
  const hi = scaled.length ? Math.max(...scaled) : 1

  function tOf(v: number) {
    const s = props.scaleFn(v)
    return hi === lo ? 0.5 : (s - lo) / (hi - lo)
  }

  function buildCell(key: string, x: number, y: number, w: number, h: number, label: string, shifted: string | null): Cell {
    const v = props.values[key]
    if (v === undefined || v === null) {
      return { key, x, y, w, h, label, shifted, hasValue: false, tip: `${label}: ${props.emptyNote}`, style: {} }
    }
    const t = tOf(v)
    const light = rampColor(props.ramp, t)
    const dark = rampColor([...props.ramp].reverse(), t)
    return {
      key,
      x,
      y,
      w,
      h,
      label,
      shifted,
      hasValue: true,
      tip: `${label}: ${props.fmt(v)}`,
      style: { '--fl': light, '--fd': dark, '--tcl': textColorFor(light), '--tcd': textColorFor(dark) },
    }
  }

  const out: Cell[] = []
  KEYBOARD_ROWS.forEach(([offset, row], rowIdx) => {
    const y = pad + rowIdx * unit
    row.forEach(([key, shifted], i) => {
      const x = pad + (offset + i) * unit
      const label = /^[a-z]$/.test(key) ? key.toUpperCase() : key
      out.push(buildCell(key, x, y, unit - gap, unit - gap, label, shifted))
    })
  })
  const spaceY = pad + KEYBOARD_ROWS.length * unit
  const spaceX = pad + SPACE_ROW_OFFSET * unit
  out.push(buildCell(SPACE_KEY, spaceX, spaceY, SPACE_WIDTH_UNITS * unit - gap, unit - gap, 'SPACE', null))
  return out
})

const tooltip = useElementTooltip()

function onEnter(ev: PointerEvent, cell: Cell) {
  tooltip.show(ev.currentTarget as Element, cell.tip)
}
</script>

<template>
  <div class="chart-card">
    <div class="tooltip" :style="{ opacity: tooltip.visible.value ? 1 : 0, left: tooltip.left.value + 'px', top: tooltip.top.value + 'px' }">
      {{ tooltip.text.value }}
    </div>
    <svg :viewBox="`0 0 ${width} ${height}`" class="chart-svg heat-svg">
      <g
        v-for="cell in cells"
        :key="cell.key"
        class="heat-cell"
        :class="{ 'heat-cell-empty': !cell.hasValue }"
        :style="cell.style"
        @pointerenter="onEnter($event, cell)"
        @pointerleave="tooltip.hide"
      >
        <rect :x="cell.x" :y="cell.y" :width="cell.w" :height="cell.h" rx="6" :class="cell.hasValue ? 'heat-cell-rect' : 'heat-cell-rect-empty'" />
        <text v-if="cell.shifted" :x="cell.x + cell.w - 5" :y="cell.y + 12" class="heat-shift" text-anchor="end">{{ cell.shifted }}</text>
        <template v-if="cell.hasValue">
          <text :x="cell.x + cell.w / 2" :y="cell.y + cell.h / 2 - 3" class="heat-label" text-anchor="middle">{{ cell.label }}</text>
          <text :x="cell.x + cell.w / 2" :y="cell.y + cell.h / 2 + 13" class="heat-value" text-anchor="middle">{{ fmt(values[cell.key]) }}</text>
        </template>
        <text v-else :x="cell.x + cell.w / 2" :y="cell.y + cell.h / 2 + 4" class="heat-label-empty" text-anchor="middle">{{ cell.label }}</text>
      </g>
    </svg>
  </div>
</template>
