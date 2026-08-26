<script setup lang="ts">
import { computed } from 'vue'
import ActionPlan from './components/ActionPlan.vue'
import BigramTable from './components/BigramTable.vue'
import CategoryDrillCards from './components/CategoryDrillCards.vue'
import CopyButton from './components/CopyButton.vue'
import ErgonomicsDetailTable from './components/ErgonomicsDetailTable.vue'
import ErgonomicsSummaryTable from './components/ErgonomicsSummaryTable.vue'
import KeyboardHeatmap from './components/KeyboardHeatmap.vue'
import KpiRow from './components/KpiRow.vue'
import OpenQuestions from './components/OpenQuestions.vue'
import PopularTestsTable from './components/PopularTestsTable.vue'
import ScatterChart from './components/ScatterChart.vue'
import WpmMasterChart from './components/WpmMasterChart.vue'
import { useDashboardData } from './composables/useDashboardData'
import { BLUE_RAMP, ORANGE_RAMP, fmtCount } from './lib/chartMath'
import { MIN_SAMPLES } from './lib/constants'

const { data, error, loading } = useDashboardData()

const latencyFmt = (v: number) => `${v.toFixed(0)} ms`
const sqrtScale = (v: number) => Math.sqrt(v)

const bigramCount = computed(() => data.value?.bigram_rows.length ?? 0)
</script>

<template>
  <div class="wrap">
    <h1>Typing progress dashboard</h1>
    <p class="subtitle">
      Built from typing.duckdb. Opening this page always refreshes results and keylogs, and re-derives the
      database only when something actually changed since last time. Every number on this page is computed
      directly from that data - no interpretation layer, nothing invented per run.
    </p>

    <p v-if="loading" class="loading-state">Loading...</p>
    <p v-else-if="error" class="error-state">{{ error }}</p>

    <template v-else-if="data">
      <section>
        <h2>Overall</h2>
        <p class="caption">Aggregate view across every test and every logged keystroke: wpm, accuracy, consistency.</p>
        <KpiRow :kpis="data.kpis" />

        <h3>WPM over time</h3>
        <p class="caption">
          One dot per attempt - color is mode, a gold ring marks a PB - instead of a single connective line, so
          outcome (any one test's wpm) doesn't stand in for trend. Toggle All-time best / Avg of 10 / Avg of 100
          to read direction instead of noise, and filter by mode, dictionary, punctuation/numbers, or a rolling
          lookback window to isolate a slice.
        </p>
        <WpmMasterChart :series="data.series" :wpm-per-hour-typing="data.insights.wpm_per_hour_typing" />

        <h3>Accuracy vs. WPM</h3>
        <p class="caption">
          One dot per test, darker = more recent. Tests speed against accuracy to see whether pushing WPM has been
          costing accuracy.
        </p>
        <ScatterChart :series="data.series" />
      </section>

      <section>
        <h2>Bigrams</h2>
        <p class="caption">
          Median inter-key latency for every bigram with at least {{ MIN_SAMPLES }} logged samples, slowest first.
          Each row's glyph plots that bigram's actual two keys - critical red when both land on the same finger,
          the one mechanic the Finger mechanics section below finds reliably slower. The dashed row is the
          representative baseline: the bigram closest to the occurrence-weighted median across all bigrams,
          for scale against how far the outliers below actually fall from typical.
        </p>
        <div v-if="data.drills.overall.text" class="mech-card"><p class="caption drill-row">
          <span>
            Real words from Monkeytype's english_10k list, picked for containing your slowest bigrams. Each word
            repeats in proportion to how slow its bigram is. Paste into Monkeytype's custom text box (word
            delimiter: pipe), or open <a :href="`/drills/${data.drills.overall.path}`">drill_practice.txt</a>.
          </span>
          <CopyButton :text="data.drills.overall.text" />
        </p></div>
        <p v-else class="caption">Not enough bigram data yet for a drill list.</p>
        <BigramTable :rows="data.bigram_rows" :representative="data.ergonomics.overall_representative" />
      </section>

      <section>
        <h2>Finger mechanics</h2>
        <p class="caption">
          Classifies the same trustworthy bigrams above by finger mechanics, using a standard QWERTY touch-typing
          chart. Categories aren't mutually exclusive. A same-finger bigram that also skips two rows counts toward
          both. "vs. overall avg" compares each category's occurrence-weighted average latency to the average
          across every bigram above.
        </p>
        <ErgonomicsSummaryTable :category-rows="data.ergonomics.category_rows" />

        <h3>Drill by category</h3>
        <p class="caption">
          Same real-word approach as the drill list above (Monkeytype's english_10k list, repeats weighted by
          latency), but scoped to one mechanic at a time - drill just your same-finger bigrams, say, instead of a
          mixed bag.
        </p>
        <CategoryDrillCards :category-rows="data.ergonomics.category_rows" :drills="data.drills.categories" />

        <h3>Worst offenders by category</h3>
        <p class="caption">
          Top 5 slowest bigrams in each category, by median latency, plus a dashed representative row: the
          bigram closest to that category's own occurrence-weighted median, as a concrete baseline for how much
          correction the worst 5 above actually need to reach typical.
        </p>
        <ErgonomicsDetailTable :detail-rows="data.ergonomics.detail_rows" :category-rows="data.ergonomics.category_rows" />
      </section>

      <section>
        <h2>Keyboard heatmap</h2>
        <p class="caption">
          Every logged single-character keystroke, laid out on a QWERTY grid. Color is relative within each map
          (lightest = least, darkest = most), not comparable between the two.
        </p>

        <h3>Frequency</h3>
        <p class="caption">
          Raw press counts, color-scaled by square root so less-used keys stay visible next to the vowels and home
          row.
        </p>
        <KeyboardHeatmap :values="data.key_stats.freq" :ramp="BLUE_RAMP" :fmt="fmtCount" :scale-fn="sqrtScale" />

        <h3>Latency</h3>
        <p class="caption">
          Median time to reach each key from whatever key preceded it, same attempt-scoped pairing and
          {{ MIN_SAMPLES }}-sample floor as the bigram table above. Grayed-out keys haven't cleared that floor yet.
          Darker means slower to reach, not "bad" in isolation - a key fed mostly by awkward bigrams reads dark
          even if the key itself is easy.
        </p>
        <KeyboardHeatmap :values="data.key_stats.latency" :ramp="ORANGE_RAMP" :fmt="latencyFmt" />
      </section>

      <section>
        <h2>Popular tests</h2>
        <p class="caption">
          Same metrics, split by Monkeytype's standard presets instead of pooled together. This is where "which
          specific test am I actually good/bad at" lives. Presets with 0 tests still show a row: that's the gap in
          your practice coverage, not a bug.
        </p>
        <PopularTestsTable :rows="data.popular_tests" />
      </section>

      <section>
        <h2>Action plan</h2>
        <ActionPlan :actions="data.actions" />
      </section>

      <section>
        <h2>Open questions (from Typing Speed.md)</h2>
        <OpenQuestions
          :insights="data.insights"
          :n-tests="data.kpis.n_tests"
          :bigram-count="bigramCount"
          :keylog-events="data.keylog_events"
          :has-tags="data.has_tags"
        />
      </section>

      <footer>monkeytype_tools &middot; {{ data.kpis.n_tests }} tests &middot; {{ data.keylog_events }} logged keystrokes</footer>
    </template>
  </div>
</template>
