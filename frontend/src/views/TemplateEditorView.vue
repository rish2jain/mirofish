<template>
  <div class="tpl-page">
    <header class="hdr">
      <button type="button" class="link" @click="router.push('/')">← Home</button>
      <h1>Template editor</h1>
      <p class="sub">
        Form-first editing for simulation templates. Server writes still require
        <code>MIROFISH_ALLOW_TEMPLATE_WRITE=1</code> or <code>FLASK_DEBUG=true</code>,
        and optionally a Bearer token when <code>MIROFISH_API_KEY</code> is enabled.
      </p>
    </header>

    <div
      v-if="templateListLoadFailed"
      class="list-load-banner"
      role="status"
    >
      <p v-if="msg && !ok" class="err banner-msg">{{ msg }}</p>
      <div class="banner-actions">
        <button
          type="button"
          class="btn secondary"
          :disabled="listRetryBusy || listLoadAttempts >= MAX_LIST_LOAD_ATTEMPTS"
          @click="retryLoadList({ manual: true })"
        >
          {{ listRetryBusy ? 'Loading…' : 'Retry loading templates' }}
        </button>
        <span v-if="listLoadAttempts > 0" class="hint">
          Attempt {{ listLoadAttempts }} / {{ MAX_LIST_LOAD_ATTEMPTS }}
          <template v-if="listLoadAttempts >= MAX_LIST_LOAD_ATTEMPTS"> — max attempts reached</template>
        </span>
      </div>
    </div>

    <section class="card">
      <div class="grid two">
        <div>
          <label class="lab">Bearer token</label>
          <input v-model="apiKey" type="password" class="inp" placeholder="Optional" autocomplete="off" />
        </div>
        <div>
          <label class="lab">Template</label>
          <select v-model="selectedId" class="inp" @change="loadOne">
            <option value="">Create new template</option>
            <option v-for="t in templateList" :key="t.id" :value="t.id">{{ t.name || t.id }}</option>
          </select>
        </div>
      </div>

      <div v-if="loading" class="skeleton-box" aria-label="Loading template">
        <div class="skeleton-line short"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line short"></div>
      </div>

      <div v-else class="form-grid">
        <div class="grid two">
          <div>
            <label class="lab">ID</label>
            <input v-model="form.id" class="inp" placeholder="template_id" />
          </div>
          <div>
            <label class="lab">Suggested rounds</label>
            <input v-model.number="form.suggested_rounds" class="inp" type="number" min="1" step="1" />
          </div>
        </div>

        <label class="lab">Name</label>
        <input v-model="form.name" class="inp" placeholder="Simulation template name" />

        <label class="lab">Description</label>
        <textarea v-model="form.description" class="ta" rows="3" />

        <label class="lab">Default requirement</label>
        <textarea v-model="form.default_requirement" class="ta" rows="5" />

        <label class="lab">System prompt addition</label>
        <textarea v-model="form.system_prompt_addition" class="ta" rows="5" />

        <label class="lab">Entity type hints</label>
        <div class="token-editor">
          <input
            v-model="entityHintInput"
            class="inp"
            placeholder="Type an entity hint and press Enter"
            @keydown.enter.prevent="addEntityHint"
          />
          <div class="chips">
            <button
              v-for="hint in form.entity_type_hints"
              :key="hint"
              type="button"
              class="chip"
              @click="removeEntityHint(hint)"
            >
              {{ hint }} ×
            </button>
          </div>
        </div>

        <details class="advanced">
          <summary>Advanced JSON</summary>
          <p class="hint">
            Use this for extra keys not covered by the form. The form fields above remain the source of truth and are merged into this object on save.
          </p>
          <textarea v-model="advancedJsonText" class="ta code" rows="12" spellcheck="false" />
        </details>
      </div>

      <div class="row">
        <button type="button" class="btn" :disabled="saving || loading" @click="save">
          {{ saving ? 'Saving…' : 'Save template' }}
        </button>
        <button type="button" class="btn secondary" :disabled="saving || loading" @click="resetForm">
          Reset
        </button>
        <span
          v-if="msg"
          :class="ok ? 'ok' : 'err'"
          aria-live="polite"
          aria-atomic="true"
        >{{ msg }}</span>
      </div>
    </section>

    <p class="foot">
      <router-link to="/tools">Workflow tools</router-link>
      ·
      <router-link to="/simulation/compare">Compare simulations</router-link>
    </p>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listTemplates, getTemplate, saveTemplate } from '../api/templates'

const router = useRouter()
const apiKey = ref('')
const templateList = ref([])
const selectedId = ref('')
const saving = ref(false)
const loading = ref(false)
const msg = ref('')
const ok = ref(false)

/** Template list bootstrap (GET /api/templates/) — separate from per-template load/save messaging. */
const MAX_LIST_LOAD_ATTEMPTS = 5
const LIST_LOAD_BACKOFF_MS = [450, 900]
const listLoadAttempts = ref(0)
const listRetryBusy = ref(false)
const templateListLoadFailed = ref(false)

const entityHintInput = ref('')
const advancedJsonText = ref('{}')

const blankForm = () => ({
  id: '',
  name: '',
  description: '',
  default_requirement: '',
  suggested_rounds: 10,
  entity_type_hints: [],
  system_prompt_addition: '',
})

const form = ref(blankForm())

const authHeaders = () => (apiKey.value.trim() ? { Authorization: `Bearer ${apiKey.value.trim()}` } : {})

const loadList = async () => {
  const list = await listTemplates()
  templateList.value = Array.isArray(list) ? list : []
}

/**
 * Load template list with optional automatic backoff retries (mount) or a single try (manual).
 * Updates msg / ok on failure; resets attempt counter on success.
 */
const retryLoadList = async ({ manual = false } = {}) => {
  listRetryBusy.value = true
  if (!manual) {
    msg.value = ''
  }
  const backoffs = manual ? [] : LIST_LOAD_BACKOFF_MS
  const triesThisCall = 1 + backoffs.length

  try {
    for (let i = 0; i < triesThisCall; i++) {
      if (listLoadAttempts.value >= MAX_LIST_LOAD_ATTEMPTS) {
        msg.value = `Could not load templates after ${MAX_LIST_LOAD_ATTEMPTS} attempts. Check the server and /api proxy.`
        ok.value = false
        templateListLoadFailed.value = true
        return
      }

      listLoadAttempts.value += 1
      try {
        await loadList()
        msg.value = ''
        ok.value = true
        templateListLoadFailed.value = false
        listLoadAttempts.value = 0
        return
      } catch (e) {
        ok.value = false
        templateListLoadFailed.value = true
        msg.value = e.message || 'Failed to load template list'
        const canBackoff =
          i < triesThisCall - 1 &&
          listLoadAttempts.value < MAX_LIST_LOAD_ATTEMPTS &&
          backoffs[i] != null
        if (canBackoff) {
          await new Promise((r) => setTimeout(r, backoffs[i]))
        }
      }
    }
  } finally {
    listRetryBusy.value = false
  }
}

const resetForm = () => {
  form.value = blankForm()
  advancedJsonText.value = '{}'
  entityHintInput.value = ''
  if (!loading.value) msg.value = ''
}

const applyTemplate = (data) => {
  form.value = {
    id: data.id || '',
    name: data.name || '',
    description: data.description || '',
    default_requirement: data.default_requirement || '',
    suggested_rounds: Number(data.suggested_rounds || 10),
    entity_type_hints: Array.isArray(data.entity_type_hints) ? [...data.entity_type_hints] : [],
    system_prompt_addition: data.system_prompt_addition || '',
  }

  const extras = { ...data }
  for (const key of Object.keys(form.value)) {
    delete extras[key]
  }
  advancedJsonText.value = JSON.stringify(extras, null, 2)
}

const loadOne = async () => {
  msg.value = ''
  if (!selectedId.value) {
    resetForm()
    return
  }
  loading.value = true
  try {
    const data = await getTemplate(selectedId.value)
    applyTemplate(data)
  } catch (e) {
    msg.value = e.message
    ok.value = false
  } finally {
    loading.value = false
  }
}

const addEntityHint = () => {
  const value = entityHintInput.value.trim()
  if (!value || form.value.entity_type_hints.includes(value)) return
  form.value.entity_type_hints.push(value)
  entityHintInput.value = ''
}

const removeEntityHint = (hint) => {
  form.value.entity_type_hints = form.value.entity_type_hints.filter((item) => item !== hint)
}

const save = async () => {
  saving.value = true
  msg.value = ''
  try {
    const extras = JSON.parse(advancedJsonText.value || '{}')
    if (extras === null || Array.isArray(extras) || typeof extras !== 'object') {
      throw new Error('Advanced JSON must be an object')
    }

    const suggestedRounds = Number(form.value.suggested_rounds ?? 0)
    if (!Number.isFinite(suggestedRounds) || suggestedRounds < 1) {
      throw new Error('Template suggested_rounds must be at least 1')
    }

    const payload = {
      ...extras,
      id: form.value.id.trim(),
      name: form.value.name.trim(),
      description: form.value.description.trim(),
      default_requirement: form.value.default_requirement.trim(),
      suggested_rounds: suggestedRounds,
      entity_type_hints: form.value.entity_type_hints.filter(Boolean),
      system_prompt_addition: form.value.system_prompt_addition.trim(),
    }

    if (!payload.id) throw new Error('Template id is required')
    if (!payload.name) throw new Error('Template name is required')

    await saveTemplate(payload.id, payload, authHeaders())
    msg.value = 'Template saved'
    ok.value = true
    selectedId.value = payload.id
    await loadList()
    templateListLoadFailed.value = false
    listLoadAttempts.value = 0
  } catch (e) {
    msg.value = e.message || 'Save failed'
    ok.value = false
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  retryLoadList({ manual: false })
})
</script>

<style scoped>
.tpl-page {
  max-width: 980px;
  margin: 0 auto;
  padding: 1.25rem 1rem 2rem;
  font-family: 'Space Grotesk', system-ui, sans-serif;
}

.hdr h1 {
  margin: 0.25rem 0;
  font-size: 1.5rem;
}

.sub {
  color: #555;
  font-size: 0.95rem;
  max-width: 68ch;
}

.link {
  border: none;
  background: none;
  color: #004e89;
  cursor: pointer;
  padding: 0;
}

.list-load-banner {
  margin-top: 1rem;
  padding: 0.85rem 1rem;
  border: 1px solid #e8d9d9;
  border-radius: 0.75rem;
  background: #fff8f8;
}

.banner-msg {
  margin: 0 0 0.65rem;
  font-size: 0.92rem;
}

.banner-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.btn.secondary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.card {
  border: 1px solid #e5e5e5;
  border-radius: 1rem;
  padding: 1rem;
  margin-top: 1rem;
  background: #fff;
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.04);
}

.grid.two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.form-grid {
  margin-top: 1rem;
}

.lab {
  display: block;
  font-size: 0.82rem;
  font-weight: 700;
  margin: 0.6rem 0 0.3rem;
}

.inp,
.ta {
  width: 100%;
  box-sizing: border-box;
  padding: 0.7rem 0.8rem;
  border: 1px solid #d2d2d2;
  border-radius: 0.75rem;
  background: #fff;
  font: inherit;
}

.ta.code {
  font-family: ui-monospace, monospace;
  font-size: 0.88rem;
}

.token-editor {
  display: grid;
  gap: 0.75rem;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.chip {
  border: 1px solid #d7e4f0;
  background: #eef5fb;
  color: #004e89;
  border-radius: 999px;
  padding: 0.35rem 0.65rem;
  cursor: pointer;
}

.advanced {
  margin-top: 1rem;
  border-top: 1px solid #efefef;
  padding-top: 1rem;
}

.hint {
  font-size: 0.88rem;
  color: #666;
}

.row {
  margin-top: 1rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.btn {
  padding: 0.65rem 1.1rem;
  background: #004e89;
  color: #fff;
  border: none;
  border-radius: 0.75rem;
  cursor: pointer;
  font-weight: 700;
}

.btn.secondary {
  background: #f3f6f8;
  color: #00365d;
}

.err {
  color: #a40000;
}

.ok {
  color: #0a6b2a;
}

.skeleton-box {
  margin-top: 1rem;
}

.skeleton-line {
  height: 0.9rem;
  border-radius: 999px;
  background: linear-gradient(90deg, #ecece3 0%, #f7f7f2 50%, #ecece3 100%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
  margin-bottom: 0.75rem;
}

.skeleton-line.short {
  width: 45%;
}

.foot {
  margin-top: 1rem;
}

@keyframes shimmer {
  from {
    background-position: 200% 0;
  }
  to {
    background-position: -200% 0;
  }
}

@media (max-width: 760px) {
  .grid.two {
    grid-template-columns: 1fr;
  }
}
</style>
