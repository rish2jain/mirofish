<template>
  <div class="compare-page">
    <header class="compare-header">
      <button type="button" class="back-btn" @click="router.push('/')" aria-label="Back to home">
        ← Home
      </button>
      <h1 class="title">Compare reports</h1>
      <p class="subtitle">
        Side-by-side markdown for two completed reports (typical A/B: fork a simulation, run both, compare reports).
        Simulation-level timeline/stats compare is not included here.
      </p>
    </header>

    <section class="compare-controls">
      <div class="field">
        <label for="rid-a">Report A</label>
        <input
          id="rid-a"
          v-model="idA"
          type="text"
          class="text-input"
          placeholder="report_…"
          autocomplete="off"
        />
      </div>
      <div class="field">
        <label for="rid-b">Report B</label>
        <input
          id="rid-b"
          v-model="idB"
          type="text"
          class="text-input"
          placeholder="report_…"
          autocomplete="off"
        />
      </div>
      <button type="button" class="primary-btn" :disabled="loading || !canSubmit" @click="runCompare">
        {{ loading ? 'Loading…' : 'Compare' }}
      </button>
    </section>

    <p v-if="errorMsg" class="error-banner" role="alert">{{ errorMsg }}</p>

    <section v-if="comparison && sectionRows.length" class="sections-compare" aria-label="Section-by-section comparison">
      <h2 class="sections-title">Sections</h2>
      <div class="sections-table-wrap">
        <table class="sections-table">
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Report A</th>
              <th scope="col">Report B</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in sectionRows" :key="idx">
              <td class="idx-cell">{{ idx + 1 }}</td>
              <td>
                <div class="sec-title">{{ row.titleA }}</div>
                <div class="md-body sm" v-html="renderMarkdown(row.bodyA)"></div>
              </td>
              <td>
                <div class="sec-title">{{ row.titleB }}</div>
                <div class="md-body sm" v-html="renderMarkdown(row.bodyB)"></div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="comparison" class="compare-grid">
      <article class="pane" aria-labelledby="pane-a-title">
        <h2 id="pane-a-title" class="pane-title">
          Report A
          <span class="mono">{{ comparison.report_a?.report_id }}</span>
        </h2>
        <p class="pane-meta mono">Sim: {{ comparison.report_a?.simulation_id || '—' }} · {{ comparison.report_a?.status }}</p>
        <div class="md-body" v-html="renderMarkdown(comparison.report_a?.markdown_content || '')"></div>
      </article>
      <article class="pane" aria-labelledby="pane-b-title">
        <h2 id="pane-b-title" class="pane-title">
          Report B
          <span class="mono">{{ comparison.report_b?.report_id }}</span>
        </h2>
        <p class="pane-meta mono">Sim: {{ comparison.report_b?.simulation_id || '—' }} · {{ comparison.report_b?.status }}</p>
        <div class="md-body" v-html="renderMarkdown(comparison.report_b?.markdown_content || '')"></div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { compareReports } from '../api/report'
import { renderMarkdown } from '../utils/markdown'

const route = useRoute()
const router = useRouter()

const idA = ref('')
const idB = ref('')
const loading = ref(false)
const errorMsg = ref('')
const comparison = ref(null)

const canSubmit = computed(() => idA.value.trim() && idB.value.trim())

function sectionHeading(content, index) {
  const line = (content || '').split('\n').find((l) => l.trim())
  if (line && /^#+\s/.test(line.trim())) return line.replace(/^#+\s*/, '').trim()
  return `Section ${index + 1}`
}

/** Align section lists from API (title + content) for side-by-side rows */
const sectionRows = computed(() => {
  const c = comparison.value
  if (!c) return []
  const lenA = c.sections_a?.length || 0
  const lenB = c.sections_b?.length || 0
  const max = Math.max(lenA, lenB)
  if (max === 0) return []
  const rows = []
  for (let i = 0; i < max; i++) {
    const sa = c.sections_a?.[i] || {}
    const sb = c.sections_b?.[i] || {}
    const bodyA = sa.content || sa.body || sa.markdown || ''
    const bodyB = sb.content || sb.body || sb.markdown || ''
    rows.push({
      titleA: sa.title || sa.section_title || sectionHeading(bodyA, i),
      titleB: sb.title || sb.section_title || sectionHeading(bodyB, i),
      bodyA,
      bodyB,
    })
  }
  return rows
})

const runCompare = async () => {
  errorMsg.value = ''
  comparison.value = null
  loading.value = true
  try {
    const res = await compareReports({
      report_id_a: idA.value.trim(),
      report_id_b: idB.value.trim(),
    })
    if (res.success && res.data) {
      comparison.value = res.data
    } else {
      errorMsg.value = res.error || 'Comparison failed'
    }
  } catch (e) {
    errorMsg.value = e.message || 'Request failed'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const q = route.query
  if (q.a) idA.value = String(q.a)
  if (q.b) idB.value = String(q.b)
  if (canSubmit.value) {
    runCompare()
  }
})
</script>

<style scoped>
.compare-page {
  min-height: 100vh;
  background: #fafafa;
  font-family: 'Space Grotesk', system-ui, sans-serif;
  padding: 1.25rem 1.5rem 2rem;
}

.compare-header {
  max-width: 1200px;
  margin: 0 auto 1.5rem;
}

.back-btn {
  border: none;
  background: transparent;
  color: #004e89;
  cursor: pointer;
  font-size: 0.95rem;
  margin-bottom: 0.75rem;
}

.title {
  font-size: 1.5rem;
  margin: 0 0 0.35rem;
}

.subtitle {
  margin: 0;
  color: #555;
  font-size: 0.95rem;
}

.compare-controls {
  max-width: 1200px;
  margin: 0 auto 1rem;
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 200px;
  flex: 1;
}

.field label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #333;
}

.text-input {
  padding: 0.5rem 0.65rem;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-family: ui-monospace, monospace;
  font-size: 0.9rem;
}

.primary-btn {
  padding: 0.55rem 1.25rem;
  background: #004e89;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
}

.primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-banner {
  max-width: 1200px;
  margin: 0 auto 1rem;
  padding: 0.65rem 1rem;
  background: #fde8e8;
  color: #8b1a1a;
  border-radius: 6px;
}

.compare-grid {
  max-width: 1400px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 900px) {
  .compare-grid {
    grid-template-columns: 1fr;
  }
}

.pane {
  background: #fff;
  border: 1px solid #eaeaea;
  border-radius: 8px;
  padding: 1rem 1.1rem;
  overflow: auto;
  max-height: calc(100vh - 220px);
}

.pane-title {
  font-size: 1rem;
  margin: 0 0 0.25rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: baseline;
}

.pane-meta {
  font-size: 0.75rem;
  color: #666;
  margin: 0 0 0.75rem;
}

.mono {
  font-family: ui-monospace, monospace;
  font-weight: 400;
}

.md-body :deep(.md-h2) {
  font-size: 1.1rem;
  margin-top: 1rem;
}

.sections-compare {
  max-width: 1400px;
  margin: 0 auto 1.25rem;
}

.sections-title {
  font-size: 1rem;
  margin: 0 0 0.5rem;
}

.sections-table-wrap {
  overflow: auto;
  border: 1px solid #eaeaea;
  border-radius: 8px;
  background: #fff;
}

.sections-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.sections-table th,
.sections-table td {
  border: 1px solid #eee;
  padding: 0.5rem 0.6rem;
  vertical-align: top;
}

.sections-table th {
  background: #f7f7f7;
  text-align: left;
}

.idx-cell {
  width: 2rem;
  color: #888;
  font-family: ui-monospace, monospace;
}

.sec-title {
  font-weight: 700;
  margin-bottom: 0.35rem;
}

.md-body.sm :deep(p) {
  font-size: 0.85rem;
  margin: 0.25rem 0;
}
</style>
