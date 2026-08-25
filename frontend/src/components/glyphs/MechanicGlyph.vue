<script setup lang="ts">
import { computed } from 'vue'
import { CATEGORY_GLYPH_DEFS, CATEGORY_GLYPH_VIEWBOX_W, GLYPH_COLS, GLYPH_ROWS, glyphCurve } from '../../lib/fingerMap'

// One of the 4 fixed finger-mechanics category diagrams, drawn on the
// abstract 4-finger x 3-row grid (the FINGER_MAP shape itself).
const props = defineProps<{ category: string }>()

const dots = computed(() => {
  const pts: [number, number][] = []
  for (let c = 0; c < 4; c++) for (const y of GLYPH_ROWS) pts.push([GLYPH_COLS[c], y])
  return pts
})

const def = computed(() => CATEGORY_GLYPH_DEFS[props.category])
const curve = computed(() => glyphCurve(def.value.frm, def.value.to, def.value.anchor))
const variantClass = computed(() => (def.value.dashed ? ' dashed' : ''))
</script>

<template>
  <svg class="glyph" :viewBox="`0 0 ${CATEGORY_GLYPH_VIEWBOX_W} 46`" aria-hidden="true">
    <circle v-for="(p, i) in dots" :key="i" class="glyph-dot" :cx="p[0]" :cy="p[1]" r="2.6" />
    <circle v-if="curve.anchor" class="glyph-anchor" :cx="curve.anchor[0]" :cy="curve.anchor[1]" r="4" />
    <path :class="'glyph-path' + variantClass" :d="curve.pathD" />
    <path class="glyph-chevron" :d="curve.chevronD" />
    <circle class="glyph-node-start" :cx="def.frm[0]" :cy="def.frm[1]" r="3.4" />
    <circle class="glyph-node-end" :cx="def.to[0]" :cy="def.to[1]" r="3.6" />
  </svg>
</template>
