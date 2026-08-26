<script setup lang="ts">
import { computed } from 'vue'
import { displayBigram } from '../lib/format'
import type { ErgoCategoryRow, ErgoDetailRow } from '../types/dashboard'
import BigramGlyph from './glyphs/BigramGlyph.vue'

const props = defineProps<{ detailRows: ErgoDetailRow[]; categoryRows: ErgoCategoryRow[] }>()

const maxMedian = computed(() =>
  Math.max(
    ...props.detailRows.map((r) => r.median),
    ...props.categoryRows.map((c) => c.representative_median ?? 0)
  )
)

// detailRows arrives already grouped by category (backend appends each
// category's top 5 in BIGRAM_CATEGORIES order), so grouping here just makes
// that explicit enough to slot each category's representative row in after
// its own worst offenders rather than at the end of the whole table.
const groups = computed(() =>
  props.categoryRows
    .map((c) => ({ category: c, rows: props.detailRows.filter((r) => r.category === c.label) }))
    .filter((g) => g.rows.length)
)
</script>

<template>
  <p v-if="!detailRows.length" class="empty-state">Not enough bigram data yet to break down by category.</p>
  <table v-else class="data-table">
    <thead>
      <tr><th>category</th><th>bigram</th><th></th><th class="num">n</th><th class="num">median</th><th>relative latency</th></tr>
    </thead>
    <tbody v-for="g in groups" :key="g.category.key">
      <tr v-for="(r, i) in g.rows" :key="g.category.key + r.bigram + i">
        <td>{{ r.category }}</td>
        <td class="mono">{{ displayBigram(r.bigram) }}</td>
        <td class="glyph-cell"><BigramGlyph :bigram="r.bigram" /></td>
        <td class="num">{{ r.n }}</td>
        <td class="num">{{ r.median.toFixed(0) }} ms</td>
        <td><div class="bar-track"><div class="bar-fill" :style="{ width: (100 * r.median / maxMedian) + '%' }"></div></div></td>
      </tr>
      <tr v-if="g.category.representative_bigram" class="rep-row">
        <td class="empty-cell">{{ g.category.label }}</td>
        <td class="mono">{{ displayBigram(g.category.representative_bigram) }} <span class="rep-tag">(representative)</span></td>
        <td class="glyph-cell"><BigramGlyph :bigram="g.category.representative_bigram" /></td>
        <td class="num empty-cell">&ndash;</td>
        <td class="num">{{ g.category.representative_median!.toFixed(0) }} ms</td>
        <td><div class="bar-track"><div class="bar-fill rep-fill" :style="{ width: (100 * g.category.representative_median! / maxMedian) + '%' }"></div></div></td>
      </tr>
    </tbody>
  </table>
</template>
