import { ref } from 'vue'

/** Port of attachHeatmapHover: a tooltip anchored above whichever element
 * the pointer is currently over, rather than a nearest-point search. */
export function useElementTooltip() {
  const visible = ref(false)
  const left = ref(0)
  const top = ref(0)
  const text = ref('')

  function show(el: Element, t: string) {
    const rect = el.getBoundingClientRect()
    left.value = rect.left + rect.width / 2
    top.value = rect.top
    text.value = t
    visible.value = true
  }

  function hide() {
    visible.value = false
  }

  return { visible, left, top, text, show, hide }
}
