<template>
  <div class="tools-page">
    <header class="hdr">
      <button type="button" class="link" @click="router.push('/')">← Home</button>
      <h1>Workflow tools</h1>
      <p class="sub">
        Export/import project bundles, Cypher (Kuzu), batch simulations, webhooks. Set
        <code>MIROFISH_API_KEY</code> on the server to require <code>Authorization: Bearer …</code> on protected routes.
      </p>
    </header>

    <section class="card">
      <h2>Service API key (client)</h2>
      <p class="hint">Stored only in this browser tab session (memory). Used as Bearer token when set.</p>
      <input v-model="apiKey" type="password" class="inp" placeholder="Optional Bearer token" autocomplete="off" />
    </section>

    <section class="card">
      <h2>Export project bundle</h2>
      <input v-model="exportProjectId" class="inp" placeholder="proj_…" />
      <div class="row">
        <button type="button" class="btn" @click="doExport">Download JSON</button>
        <button type="button" class="btn secondary" @click="doExportPreview">Preview in page</button>
      </div>
      <pre v-if="exportPreview" class="pre">{{ exportPreview }}</pre>
      <p v-if="exportErr" class="err">{{ exportErr }}</p>
    </section>

    <section class="card">
      <h2>Import project bundle</h2>
      <textarea v-model="importJson" class="ta" rows="8" placeholder='Paste bundle JSON (bundle_version: 1)' />
      <div class="row">
        <input v-model="userHeader" class="inp" placeholder="X-MiroFish-User (if server requires)" />
        <button type="button" class="btn" @click="doImport">Import</button>
      </div>
      <p v-if="importResult" class="ok">{{ importResult }}</p>
      <p v-if="importErr" class="err">{{ importErr }}</p>
    </section>

    <section class="card">
      <h2>Graph snapshot &amp; diff</h2>
      <input v-model="snapProjectId" class="inp" placeholder="Project ID" />
      <div class="row">
        <input v-model="snapLabel" class="inp" placeholder="Snapshot label" />
        <button type="button" class="btn" @click="doSnapshot">Save snapshot</button>
        <button type="button" class="btn secondary" @click="listSnaps">List</button>
      </div>
      <div class="row">
        <input v-model="diffA" class="inp" placeholder="snapshot id A" />
        <input v-model="diffB" class="inp" placeholder="snapshot id B" />
        <button type="button" class="btn" @click="doDiff">Diff</button>
      </div>
      <pre v-if="snapshotsJson" class="pre sm">{{ snapshotsJson }}</pre>
      <pre v-if="diffJson" class="pre sm">{{ diffJson }}</pre>
    </section>

    <section class="card">
      <h2>Batch create simulations</h2>
      <textarea v-model="batchJson" class="ta" rows="6" placeholder='[{"project_id":"proj_…","graph_id":"graph_…"}]' />
      <button type="button" class="btn" @click="doBatch">Run batch</button>
      <pre v-if="batchResult" class="pre sm">{{ batchResult }}</pre>
      <p v-if="batchErr" class="err">{{ batchErr }}</p>
    </section>

    <section class="card">
      <h2>Webhooks</h2>
      <input v-model="hookUrl" class="inp" placeholder="https://…" />
      <input v-model="hookSecret" class="inp" type="password" placeholder="Optional HMAC secret" />
      <button type="button" class="btn" @click="registerHook">Register</button>
      <button type="button" class="btn secondary" @click="loadHooks">List</button>
      <pre v-if="hooksJson" class="pre sm">{{ hooksJson }}</pre>
      <p v-if="hookErr" class="err">{{ hookErr }}</p>
    </section>

    <p class="foot">
      <router-link to="/templates/edit">Template editor</router-link>
      ·
      <router-link to="/report/compare">Compare reports</router-link>
      ·
      <router-link to="/simulation/compare">Compare simulations</router-link>
    </p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  exportProjectBundle,
  importProjectBundle,
  createGraphSnapshot,
  listGraphSnapshots,
  diffGraphSnapshots
} from '../api/graph'
import { batchCreateSimulations } from '../api/simulation'
import { listWebhooks, registerWebhook } from '../api/hooks'

const router = useRouter()
const apiKey = ref('')
const authHeaders = () => (apiKey.value.trim() ? { Authorization: `Bearer ${apiKey.value.trim()}` } : {})

const exportProjectId = ref('')
const exportPreview = ref('')
const exportErr = ref('')

const importJson = ref('')
const importErr = ref('')
const importResult = ref('')
const userHeader = ref('')

const snapProjectId = ref('')
const snapLabel = ref('snapshot')
const diffA = ref('')
const diffB = ref('')
const snapshotsJson = ref('')
const diffJson = ref('')

const batchJson = ref('[{"project_id":"","graph_id":""}]')
const batchResult = ref('')
const batchErr = ref('')

const hookUrl = ref('')
const hookSecret = ref('')
const hooksJson = ref('')
const hookErr = ref('')

const doExportPreview = async () => {
  exportErr.value = ''
  exportPreview.value = ''
  const id = exportProjectId.value?.trim()
  if (!id) {
    exportErr.value = 'Project ID is required'
    return
  }
  try {
    const res = await exportProjectBundle(id, authHeaders())
    if (res.success) exportPreview.value = JSON.stringify(res.data, null, 2)
    else exportErr.value = res.error || 'failed'
  } catch (e) {
    exportErr.value = e.message
  }
}

const doExport = async () => {
  exportErr.value = ''
  exportPreview.value = ''
  const pid = exportProjectId.value?.trim()
  if (!pid) {
    exportErr.value = 'Project ID is required'
    return
  }
  try {
    const base = import.meta.env.VITE_API_BASE_URL || ''
    const url = `${base}/api/graph/project/${encodeURIComponent(pid)}/export-bundle/file`
    const headers = { ...authHeaders() }
    const r = await fetch(url, { headers })
    if (!r.ok) throw new Error(await r.text())
    const blob = await r.blob()
    const a = document.createElement('a')
    const objectUrl = URL.createObjectURL(blob)
    a.href = objectUrl
    a.download = `mirofish-${pid}.json`
    a.click()
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
  } catch (e) {
    exportErr.value = e.message
  }
}

const doImport = async () => {
  importErr.value = ''
  importResult.value = ''
  try {
    const body = JSON.parse(importJson.value)
    const headers = { ...authHeaders() }
    if (userHeader.value.trim()) headers['X-MiroFish-User'] = userHeader.value.trim()
    const res = await importProjectBundle(body, headers)
    if (res.success) importResult.value = JSON.stringify(res.data)
    else importErr.value = res.error || 'failed'
  } catch (e) {
    importErr.value = e.message
  }
}

const doSnapshot = async () => {
  snapshotsJson.value = ''
  try {
    const res = await createGraphSnapshot(
      snapProjectId.value.trim(),
      snapLabel.value || 'snapshot',
      authHeaders()
    )
    snapshotsJson.value = JSON.stringify(res.data || res, null, 2)
  } catch (e) {
    snapshotsJson.value = e.message
  }
}

const listSnaps = async () => {
  diffJson.value = ''
  try {
    const res = await listGraphSnapshots(snapProjectId.value.trim(), authHeaders())
    snapshotsJson.value = JSON.stringify(res.data || res, null, 2)
  } catch (e) {
    snapshotsJson.value = e.message
  }
}

const doDiff = async () => {
  diffJson.value = ''
  try {
    const res = await diffGraphSnapshots(
      snapProjectId.value.trim(),
      diffA.value,
      diffB.value,
      authHeaders()
    )
    diffJson.value = JSON.stringify(res.data || res, null, 2)
  } catch (e) {
    diffJson.value = e.message
  }
}

const doBatch = async () => {
  batchErr.value = ''
  batchResult.value = ''
  try {
    const items = JSON.parse(batchJson.value)
    const res = await batchCreateSimulations(items, authHeaders())
    batchResult.value = JSON.stringify(res.data || res, null, 2)
  } catch (e) {
    batchErr.value = e.message
  }
}

const registerHook = async () => {
  hookErr.value = ''
  try {
    const res = await registerWebhook(
      { url: hookUrl.value.trim(), events: ['simulation.completed', 'simulation.failed'], secret: hookSecret.value },
      authHeaders()
    )
    if (!res.success) hookErr.value = res.error || 'failed'
    else await loadHooks()
  } catch (e) {
    hookErr.value = e.message
  }
}

const loadHooks = async () => {
  hookErr.value = ''
  try {
    const res = await listWebhooks(authHeaders())
    hooksJson.value = JSON.stringify(res.data || res, null, 2)
  } catch (e) {
    hookErr.value = e.message
  }
}
</script>

<style scoped>
.tools-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 1.25rem 1rem 2rem;
  font-family: system-ui, sans-serif;
}
.hdr h1 {
  font-size: 1.35rem;
  margin: 0.25rem 0;
}
.sub {
  color: #555;
  font-size: 0.9rem;
}
.link {
  border: none;
  background: none;
  color: #004e89;
  cursor: pointer;
  padding: 0;
}
.card {
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 1rem;
  margin-top: 1rem;
  background: #fff;
}
.card h2 {
  font-size: 1rem;
  margin: 0 0 0.5rem;
}
.inp,
.ta {
  width: 100%;
  box-sizing: border-box;
  margin: 0.25rem 0;
  padding: 0.45rem 0.5rem;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 0.9rem;
}
.ta {
  font-family: ui-monospace, monospace;
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.35rem;
}
.btn {
  padding: 0.45rem 0.85rem;
  background: #004e89;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
}
.btn.secondary {
  background: #eee;
  color: #222;
}
.pre {
  background: #f7f7f7;
  padding: 0.75rem;
  border-radius: 6px;
  overflow: auto;
  font-size: 0.75rem;
  max-height: 320px;
}
.pre.sm {
  max-height: 200px;
}
.err {
  color: #a40000;
}
.ok {
  color: #0a6b2a;
}
.hint {
  font-size: 0.8rem;
  color: #666;
}
.foot {
  margin-top: 1.5rem;
  font-size: 0.9rem;
}
code {
  font-size: 0.85em;
}
</style>
