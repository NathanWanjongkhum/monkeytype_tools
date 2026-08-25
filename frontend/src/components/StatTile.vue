<script setup lang="ts">
import { computed } from 'vue'
import { RECENT_N } from '../lib/constants'
import { fmtDelta } from '../lib/format'

const props = withDefaults(
  defineProps<{
    label: string
    value: string
    delta?: number | null
    deltaGoodIfPositive?: boolean
    suffix?: string
  }>(),
  { delta: null, deltaGoodIfPositive: true, suffix: '' },
)

const good = computed(() => props.delta !== null && (props.delta >= 0) === props.deltaGoodIfPositive)
const arrow = computed(() => ((props.delta ?? 0) >= 0 ? '▲' : '▼'))
</script>

<template>
  <div class="stat-tile">
    <div class="stat-label">{{ label }}</div>
    <div class="stat-value">{{ value }}</div>
    <div v-if="delta !== null" class="stat-delta" :class="good ? 'good' : 'critical'">
      {{ arrow }} {{ fmtDelta(delta!) }}{{ suffix }} vs first {{ RECENT_N }}
    </div>
  </div>
</template>
