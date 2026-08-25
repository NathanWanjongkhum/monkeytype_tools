<script setup lang="ts">
import { computed } from 'vue'
import type { Insights } from '../types/dashboard'

const props = defineProps<{
  insights: Insights
  nTests: number
  bigramCount: number
  keylogEvents: number
  hasTags: boolean
}>()

const accStdNote = computed(() =>
  props.insights.acc_std_first_half !== null && props.insights.acc_std_second_half !== null
    ? `first-half std ${props.insights.acc_std_first_half.toFixed(2)}pp vs second-half std ` +
      `${props.insights.acc_std_second_half.toFixed(2)}pp across ${props.nTests} tests`
    : 'not enough tests yet to split in half',
)

const questions = computed(() => {
  const tagTag = props.hasTags ? 'partial' : 'blocked'
  return [
    {
      tag: 'answerable',
      q: 'Does accuracy plateau before speed keeps climbing?',
      a: `Partially testable now (${accStdNote.value}). See the Overall section. More tests will sharpen it.`,
    },
    {
      tag: 'answerable',
      q: 'Which specific bigrams are slow for me?',
      a: props.bigramCount
        ? `Answerable from ${props.keylogEvents} logged keystrokes. See the Bigrams section above.`
        : 'Not yet. No bigram cleared the minimum sample count.',
    },
    {
      tag: tagTag,
      q: 'Volume vs. targeted drilling: which moves WPM more?',
      a: props.hasTags
        ? 'Partially tagged, needs more sessions per tag to compare slopes.'
        : 'Blocked. Needs tagged sessions comparing normal practice vs. drill lists; no tags used yet.',
    },
    {
      tag: tagTag,
      q: 'Does the hands-back, fingers-curled position actually help?',
      a: props.hasTags
        ? 'Partially tagged, needs more sessions per tag to compare.'
        : "Blocked. Needs tagged 'hands-back' vs 'hands-normal' sessions to compare; no tags used yet.",
    },
  ]
})
</script>

<template>
  <div class="oq-grid">
    <div v-for="(row, i) in questions" :key="i" class="oq-row">
      <span class="oq-tag" :class="row.tag">{{ row.tag }}</span>
      <span class="oq-text"><b>{{ row.q }}</b> {{ row.a }}</span>
    </div>
  </div>
</template>
