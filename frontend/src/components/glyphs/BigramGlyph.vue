<script setup lang="ts">
import { computed } from 'vue'
import { BIGRAM_GLYPH_COLS, BIGRAM_GLYPH_VIEWBOX_W, GLYPH_ROWS, bigramKeyPt, glyphCurve, isSameFinger } from '../../lib/fingerMap'

// Small per-bigram diagram of exactly which two keys a specific bigram uses,
// on the real two-hand grid (4 columns per hand x 3 rows). Falls back to a
// blank grid for a bigram with a key outside the touch-typing chart (space,
// digits, punctuation).
const props = defineProps<{ bigram: string }>()

const dots = computed(() => {
  const pts: [number, number][] = []
  for (const x of BIGRAM_GLYPH_COLS) for (const y of GLYPH_ROWS) pts.push([x, y])
  return pts
})

const geometry = computed(() => {
  if (props.bigram.length !== 2) return null
  const frm = bigramKeyPt(props.bigram[0])
  const to = bigramKeyPt(props.bigram[1])
  if (!frm || !to) return null
  const critical = isSameFinger(props.bigram[0], props.bigram[1])
  return { frm, to, critical, curve: glyphCurve(frm, to) }
})
</script>

<template>
  <svg class="glyph glyph-bigram" :viewBox="`0 0 ${BIGRAM_GLYPH_VIEWBOX_W} 46`" aria-hidden="true">
    <circle v-for="(p, i) in dots" :key="i" class="glyph-dot" :cx="p[0]" :cy="p[1]" r="2.1" />
    <template v-if="geometry">
      <path :class="{ 'glyph-path': true, critical: geometry.critical }" :d="geometry.curve.pathD" />
      <path :class="{ 'glyph-chevron': true, critical: geometry.critical }" :d="geometry.curve.chevronD" />
      <circle class="glyph-node-start" :cx="geometry.frm[0]" :cy="geometry.frm[1]" r="3.4" />
      <circle :class="{ 'glyph-node-end': true, critical: geometry.critical }" :cx="geometry.to[0]" :cy="geometry.to[1]" r="3.6" />
    </template>
  </svg>
</template>
