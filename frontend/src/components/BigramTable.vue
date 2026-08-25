<script setup lang="ts">
import { computed } from 'vue'
import { BIGRAM_TOP_N } from '../lib/constants'
import { displayBigram } from '../lib/format'
import type { BigramRow } from '../types/dashboard'
import BigramGlyph from './glyphs/BigramGlyph.vue'

const props = defineProps<{ rows: BigramRow[] }>()

const top = computed(() => props.rows.slice(0, BIGRAM_TOP_N))
const maxMedian = computed(() => Math.max(...top.value.map((r) => r.median)))
</script>

<template>
  <p v-if="!rows.length" class="empty-state">No bigram sessions cleared the sample threshold yet.</p>
  <table v-else class="data-table">
    <thead>
      <tr><th>bigram</th><th></th><th class="num">n</th><th class="num">median</th><th>relative latency</th></tr>
    </thead>
    <tbody>
      <tr v-for="r in top" :key="r.bigram">
        <td class="mono">{{ displayBigram(r.bigram) }}</td>
        <td class="glyph-cell"><BigramGlyph :bigram="r.bigram" /></td>
        <td class="num">{{ r.n }}</td>
        <td class="num">{{ r.median.toFixed(0) }} ms</td>
        <td><div class="bar-track"><div class="bar-fill" :style="{ width: (100 * r.median / maxMedian) + '%' }"></div></div></td>
      </tr>
    </tbody>
  </table>
</template>
