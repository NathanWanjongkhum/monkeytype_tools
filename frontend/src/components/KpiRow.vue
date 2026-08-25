<script setup lang="ts">
import { RECENT_N } from '../lib/constants'
import type { Kpis } from '../types/dashboard'
import StatTile from './StatTile.vue'

defineProps<{ kpis: Kpis }>()
</script>

<template>
  <div class="kpi-row">
    <StatTile label="Best WPM (all-time)" :value="kpis.best_wpm.toFixed(0)" />
    <StatTile
      :label="`Avg WPM, last ${RECENT_N}`"
      :value="kpis.avg_wpm_recent.toFixed(1)"
      :delta="kpis.avg_wpm_recent - kpis.avg_wpm_first"
    />
    <StatTile
      :label="`Avg accuracy, last ${RECENT_N}`"
      :value="`${kpis.avg_acc_recent.toFixed(1)}%`"
      :delta="kpis.avg_acc_recent - kpis.avg_acc_all"
      suffix="pp"
    />
    <StatTile :label="`Avg consistency, last ${RECENT_N}`" :value="kpis.avg_consistency_recent.toFixed(1)" />
    <StatTile
      :label="`Avg errors, last ${RECENT_N}`"
      :value="kpis.avg_errors_recent.toFixed(1)"
      :delta="kpis.avg_errors_recent - kpis.avg_errors_first"
      :delta-good-if-positive="false"
    />
    <StatTile label="Tests logged" :value="String(kpis.n_tests)" />
    <StatTile label="Time typing" :value="`${kpis.total_minutes_typing.toFixed(0)} min`" />
  </div>
</template>
