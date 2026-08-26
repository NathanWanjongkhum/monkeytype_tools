<script setup lang="ts">
import { computed } from 'vue'
import { RECENT_N } from '../lib/constants'
import { fmtDelta, fmtDurationHMS } from '../lib/format'
import type { Kpis } from '../types/dashboard'

const props = defineProps<{ kpis: Kpis }>()

interface KpiEntry {
  label: string
  value: string
  delta?: number | null
  deltaGoodIfPositive?: boolean
  suffix?: string
}

interface KpiGroup {
  group: string
  rows: KpiEntry[]
}

const groups = computed<KpiGroup[]>(() => {
  const k = props.kpis
  return [
    {
      group: 'Volume',
      rows: [
        { label: 'Estimated words typed', value: k.est_words_typed.toFixed(0) },
        { label: 'Tests started', value: k.tests_started.toFixed(0) },
        { label: 'Tests completed', value: `${k.n_tests} (${k.completion_rate_pct.toFixed(0)}%)` },
        { label: 'Restarts per completed test', value: k.restarts_per_test.toFixed(2) },
        { label: 'Time typing', value: fmtDurationHMS(k.total_minutes_typing) },
      ],
    },
    {
      group: 'WPM',
      rows: [
        { label: 'Highest WPM', value: k.best_wpm.toFixed(0) },
        { label: 'Average WPM (all-time)', value: k.avg_wpm_all.toFixed(1) },
        {
          label: `Average WPM, last ${RECENT_N}`,
          value: k.avg_wpm_recent.toFixed(1),
          delta: k.avg_wpm_recent - k.avg_wpm_first,
        },
      ],
    },
    {
      group: 'Raw WPM',
      rows: [
        { label: 'Highest raw WPM', value: k.best_raw_wpm.toFixed(0) },
        { label: 'Average raw WPM (all-time)', value: k.avg_raw_wpm_all.toFixed(1) },
        {
          label: `Average raw WPM, last ${RECENT_N}`,
          value: k.avg_raw_wpm_recent.toFixed(1),
          delta: k.avg_raw_wpm_recent - k.avg_raw_wpm_all,
        },
      ],
    },
    {
      group: 'Accuracy',
      rows: [
        { label: 'Highest accuracy', value: `${k.best_acc.toFixed(0)}%` },
        { label: 'Average accuracy (all-time)', value: `${k.avg_acc_all.toFixed(1)}%` },
        {
          label: `Average accuracy, last ${RECENT_N}`,
          value: `${k.avg_acc_recent.toFixed(1)}%`,
          delta: k.avg_acc_recent - k.avg_acc_all,
          suffix: 'pp',
        },
      ],
    },
    {
      group: 'Consistency',
      rows: [
        { label: 'Highest consistency', value: `${k.best_consistency.toFixed(0)}%` },
        { label: 'Average consistency (all-time)', value: `${k.avg_consistency_all.toFixed(1)}%` },
        {
          label: `Average consistency, last ${RECENT_N}`,
          value: `${k.avg_consistency_recent.toFixed(1)}%`,
          delta: k.avg_consistency_recent - k.avg_consistency_all,
          suffix: 'pp',
        },
      ],
    },
    {
      group: 'Errors',
      rows: [
        {
          label: `Avg errors, last ${RECENT_N}`,
          value: k.avg_errors_recent.toFixed(1),
          delta: k.avg_errors_recent - k.avg_errors_first,
          deltaGoodIfPositive: false,
        },
      ],
    },
  ]
})

function deltaClass(row: KpiEntry): string {
  if (row.delta == null) return ''
  const goodIfPositive = row.deltaGoodIfPositive ?? true
  return (row.delta >= 0) === goodIfPositive ? 'good' : 'critical'
}

function deltaText(row: KpiEntry): string {
  if (row.delta == null) return ''
  const arrow = row.delta >= 0 ? '▲' : '▼'
  return `${arrow} ${fmtDelta(row.delta)}${row.suffix ?? ''} vs first ${RECENT_N}`
}
</script>

<template>
  <table class="data-table kpi-table">
    <thead>
      <tr>
        <th>Group</th>
        <th>Metric</th>
        <th class="num">Value</th>
        <th>Trend</th>
      </tr>
    </thead>
    <tbody>
      <template v-for="g in groups" :key="g.group">
        <tr v-for="(row, i) in g.rows" :key="row.label">
          <td v-if="i === 0" :rowspan="g.rows.length" class="kpi-group-cell">{{ g.group }}</td>
          <td>{{ row.label }}</td>
          <td class="num">{{ row.value }}</td>
          <td class="delta-badge" :class="deltaClass(row)">{{ deltaText(row) }}</td>
        </tr>
      </template>
    </tbody>
  </table>
</template>
