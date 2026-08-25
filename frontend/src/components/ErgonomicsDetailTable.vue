<script setup lang="ts">
import { computed } from 'vue'
import { displayBigram } from '../lib/format'
import type { ErgoDetailRow } from '../types/dashboard'
import BigramGlyph from './glyphs/BigramGlyph.vue'

const props = defineProps<{ detailRows: ErgoDetailRow[] }>()

const maxMedian = computed(() => Math.max(...props.detailRows.map((r) => r.median)))
</script>

<template>
  <p v-if="!detailRows.length" class="empty-state">Not enough bigram data yet to break down by category.</p>
  <table v-else class="data-table">
    <thead>
      <tr><th>category</th><th>bigram</th><th></th><th class="num">n</th><th class="num">median</th><th>relative latency</th></tr>
    </thead>
    <tbody>
      <tr v-for="(r, i) in detailRows" :key="r.category + r.bigram + i">
        <td>{{ r.category }}</td>
        <td class="mono">{{ displayBigram(r.bigram) }}</td>
        <td class="glyph-cell"><BigramGlyph :bigram="r.bigram" /></td>
        <td class="num">{{ r.n }}</td>
        <td class="num">{{ r.median.toFixed(0) }} ms</td>
        <td><div class="bar-track"><div class="bar-fill" :style="{ width: (100 * r.median / maxMedian) + '%' }"></div></div></td>
      </tr>
    </tbody>
  </table>
</template>
