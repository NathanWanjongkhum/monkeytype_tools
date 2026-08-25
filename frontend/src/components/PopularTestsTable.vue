<script setup lang="ts">
import type { PopularTestRow } from '../types/dashboard'

defineProps<{ rows: PopularTestRow[] }>()
</script>

<template>
  <table class="data-table">
    <thead>
      <tr><th>test</th><th class="num">n</th><th class="num">avg wpm</th><th class="num">avg acc</th><th class="num">best wpm</th></tr>
    </thead>
    <tbody>
      <tr v-for="r in rows" :key="r.label">
        <td>{{ r.label }}</td>
        <template v-if="r.n === 0">
          <td class="num">0</td>
          <td class="num empty-cell">-</td>
          <td class="num empty-cell">-</td>
          <td class="num empty-cell">-</td>
        </template>
        <template v-else>
          <td class="num">{{ r.n }}</td>
          <td class="num">{{ r.avg_wpm!.toFixed(1) }}</td>
          <td class="num">{{ r.avg_acc!.toFixed(1) }}%</td>
          <td class="num">{{ r.best_wpm!.toFixed(0) }}</td>
        </template>
      </tr>
    </tbody>
  </table>
</template>
