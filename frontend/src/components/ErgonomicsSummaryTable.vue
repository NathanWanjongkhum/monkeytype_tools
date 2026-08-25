<script setup lang="ts">
import type { ErgoCategoryRow } from '../types/dashboard'

defineProps<{ categoryRows: ErgoCategoryRow[] }>()
</script>

<template>
  <table class="data-table">
    <thead>
      <tr><th>category</th><th class="num">bigrams</th><th class="num">occurrences</th><th class="num">avg latency</th><th class="num">vs. overall avg</th></tr>
    </thead>
    <tbody>
      <tr v-for="c in categoryRows" :key="c.key">
        <td>{{ c.label }}<div class="caption" style="margin: 2px 0 0">{{ c.desc }}</div></td>
        <td class="num">{{ c.distinct }}</td>
        <template v-if="c.n === 0">
          <td class="num">0</td>
          <td class="num empty-cell">-</td>
          <td class="num empty-cell">-</td>
        </template>
        <template v-else>
          <td class="num">{{ c.n }}</td>
          <td class="num">{{ c.avg!.toFixed(0) }} ms</td>
          <td class="num">
            <span class="delta-badge" :class="c.delta_pct! >= 0 ? 'critical' : 'good'">
              {{ c.delta_pct! >= 0 ? '+' : '' }}{{ c.delta_pct!.toFixed(0) }}%
            </span>
          </td>
        </template>
      </tr>
    </tbody>
  </table>
</template>
