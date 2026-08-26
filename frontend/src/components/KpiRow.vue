<script setup lang="ts">
import { RECENT_N } from '../lib/constants'
import { fmtDurationHMS } from '../lib/format'
import type { Kpis } from '../types/dashboard'
import StatTile from './StatTile.vue'

defineProps<{ kpis: Kpis }>()
</script>

<template>
  <div class="kpi-groups">
    <div class="kpi-group">
      <div class="kpi-group-label">Volume</div>
      <div class="kpi-row">
        <StatTile label="Estimated words typed" :value="kpis.est_words_typed.toFixed(0)" />
        <StatTile label="Tests started" :value="kpis.tests_started.toFixed(0)" />
        <StatTile
          label="Tests completed"
          :value="`${kpis.n_tests} (${kpis.completion_rate_pct.toFixed(0)}%)`"
        />
        <StatTile label="Restarts per completed test" :value="kpis.restarts_per_test.toFixed(2)" />
        <StatTile label="Time typing" :value="fmtDurationHMS(kpis.total_minutes_typing)" />
      </div>
    </div>

    <div class="kpi-group">
      <div class="kpi-group-label">WPM</div>
      <div class="kpi-row">
        <StatTile label="Highest WPM" :value="kpis.best_wpm.toFixed(0)" />
        <StatTile label="Average WPM (all-time)" :value="kpis.avg_wpm_all.toFixed(1)" />
        <StatTile
          :label="`Average WPM, last ${RECENT_N}`"
          :value="kpis.avg_wpm_recent.toFixed(1)"
          :delta="kpis.avg_wpm_recent - kpis.avg_wpm_first"
        />
      </div>
    </div>

    <div class="kpi-group">
      <div class="kpi-group-label">Raw WPM</div>
      <div class="kpi-row">
        <StatTile label="Highest raw WPM" :value="kpis.best_raw_wpm.toFixed(0)" />
        <StatTile label="Average raw WPM (all-time)" :value="kpis.avg_raw_wpm_all.toFixed(1)" />
        <StatTile
          :label="`Average raw WPM, last ${RECENT_N}`"
          :value="kpis.avg_raw_wpm_recent.toFixed(1)"
          :delta="kpis.avg_raw_wpm_recent - kpis.avg_raw_wpm_all"
        />
      </div>
    </div>

    <div class="kpi-group">
      <div class="kpi-group-label">Accuracy</div>
      <div class="kpi-row">
        <StatTile label="Highest accuracy" :value="`${kpis.best_acc.toFixed(0)}%`" />
        <StatTile label="Average accuracy (all-time)" :value="`${kpis.avg_acc_all.toFixed(1)}%`" />
        <StatTile
          :label="`Average accuracy, last ${RECENT_N}`"
          :value="`${kpis.avg_acc_recent.toFixed(1)}%`"
          :delta="kpis.avg_acc_recent - kpis.avg_acc_all"
          suffix="pp"
        />
      </div>
    </div>

    <div class="kpi-group">
      <div class="kpi-group-label">Consistency</div>
      <div class="kpi-row">
        <StatTile label="Highest consistency" :value="`${kpis.best_consistency.toFixed(0)}%`" />
        <StatTile label="Average consistency (all-time)" :value="`${kpis.avg_consistency_all.toFixed(1)}%`" />
        <StatTile
          :label="`Average consistency, last ${RECENT_N}`"
          :value="`${kpis.avg_consistency_recent.toFixed(1)}%`"
          :delta="kpis.avg_consistency_recent - kpis.avg_consistency_all"
          suffix="pp"
        />
      </div>
    </div>

    <div class="kpi-group">
      <div class="kpi-group-label">Errors</div>
      <div class="kpi-row">
        <StatTile
          :label="`Avg errors, last ${RECENT_N}`"
          :value="kpis.avg_errors_recent.toFixed(1)"
          :delta="kpis.avg_errors_recent - kpis.avg_errors_first"
          :delta-good-if-positive="false"
        />
      </div>
    </div>
  </div>
</template>
