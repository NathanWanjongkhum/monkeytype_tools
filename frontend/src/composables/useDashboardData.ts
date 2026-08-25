import { ref } from 'vue'
import type { DashboardPayload } from '../types/dashboard'

// Module-level singleton: fetched once per page load (on first call from
// any component), not once per component and never on Vite HMR. HMR swaps
// component modules in place without re-running this module's top level, so
// a template/style edit during dev never triggers a refetch.
const data = ref<DashboardPayload | null>(null)
const error = ref<string | null>(null)
const loading = ref(true)
let started = false

async function fetchDashboard() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch('/api/dashboard')
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      throw new Error(body?.detail ?? `HTTP ${res.status}`)
    }
    data.value = (await res.json()) as DashboardPayload
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

export function useDashboardData() {
  if (!started) {
    started = true
    fetchDashboard()
  }
  return { data, error, loading }
}
