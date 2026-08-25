<script setup lang="ts">
import type { Action } from '../types/dashboard'

defineProps<{ actions: Action[] }>()

function icon(status: Action['status']) {
  return status === 'serious' ? 'i' : status === 'warning' ? '!' : '✓'
}
</script>

<template>
  <div class="action-list">
    <div v-for="(a, i) in actions" :key="i" class="action-item">
      <div class="status-icon" :class="a.status">{{ icon(a.status) }}</div>
      <div class="action-text">{{ a.text }}</div>
    </div>
  </div>
</template>
