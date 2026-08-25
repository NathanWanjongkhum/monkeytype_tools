<script setup lang="ts">
import type { CategoryDrillInfo, ErgoCategoryRow } from '../types/dashboard'
import CopyButton from './CopyButton.vue'
import MechanicGlyph from './glyphs/MechanicGlyph.vue'

const props = defineProps<{ categoryRows: ErgoCategoryRow[]; drills: CategoryDrillInfo[] }>()

function drillFor(key: string) {
  return props.drills.find((d) => d.key === key)
}
</script>

<template>
  <div class="mech-grid">
    <div v-for="cat in categoryRows" :key="cat.key" class="mech-card">
      <div class="mech-card-head">
        <MechanicGlyph :category="cat.key" />
        <div class="mech-card-title">{{ cat.label }}</div>
      </div>
      <div class="mech-card-desc">{{ cat.desc }}</div>
      <div v-if="drillFor(cat.key)?.text" class="mech-card-foot">
        <CopyButton :text="drillFor(cat.key)!.text" />
        <span class="mech-card-stat">
          {{ drillFor(cat.key)!.n_entries }} bigram{{ drillFor(cat.key)!.n_entries === 1 ? '' : 's' }}
          &middot; <a :href="`/drills/${drillFor(cat.key)!.path}`">.txt</a>
        </span>
      </div>
      <div v-else class="mech-card-foot"><span class="empty-state">Not enough matching bigrams yet.</span></div>
    </div>
  </div>
</template>
