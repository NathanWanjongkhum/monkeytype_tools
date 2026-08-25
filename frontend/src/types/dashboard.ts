export interface Kpis {
  n_tests: number
  best_wpm: number
  avg_wpm_recent: number
  avg_wpm_first: number
  avg_acc_recent: number
  avg_acc_all: number
  avg_consistency_recent: number
  avg_errors_recent: number
  avg_errors_first: number
  total_minutes_typing: number
  date_span_days: number
}

export interface Insights {
  wpm_slope_per_test: number
  wpm_trend_r: number
  acc_slope_per_test: number
  acc_std_first_half: number | null
  acc_std_second_half: number | null
  acc_wpm_correlation: number
}

export type ActionStatus = 'good' | 'warning' | 'serious'

export interface Action {
  status: ActionStatus
  text: string
}

export interface BigramRow {
  bigram: string
  n: number
  median: number
  mean: number
}

export interface PopularTestRow {
  label: string
  n: number
  avg_wpm: number | null
  avg_acc: number | null
  best_wpm: number | null
}

export interface ErgoCategoryRow {
  key: string
  label: string
  desc: string
  distinct: number
  n: number
  avg: number | null
  delta_pct: number | null
}

export interface ErgoDetailRow extends BigramRow {
  category: string
}

export interface DrillInfo {
  text: string | null
  path: string | null
}

export interface CategoryDrillInfo extends DrillInfo {
  key: string
  label: string
  desc: string
  n_entries: number
}

export interface SeriesPoint {
  timestamp: string
  wpm: number
  acc: number
  mode: string
  mode2: string | null
}

export interface DashboardPayload {
  kpis: Kpis
  insights: Insights
  has_tags: boolean
  actions: Action[]
  bigram_rows: BigramRow[]
  popular_tests: PopularTestRow[]
  ergonomics: {
    category_rows: ErgoCategoryRow[]
    detail_rows: ErgoDetailRow[]
  }
  drills: {
    overall: DrillInfo
    categories: CategoryDrillInfo[]
  }
  series: SeriesPoint[]
  key_stats: {
    freq: Record<string, number>
    latency: Record<string, number>
  }
  keylog_events: number
  keylog_sessions: number
}
