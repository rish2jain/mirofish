<template>
  <div class="compare-page">
    <header class="compare-header">
      <button type="button" class="back-btn" @click="router.push('/')" aria-label="Back to home">
        ← Home
      </button>
      <h1 class="title">Compare simulations</h1>
      <p class="subtitle">
        Side-by-side run summaries, recent timeline activity, and post volume across two simulations.
      </p>
    </header>

    <section class="compare-controls">
      <div class="field">
        <label for="sid-a">Simulation A</label>
        <input id="sid-a" v-model="idA" class="text-input" type="text" placeholder="sim_…" autocomplete="off" />
      </div>
      <div class="field">
        <label for="sid-b">Simulation B</label>
        <input id="sid-b" v-model="idB" class="text-input" type="text" placeholder="sim_…" autocomplete="off" />
      </div>
      <button type="button" class="primary-btn" :disabled="loading || !canSubmit" @click="runCompare">
        {{ loading ? 'Loading…' : 'Compare' }}
      </button>
    </section>

    <p v-if="errorMsg" class="error-banner" role="alert">{{ errorMsg }}</p>

    <section v-if="loading" class="skeleton-grid" aria-label="Loading simulation comparison">
      <div v-for="n in 4" :key="n" class="skeleton-card">
        <div class="skeleton-line short"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line short"></div>
      </div>
    </section>

    <template v-if="comparison">
      <section class="summary-grid" aria-label="Simulation summaries">
        <article class="summary-card">
          <header class="card-head">
            <h2>Simulation A</h2>
            <span class="mono">{{ comparison.simulation_a?.simulation?.simulation_id }}</span>
          </header>
          <ul class="metric-list">
            <li><strong>Status</strong><span>{{ comparison.simulation_a?.simulation?.status || '—' }}</span></li>
            <li><strong>Profiles</strong><span>{{ comparison.simulation_a?.simulation?.profiles_count ?? 0 }}</span></li>
            <li><strong>Entities</strong><span>{{ comparison.simulation_a?.simulation?.entities_count ?? 0 }}</span></li>
            <li><strong>Round</strong><span>{{ comparison.simulation_a?.run_state?.current_round ?? 0 }}</span></li>
            <li><strong>Twitter posts</strong><span>{{ comparison.simulation_a?.posts?.twitter?.total ?? 0 }}</span></li>
            <li><strong>Reddit posts</strong><span>{{ comparison.simulation_a?.posts?.reddit?.total ?? 0 }}</span></li>
          </ul>
        </article>

        <article class="summary-card delta-card">
          <header class="card-head">
            <h2>Delta</h2>
            <span class="pill">B minus A</span>
          </header>
          <ul class="metric-list">
            <li><strong>Profiles</strong><span>{{ signed(comparison.delta?.profiles_count) }}</span></li>
            <li><strong>Entities</strong><span>{{ signed(comparison.delta?.entities_count) }}</span></li>
            <li><strong>Current round</strong><span>{{ signed(comparison.delta?.current_round) }}</span></li>
            <li><strong>Twitter posts</strong><span>{{ signed(comparison.delta?.total_posts_twitter) }}</span></li>
            <li><strong>Reddit posts</strong><span>{{ signed(comparison.delta?.total_posts_reddit) }}</span></li>
          </ul>
        </article>

        <article class="summary-card">
          <header class="card-head">
            <h2>Simulation B</h2>
            <span class="mono">{{ comparison.simulation_b?.simulation?.simulation_id }}</span>
          </header>
          <ul class="metric-list">
            <li><strong>Status</strong><span>{{ comparison.simulation_b?.simulation?.status || '—' }}</span></li>
            <li><strong>Profiles</strong><span>{{ comparison.simulation_b?.simulation?.profiles_count ?? 0 }}</span></li>
            <li><strong>Entities</strong><span>{{ comparison.simulation_b?.simulation?.entities_count ?? 0 }}</span></li>
            <li><strong>Round</strong><span>{{ comparison.simulation_b?.run_state?.current_round ?? 0 }}</span></li>
            <li><strong>Twitter posts</strong><span>{{ comparison.simulation_b?.posts?.twitter?.total ?? 0 }}</span></li>
            <li><strong>Reddit posts</strong><span>{{ comparison.simulation_b?.posts?.reddit?.total ?? 0 }}</span></li>
          </ul>
        </article>
      </section>

      <section class="pane-grid">
        <article class="pane">
          <h2 class="pane-title">Timeline A</h2>
          <ul class="timeline-list">
            <li v-for="item in comparison.simulation_a?.timeline_tail || []" :key="`a-${item.round_num}`">
              <span class="round-tag">Round {{ item.round_num }}</span>
              <span>{{ item.total_actions }} actions · {{ item.active_agents_count }} active agents</span>
            </li>
          </ul>
        </article>

        <article class="pane">
          <h2 class="pane-title">Timeline B</h2>
          <ul class="timeline-list">
            <li v-for="item in comparison.simulation_b?.timeline_tail || []" :key="`b-${item.round_num}`">
              <span class="round-tag">Round {{ item.round_num }}</span>
              <span>{{ item.total_actions }} actions · {{ item.active_agents_count }} active agents</span>
            </li>
          </ul>
        </article>
      </section>

      <section class="pane-grid">
        <article class="pane">
          <h2 class="pane-title">Top agents A</h2>
          <ul class="metric-list compact">
            <li v-for="agent in comparison.simulation_a?.top_agents || []" :key="`agent-a-${agent.agent_id}`">
              <strong>{{ agent.agent_name || `Agent ${agent.agent_id}` }}</strong>
              <span>{{ agent.total_actions }} actions</span>
            </li>
          </ul>
        </article>

        <article class="pane">
          <h2 class="pane-title">Top agents B</h2>
          <ul class="metric-list compact">
            <li v-for="agent in comparison.simulation_b?.top_agents || []" :key="`agent-b-${agent.agent_id}`">
              <strong>{{ agent.agent_name || `Agent ${agent.agent_id}` }}</strong>
              <span>{{ agent.total_actions }} actions</span>
            </li>
          </ul>
        </article>
      </section>

      <section class="pane-grid">
        <article class="pane">
          <h2 class="pane-title">Recent posts A</h2>
          <div class="post-columns">
            <div class="post-column">
              <h3>Twitter</h3>
              <ul class="post-list">
                <li
                  v-for="(post, idx) in comparison.simulation_a?.posts?.twitter?.posts || []"
                  :key="`at-${post.id || post.created_at}-${idx}`"
                >
                  {{ post.content || post.text || '(no content)' }}
                </li>
              </ul>
            </div>
            <div class="post-column">
              <h3>Reddit</h3>
              <ul class="post-list">
                <li
                  v-for="(post, idx) in comparison.simulation_a?.posts?.reddit?.posts || []"
                  :key="`ar-${post.id || post.created_at}-${idx}`"
                >
                  {{ post.content || post.text || '(no content)' }}
                </li>
              </ul>
            </div>
          </div>
        </article>

        <article class="pane">
          <h2 class="pane-title">Recent posts B</h2>
          <div class="post-columns">
            <div class="post-column">
              <h3>Twitter</h3>
              <ul class="post-list">
                <li
                  v-for="(post, idx) in comparison.simulation_b?.posts?.twitter?.posts || []"
                  :key="`bt-${post.id || post.created_at}-${idx}`"
                >
                  {{ post.content || post.text || '(no content)' }}
                </li>
              </ul>
            </div>
            <div class="post-column">
              <h3>Reddit</h3>
              <ul class="post-list">
                <li
                  v-for="(post, idx) in comparison.simulation_b?.posts?.reddit?.posts || []"
                  :key="`br-${post.id || post.created_at}-${idx}`"
                >
                  {{ post.content || post.text || '(no content)' }}
                </li>
              </ul>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { compareSimulations } from '../api/simulation'

const route = useRoute()
const router = useRouter()

const idA = ref('')
const idB = ref('')
const loading = ref(false)
const errorMsg = ref('')
const comparison = ref(null)

const canSubmit = computed(() => idA.value.trim() && idB.value.trim())

const signed = (value) => {
  const n = Number(value || 0)
  return n > 0 ? `+${n}` : `${n}`
}

const runCompare = async () => {
  errorMsg.value = ''
  comparison.value = null
  loading.value = true
  try {
    const res = await compareSimulations({
      simulation_id_a: idA.value.trim(),
      simulation_id_b: idB.value.trim(),
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
  if (canSubmit.value) runCompare()
})
</script>

<style scoped>
.compare-page {
  min-height: 100vh;
  background: #f7f7f2;
  color: #111;
  font-family: 'Space Grotesk', system-ui, sans-serif;
  padding: 1.5rem;
}

.compare-header,
.compare-controls,
.summary-grid,
.pane-grid,
.skeleton-grid,
.error-banner {
  max-width: 1400px;
  margin: 0 auto 1rem;
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
  margin: 0 0 0.35rem;
  font-size: 1.65rem;
}

.subtitle {
  margin: 0;
  color: #555;
  max-width: 70ch;
}

.compare-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 220px;
  flex: 1;
}

.field label {
  font-size: 0.85rem;
  font-weight: 700;
}

.text-input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.7rem 0.85rem;
  border: 1px solid #d5d5cc;
  border-radius: 0.75rem;
  font-family: ui-monospace, monospace;
  font-size: 0.95rem;
  background: #fff;
}

.primary-btn {
  padding: 0.75rem 1.3rem;
  border: none;
  border-radius: 0.8rem;
  background: #004e89;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.primary-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.error-banner {
  padding: 0.8rem 1rem;
  border-radius: 0.8rem;
  background: #fde8e8;
  color: #8b1a1a;
}

.summary-grid,
.pane-grid,
.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.pane-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.summary-card,
.pane,
.skeleton-card {
  border: 1px solid #e3e3da;
  border-radius: 1rem;
  background: #fff;
  padding: 1rem;
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.04);
}

.card-head,
.pane-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.card-head h2,
.pane-title {
  margin: 0;
  font-size: 1rem;
}

.mono {
  font-family: ui-monospace, monospace;
  font-size: 0.85rem;
  color: #666;
}

.pill,
.round-tag {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #eef5fb;
  color: #004e89;
  padding: 0.2rem 0.55rem;
  font-size: 0.78rem;
  font-weight: 700;
}

.metric-list,
.timeline-list,
.post-list {
  list-style: none;
  margin: 1rem 0 0;
  padding: 0;
}

.metric-list li,
.timeline-list li {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.45rem 0;
  border-top: 1px solid #f0f0e7;
}

.metric-list.compact li {
  align-items: center;
}

.post-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.post-column h3 {
  margin: 0 0 0.6rem;
  font-size: 0.95rem;
}

.post-list li {
  border-top: 1px solid #f0f0e7;
  padding: 0.6rem 0;
  font-size: 0.9rem;
  line-height: 1.45;
}

.skeleton-line {
  height: 0.85rem;
  border-radius: 999px;
  background: linear-gradient(90deg, #ecece3 0%, #f7f7f2 50%, #ecece3 100%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
  margin-bottom: 0.75rem;
}

.skeleton-line.short {
  width: 45%;
}

@keyframes shimmer {
  from {
    background-position: 200% 0;
  }
  to {
    background-position: -200% 0;
  }
}

@media (max-width: 960px) {
  .summary-grid,
  .pane-grid,
  .skeleton-grid,
  .post-columns {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .compare-page {
    padding: 1rem;
  }

  .title {
    font-size: 1.35rem;
  }

  .compare-controls {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
