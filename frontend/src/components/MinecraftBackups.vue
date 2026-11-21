<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { minecraftRequest } from '../api/minecraft'

const props = defineProps({ state: Object })
const emit = defineEmits(['operation'])
const items = ref([])
const cursor = ref(null)
const loading = ref(false)
const working = ref(false)
const error = ref('')
const notice = ref('')
const selected = ref('')
const file = ref(null)
const uploadedKey = ref('')
const progress = ref(0)
const confirm = ref(false)
const uploadInput = ref(null)
let disposed = false
let uploadRequest
const controller = new AbortController()
const busy = computed(() => working.value || props.state?.busy)
const ready = computed(() => !busy.value && props.state?.phase === 'online' && !props.state?.idle?.shutdownRequested)
const restoreKey = computed(() => file.value ? uploadedKey.value : selected.value)
const phases = { backing_up: 'Saving your world to S3…', restoring: 'Restoring your saved world…' }
const formatSize = value => `${(value / 1024 / 1024).toFixed(1)} MB`
const date = value => new Date(value).toLocaleString()

async function refresh(more = false) {
  if (loading.value) return
  loading.value = true
  try {
    const path = 'backups' + (more && cursor.value ? `?cursor=${encodeURIComponent(cursor.value)}` : '')
    const result = await minecraftRequest(path, { signal: controller.signal })
    if (disposed) return
    const combined = more ? [...items.value, ...result.items] : result.items
    items.value = [...new Map(combined.map(item => [item.key, item])).values()].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    cursor.value = result.nextCursor
    error.value = ''
  } catch (problem) { if (!disposed) error.value = problem.message }
  finally { loading.value = false }
}
async function operation(action) {
  if (!ready.value || (action === 'restore' && (!confirm.value || !restoreKey.value))) return
  working.value = true
  error.value = ''; notice.value = ''
  try {
    const result = await minecraftRequest(action, { method: 'POST', body: action === 'restore' ? { key: restoreKey.value, confirmRestore: true } : {}, signal: controller.signal })
    if (disposed) return
    emit('operation', result)
    notice.value = action === 'backup' ? 'Backup queued. The archive will appear below when it is safely saved.' : 'Restore queued. Players will disconnect while the map is replaced.'
    confirm.value = false
    if (action === 'restore') { file.value = null; uploadedKey.value = ''; if (uploadInput.value) uploadInput.value.value = '' }
  } catch (problem) { if (!disposed) error.value = problem.message }
  finally { working.value = false }
}
async function download(item) {
  error.value = ''
  try {
    const result = await minecraftRequest('backups/download', { method: 'POST', body: { key: item.key }, signal: controller.signal })
    if (disposed) return
    // S3 returns Content-Disposition: attachment; no credentials enter the URL.
    const link = document.createElement('a')
    link.href = result.url; link.rel = 'noreferrer'; link.referrerPolicy = 'no-referrer'
    link.click()
  } catch (problem) { if (!disposed) error.value = problem.message }
}
function chooseFile(event) {
  file.value = event.target.files?.[0] || null
  uploadedKey.value = ''; selected.value = ''; progress.value = 0; confirm.value = false; error.value = ''
  if (file.value && (!file.value.name.toLowerCase().endsWith('.zip') || !file.value.size || file.value.size > 1024 ** 3)) {
    error.value = 'Choose a nonempty .zip map backup up to 1 GiB.'; file.value = null
  }
}
async function upload() {
  if (!file.value || busy.value) return
  working.value = true; error.value = ''; notice.value = ''
  try {
    const result = await minecraftRequest('backups/upload', { method: 'POST', body: { filename: file.value.name, size: file.value.size }, signal: controller.signal })
    const form = new FormData()
    for (const [key, value] of Object.entries(result.upload.fields)) form.append(key, value)
    form.append('file', file.value)
    await new Promise((resolve, reject) => {
      uploadRequest = new XMLHttpRequest()
      uploadRequest.open('POST', result.upload.url)
      uploadRequest.timeout = 15 * 60 * 1000
      uploadRequest.upload.onprogress = event => { if (event.lengthComputable) progress.value = Math.round(event.loaded / event.total * 100) }
      uploadRequest.onload = () => uploadRequest.status >= 200 && uploadRequest.status < 300 ? resolve() : reject(new Error('S3 upload failed. Try uploading again.'))
      uploadRequest.onerror = () => reject(new Error('Upload interrupted. Check your connection and retry.'))
      uploadRequest.ontimeout = () => reject(new Error('Upload timed out. Please retry.'))
      uploadRequest.onabort = () => reject(new Error('Upload cancelled.'))
      uploadRequest.send(form)
    })
    if (!disposed) { uploadedKey.value = result.key; notice.value = 'Upload complete. Confirm below to restore this map.' }
  } catch (problem) { if (!disposed) error.value = problem.message }
  finally { working.value = false; uploadRequest = null }
}
watch(() => props.state?.busy, (value, previous) => { if (previous && !value) refresh() })
onMounted(refresh)
onUnmounted(() => { disposed = true; controller.abort(); uploadRequest?.abort() })
</script>

<template>
  <section class="mt-6 overflow-hidden rounded-xl border border-line bg-panel" aria-labelledby="map-vault-title">
    <div class="border-b border-line p-6 md:p-8">
      <p class="eyebrow mb-4">YOUR WORLD, KEPT SAFE</p>
      <div class="flex flex-wrap items-start justify-between gap-5">
        <div><h2 id="map-vault-title" class="!text-2xl !tracking-tight">World vault<span class="text-accent">.</span></h2><p class="mt-3 max-w-2xl text-sm leading-7 text-muted">Keep a copy before you log off. Private S3 backups survive server destruction and include the Overworld, Nether, End, and player data.</p></div>
        <span class="rounded-full border border-line px-3 py-2 font-mono text-xs text-accent">PRIVATE · S3</span>
      </div>
      <p v-if="error" role="alert" class="mt-5 text-sm leading-6 text-red-200">{{ error }}</p>
      <p v-if="notice" role="status" class="mt-5 text-sm leading-6 text-accent">{{ notice }}</p>
      <p v-if="phases[state?.phase]" role="status" class="mt-5 text-sm leading-6 text-amber-200">{{ phases[state.phase] }} Minecraft and idle cleanup pause during the transfer.</p>
    </div>
    <div class="grid gap-0 lg:grid-cols-2">
      <div class="p-6 md:p-8">
        <h3 class="text-base font-medium text-ink">Save the current world</h3>
        <p class="mt-3 text-xs leading-6 text-muted">Minecraft stops briefly to save a consistent map, then resumes. Players will disconnect. Saves are manual; save again before destroying a world you want to keep.</p>
        <button class="primary-button mt-5 disabled:cursor-not-allowed disabled:opacity-40" :disabled="!ready" @click="operation('backup')">Save backup to S3</button>
        <div class="mt-8 border-t border-line pt-6">
          <div class="flex flex-wrap items-center justify-between gap-3"><h3 class="text-base font-medium text-ink">Saved maps</h3><button class="text-link text-xs disabled:opacity-40" :disabled="loading" @click="refresh(false)">{{ loading ? 'Refreshing…' : 'Refresh' }}</button></div>
          <p v-if="!items.length && !loading" class="mt-5 text-xs leading-6 text-muted">No backups yet. Launch a server and save your first world.</p>
          <ul v-else class="mt-4 max-h-80 space-y-3 overflow-y-auto">
            <li v-for="item in items" :key="item.key" class="rounded-lg border p-4" :class="selected === item.key ? 'border-accent/50 bg-accent/5' : 'border-line bg-base'">
              <p class="text-sm text-soft">{{ date(item.createdAt) }}</p><p class="mt-1 font-mono text-xs text-muted">{{ formatSize(item.size) }} · All dimensions</p>
              <div class="mt-3 flex flex-wrap gap-5"><button class="text-link text-xs" @click="download(item)">Download ZIP ↓</button><button class="text-link text-xs disabled:opacity-40" :disabled="!ready" @click="selected = item.key; file = null; uploadedKey = ''; confirm = false; if (uploadInput) uploadInput.value = ''">{{ selected === item.key ? 'Selected for restore' : 'Select for restore' }}</button></div>
            </li>
          </ul>
          <button v-if="cursor" class="text-link mt-4 text-xs" :disabled="loading" @click="refresh(true)">Load more maps</button>
        </div>
      </div>
      <div class="border-t border-line bg-base/40 p-6 lg:border-l lg:border-t-0 md:p-8">
        <h3 class="text-base font-medium text-ink">Bring a world back</h3>
        <p class="mt-3 text-xs leading-6 text-muted">Select a saved map or upload a ZIP from your computer. Use the same Minecraft and mod versions. The ZIP must contain <code>world/level.dat</code>.</p>
        <label for="map-zip" class="mt-6 block text-xs text-soft">Upload a map ZIP · up to 1 GiB</label>
        <input id="map-zip" ref="uploadInput" type="file" accept=".zip,application/zip" class="mt-3 block w-full min-w-0 text-xs text-muted file:mr-3 file:rounded file:border file:border-line file:bg-panel file:px-3 file:py-2 file:text-soft disabled:opacity-40" :disabled="busy" @change="chooseFile" />
        <button v-if="file && !uploadedKey" class="text-link mt-4 text-sm disabled:opacity-40" :disabled="busy" @click="upload">{{ working ? `Uploading… ${progress}%` : 'Upload ZIP to S3' }}</button>
        <progress v-if="working && file && !uploadedKey" :value="progress" max="100" class="mt-4 w-full accent-accent" aria-label="Map upload progress"></progress>
        <div v-if="restoreKey" class="mt-6 rounded-lg border border-amber-200/30 bg-amber-200/5 p-4"><p class="text-xs leading-6 text-amber-200">{{ uploadedKey ? `Uploaded map: ${file?.name}` : `Saved map: ${date(items.find(item => item.key === selected)?.createdAt)}` }}</p><p class="mt-2 text-xs leading-6 text-muted">The current map will first be saved to S3, then replaced. Players will disconnect.</p></div>
        <label class="mt-6 flex items-start gap-3 text-xs leading-6 text-soft"><input v-model="confirm" type="checkbox" class="mt-1 h-4 w-4 shrink-0 accent-amber-200" :disabled="!ready || !restoreKey" />I want to replace the running world with the selected backup.</label>
        <button class="mt-5 w-full rounded border border-amber-200/50 px-4 py-3 text-sm text-amber-200 transition hover:bg-amber-200/10 disabled:cursor-not-allowed disabled:opacity-40" :disabled="!ready || !confirm || !restoreKey" @click="operation('restore')">Restore selected world</button>
        <p v-if="!state?.resourcesExist" class="mt-4 text-xs leading-6 text-muted">Launch a server before restoring a map. Saved maps remain available to download while the server is offline.</p>
        <p class="mt-6 text-xs leading-6 text-muted">Saved backups remain until you remove them in S3. Temporary uploads expire after one day. Private download links expire after five minutes.</p>
      </div>
    </div>
  </section>
</template>
