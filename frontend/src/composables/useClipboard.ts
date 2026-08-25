// Ported from generate_dashboard.py's copyDrillList. navigator.clipboard
// needs a secure context, which isn't guaranteed everywhere, so this falls
// back to the older execCommand("copy") via a hidden textarea when the
// Clipboard API is missing or rejects.
function legacyCopy(text: string): boolean {
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.position = 'fixed'
  ta.style.opacity = '0'
  document.body.appendChild(ta)
  ta.focus()
  ta.select()
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  }
  document.body.removeChild(ta)
  return ok
}

export function useClipboard() {
  async function copy(text: string): Promise<boolean> {
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text)
        return true
      } catch {
        return legacyCopy(text)
      }
    }
    return legacyCopy(text)
  }
  return { copy }
}
