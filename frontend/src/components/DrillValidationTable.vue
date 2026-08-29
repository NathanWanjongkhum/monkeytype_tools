<script setup lang="ts">
import { displayBigram } from '../lib/format'
import type { DrillValidationRow } from '../types/dashboard'

defineProps<{ rows: DrillValidationRow[] }>()
</script>

<template>
  <p v-if="!rows.length" class="empty-state">
    No tagged drill completions yet - see docs/adr/0003-drill-completion-validation.md for how to set one up.
  </p>
  <table v-else class="data-table">
    <thead>
      <tr>
        <th>bigram</th><th>category</th><th class="num">completions</th>
        <th class="num">avg before</th><th class="num">avg after</th><th class="num">avg change</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="r in rows" :key="r.bigram + r.category">
        <td class="mono">{{ displayBigram(r.bigram) }}</td>
        <td>{{ r.category }}</td>
        <td class="num">{{ r.occurrences }}</td>
        <td class="num">{{ r.avg_before_median.toFixed(0) }} ms</td>
        <td class="num">{{ r.avg_after_median.toFixed(0) }} ms</td>
        <td class="num" :class="r.avg_delta_ms > 0 ? 'improved' : 'worsened'">
          {{ r.avg_delta_ms > 0 ? '−' : '+' }}{{ Math.abs(r.avg_delta_ms).toFixed(0) }} ms
        </td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.improved { color: var(--good); }
.worsened { color: var(--critical); }
</style>
