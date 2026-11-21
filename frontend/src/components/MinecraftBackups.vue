<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { minecraftRequest } from '../api/minecraft'
const props = defineProps({ state: Object })
const emit = defineEmits(['operation'])
const items = ref([]), cursor = ref(null), selected = ref(''), activeKey = ref(null)
const error = ref(''), notice = ref(''), working = ref(false), loading = ref(false)
const file = ref(null), progress = ref(0), confirmed = ref(false)
let xhr, disposed = false
const controller = new AbortController()
const offline = computed(() => props.state && !props.state.resourcesExist && !props.state.busy && !working.value)
const online = computed(() => props.state?.phase === 'online' && !props.state.busy && !working.value)
const size = value => `${(value / 1024 / 1024).toFixed(1)} MB`
async function refresh(more = false) {
  if (loading.value) return
  loading.value = true
  try {
    const value = await minecraftRequest('backups' + (more && cursor.value ? `?cursor=${encodeURIComponent(cursor.value)}` : ''), { signal: controller.signal })
    const entries = more ? [...items.value, ...value.items] : value.items
    items.value = [...new Map(entries.map(item => [item.key, item])).values()].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    cursor.value = value.nextCursor
    activeKey.value = (await minecraftRequest('config', { signal: controller.signal })).desired.worldKey
  } catch (problem) { if (!disposed) error.value = problem.message }
  finally { loading.value = false }
}
async function saveBackup() {
  if (!online.value) return
  working.value = true; error.value = ''
  try { emit('operation', await minecraftRequest('backup', { method: 'POST', body: {}, signal: controller.signal })); notice.value = 'Saving the current map to S3. Minecraft will resume after the snapshot.' }
  catch (problem) { error.value = problem.message }
  finally { working.value = false }
}
async function download(item) {
  try { const value = await minecraftRequest('backups/download', { method: 'POST', body: { key: item.key }, signal: controller.signal }); const link = document.createElement('a'); link.href = value.url; link.rel = 'noreferrer'; link.referrerPolicy = 'no-referrer'; link.click() }
  catch (problem) { error.value = problem.message }
}
async function chooseWorld(key) {
  if (!offline.value || (key && !confirmed.value)) return
  working.value = true; error.value = ''
  try { const value = await minecraftRequest('restore', { method: 'POST', body: { key }, signal: controller.signal }); activeKey.value = value.desired.worldKey; notice.value = key ? 'S3 world selected. Start restores it before Java starts.' : 'The next Start will generate a new world.'; confirmed.value = false }
  catch (problem) { error.value = problem.message }
  finally { working.value = false }
}
function chooseFile(event) {
  file.value = event.target.files?.[0] || null; progress.value = 0; error.value = ''
  if (file.value && (!file.value.name.toLowerCase().endsWith('.zip') || !file.value.size || file.value.size > 1024 ** 3)) { file.value = null; error.value = 'Choose a nonempty .zip map up to 1 GiB.' }
}
async function upload() {
  if (!offline.value || !file.value) return
  working.value = true; error.value = ''; notice.value = ''
  let operation, completed = false
  try {
    operation = await minecraftRequest('backups/upload', { method: 'POST', body: { filename: file.value.name, size: file.value.size }, signal: controller.signal })
    emit('operation', { phase: 'uploading', busy: true })
    const parts = []
    for (const part of operation.parts) {
      const start = (part.partNumber - 1) * operation.partSize
      const blob = file.value.slice(start, start + operation.partSize)
      const etag = await new Promise((resolve, reject) => {
        xhr = new XMLHttpRequest(); xhr.open('PUT', part.url); xhr.timeout = 180000
        xhr.upload.onprogress = event => { if (event.lengthComputable) progress.value = Math.round((start + event.loaded) / file.value.size * 100) }
        xhr.onload = () => xhr.status >= 200 && xhr.status < 300 && xhr.getResponseHeader('ETag') ? resolve(xhr.getResponseHeader('ETag')) : reject(new Error('S3 rejected an upload part'))
        xhr.onerror = xhr.ontimeout = () => reject(new Error('Upload interrupted; retry on a stable connection'))
        xhr.onabort = () => reject(new Error('Upload cancelled'))
        xhr.send(blob)
      })
      parts.push({ PartNumber: part.partNumber, ETag: etag })
    }
    const value = await minecraftRequest('backups/complete', { method: 'POST', body: { operationId: operation.operationId, parts }, signal: controller.signal })
    completed = true; selected.value = value.key; file.value = null
    notice.value = 'World uploaded to S3. Select it below for the next Start; nothing was sent to EC2.'
    await refresh()
  } catch (problem) { if (!disposed) error.value = problem.message }
  finally {
    xhr = null
    if (operation && !completed) {
      try { await minecraftRequest('backups/cancel', { method: 'POST', body: { operationId: operation.operationId } }) }
      catch { if (!disposed) error.value += ' Upload lock will expire automatically; refresh status before starting.' }
    }
    working.value = false
    if (operation) emit('operation', { phase: 'offline', busy: false })
  }
}
watch(() => props.state?.busy, (value, before) => { if (before && !value) refresh() })
onMounted(() => refresh())
onUnmounted(() => { disposed = true; controller.abort(); xhr?.abort() })
</script>
<template>
  <section class="rounded-xl border border-line bg-panel p-6 md:p-8" aria-labelledby="worlds-title">
    <p class="eyebrow mb-4">S3 WORLD LIBRARY</p><h2 id="worlds-title" class="!text-2xl !tracking-tight">Worlds</h2>
    <p class="mt-4 text-sm leading-7 text-muted">Uploads go only to private S3. Stop the server to upload or choose a map. Start reads the selected world directly from S3 before Minecraft runs.</p>
    <p v-if="error" role="alert" class="mt-5 text-sm text-red-200">{{ error }}</p><p v-if="notice" role="status" class="mt-5 text-sm leading-7 text-accent">{{ notice }}</p>
    <div class="mt-7 grid gap-7 xl:grid-cols-2">
      <div>
        <div class="flex items-center justify-between gap-4"><h3 class="text-sm font-medium text-ink">Saved maps</h3><button class="text-link text-xs" :disabled="loading" @click="refresh(false)">Refresh</button></div>
        <p class="mt-3 text-xs leading-6 text-muted">{{ activeKey ? 'A saved S3 world is selected for the next Start.' : 'Next Start: generate a new world.' }}</p>
        <ul class="mt-4 max-h-96 space-y-3 overflow-y-auto"><li v-for="item in items" :key="item.key" class="rounded-lg border p-4" :class="selected === item.key ? 'border-accent/50' : 'border-line'">
          <p class="text-sm text-soft">{{ new Date(item.createdAt).toLocaleString() }} <span v-if="activeKey === item.key" class="text-accent">· Next start</span></p><p class="mt-2 font-mono text-xs text-muted">{{ size(item.size) }} · world ZIP</p>
          <div class="mt-3 flex flex-wrap gap-5"><button class="text-link text-xs" @click="download(item)">Download ZIP ↓</button><button class="text-link text-xs disabled:opacity-40" :disabled="!offline" @click="selected = item.key; confirmed = false">{{ selected === item.key ? 'Selected' : 'Choose world' }}</button></div>
        </li></ul>
        <p v-if="!items.length && !loading" class="mt-4 text-xs text-muted">No saved worlds yet.</p><button v-if="cursor" class="text-link mt-4 text-xs" @click="refresh(true)">Load more</button>
        <label class="mt-6 flex items-start gap-3 text-xs leading-6 text-soft"><input v-model="confirmed" type="checkbox" class="mt-1 accent-accent" :disabled="!offline || !selected" />Use this S3 map on the next Start. I have checked version compatibility.</label>
        <button class="primary-button mt-4 disabled:opacity-40" :disabled="!offline || !selected || !confirmed" @click="chooseWorld(selected)">Use selected S3 world</button>
        <button class="text-link mt-5 block text-xs disabled:opacity-40" :disabled="!offline" @click="chooseWorld(null)">Generate a new world on next Start</button>
      </div>
      <div class="rounded-lg border border-line bg-base p-5">
        <h3 class="text-sm font-medium text-ink">Upload to S3</h3><p class="mt-3 text-xs leading-6 text-muted">ZIP up to 1 GiB, containing world/level.dat and all dimensions. Archive contents are validated during startup. Use a compatible Minecraft/mod version.</p>
        <p v-if="!offline" class="mt-3 text-xs leading-6 text-amber-200">Uploads are available only when the server is fully down and no operation is active.</p>
        <input type="file" accept=".zip,application/zip" aria-label="World ZIP" class="mt-5 block w-full min-w-0 text-xs text-soft file:mr-3 file:rounded file:border file:border-line file:bg-panel file:px-3 file:py-2 file:text-soft disabled:opacity-40" :disabled="!offline" @change="chooseFile" />
        <button class="primary-button mt-5 disabled:opacity-40" :disabled="!offline || !file" @click="upload">{{ working ? `Uploading… ${progress}%` : 'Upload world to S3' }}</button><progress v-if="working" :value="progress" max="100" class="mt-4 w-full accent-accent" aria-label="Upload progress"></progress>
        <div class="mt-7 border-t border-line pt-5"><h3 class="text-sm font-medium text-ink">Save a running world</h3><p class="mt-3 text-xs leading-6 text-muted">Save a manual S3 snapshot while online. Stop also saves the map automatically before Terraform removes EC2.</p><button class="text-link mt-4 text-sm disabled:opacity-40" :disabled="!online" @click="saveBackup">Save current world to S3</button></div>
        <p class="mt-6 text-xs leading-6 text-muted">Worlds stay in private S3 after server removal. Downloads work while offline. No direct browser-to-server uploads or live restores.</p>
      </div>
    </div>
  </section>
</template>
