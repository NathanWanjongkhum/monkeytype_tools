<script setup lang="ts">
import { ref } from 'vue'
import { useClipboard } from '../composables/useClipboard'

const props = defineProps<{ text: string | null }>()

const { copy } = useClipboard()
const label = ref('Copy drill')
let revertTimer: ReturnType<typeof setTimeout> | undefined

async function onClick() {
  const ok = await copy(props.text ?? '')
  label.value = ok ? 'Copied!' : 'Copy failed, select the .txt file manually'
  clearTimeout(revertTimer)
  revertTimer = setTimeout(() => {
    label.value = 'Copy drill'
  }, 1500)
}
</script>

<template>
  <button class="copy-btn" type="button" @click="onClick">{{ label }}</button>
</template>
