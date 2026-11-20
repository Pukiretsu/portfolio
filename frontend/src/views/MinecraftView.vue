<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import WorkspaceLayout from '../components/WorkspaceLayout.vue'
import { minecraftRequest } from '../api/minecraft'

const state = ref(null)
const error = ref('')
const notice = ref('')
const requesting = ref(false)
const confirmDestroy = ref(false)
const lastChecked = ref('')
let timer
let stopped = false
let pollController
let actionController
const phase = computed(() => state.value?.phase || 'checking')
const labels = { checking: 'Checking status', offline: 'Offline', provisioning: 'Provisioning', online: 'Online', destroying: 'Destroying', error: 'Needs attention' }
const busy = computed(() => requesting.value || state.value?.busy)
const canLaunch = computed(() => state.value && !busy.value && !state.value.resourcesExist && state.value.acceptEula)
const canDestroy = computed(() => state.value && !busy.value && (state.value.resourcesExist || phase.value === 'error'))
const workflowUrl = computed(() => /^https:\/\/github\.com\/Pukiretsu\/portfolio\/actions\/runs\/\d+$/.test(state.value?.workflowUrl || '') ? state.value.workflowUrl : '')

async function poll() {
  pollController = new AbortController()
  const timeout = setTimeout(() => pollController.abort(), 12000)
  try {
    const result = await minecraftRequest('status', { signal: pollController.signal })
    if (stopped) return
    state.value = result
    lastChecked.value = new Date().toLocaleTimeString()
    error.value = ''
  } catch (problem) {
    if (!stopped) error.value = problem.name === 'AbortError' ? 'Status check timed out. Retrying shortly.' : problem.message
  } finally {
    clearTimeout(timeout)
    if (!stopped) timer = setTimeout(poll, 10000)
  }
}

async function act(action) {
  if (requesting.value) return
  if (action === 'destroy' && !confirmDestroy.value) return
  requesting.value = true
  error.value = ''
  notice.value = ''
  actionController = new AbortController()
  const timeout = setTimeout(() => actionController.abort(), 25000)
  try {
    const result = await minecraftRequest(action, { method: 'POST', body: action === 'destroy' ? { confirmDestroy: true } : {}, signal: actionController.signal })
    if (stopped) return
    state.value = { ...state.value, phase: result.phase, busy: true }
    notice.value = action === 'deploy' ? 'Launch requested. The workflow will provision EC2, DNS, and the Minecraft server.' : 'Destroy requested. The workflow will remove the server, world disk, and DNS.'
    confirmDestroy.value = false
  } catch (problem) {
    if (!stopped) error.value = problem.name === 'AbortError' ? 'Request timed out. Check the workflow and status before retrying.' : problem.message
  } finally {
    clearTimeout(timeout)
    requesting.value = false
  }
}
async function copyAddress() {
  try { await navigator.clipboard.writeText(state.value.address); notice.value = 'Connection address copied.' }
  catch { error.value = 'Clipboard unavailable. Select and copy the address manually.' }
}
onMounted(poll)
onUnmounted(() => { stopped = true; clearTimeout(timer); pollController?.abort(); actionController?.abort() })
</script>

<template>
  <WorkspaceLayout>
    <template #actions><RouterLink to="/tools" class="header-github">All tools</RouterLink></template>
    <section class="max-w-5xl">
      <p class="eyebrow mb-5">YOUR ON-DEMAND WORLD</p>
      <div class="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
        <div><h1 class="font-display text-5xl font-medium tracking-tighter md:text-6xl">Minecraft<span class="text-accent">.</span></h1><p class="mt-5 max-w-xl text-sm leading-7 text-muted">Launch a Java Edition server when you need it. Tear it down when you're done.</p></div>
        <span role="status" class="inline-flex w-fit items-center gap-3 rounded-full border border-line bg-panel px-5 py-3 text-sm" :class="phase === 'online' ? 'text-accent' : 'text-soft'"><span aria-hidden="true" class="h-2 w-2 rounded-full" :class="phase === 'online' ? 'bg-accent' : phase === 'error' ? 'bg-red-300' : 'bg-muted'"></span>{{ labels[phase] || 'Unknown' }}</span>
      </div>
      <p v-if="error" role="alert" class="mt-7 rounded-lg border border-red-400/30 bg-red-400/10 p-4 text-sm leading-6 text-red-200">{{ error }}</p>
      <p v-if="notice" role="status" class="mt-6 text-sm leading-6 text-accent">{{ notice }}</p>
      <p v-if="state?.message" class="mt-5 text-sm leading-7 text-muted">{{ state.message }}</p>
      <div class="mt-10 grid gap-6 lg:grid-cols-3">
        <section class="rounded-xl border border-line bg-panel p-6 lg:col-span-2 md:p-8" aria-labelledby="server-title">
          <p class="eyebrow mb-4">CONNECTION</p><h2 id="server-title" class="!text-2xl !tracking-tight">Your next adventure.</h2>
          <div class="mt-6 rounded-lg border border-line bg-base p-5"><p class="break-all font-mono text-lg text-accent">{{ state?.address || 'Loading address…' }}</p><p class="mt-2 text-xs leading-6 text-muted">Minecraft Java Edition · TCP 25565 · direct IPv6 + IPv4 connection</p></div>
          <button v-if="state?.address" class="text-link mt-4" @click="copyAddress">Copy connection address</button>
          <div class="mt-8 grid grid-cols-2 gap-5 border-t border-line pt-6 sm:grid-cols-3">
            <div><p class="text-xs text-muted">Players</p><p class="mt-2 font-mono text-xl">{{ state?.telemetry ? `${state.telemetry.playersOnline} / ${state.telemetry.playersMax}` : '—' }}</p></div>
            <div><p class="text-xs text-muted">Probe latency</p><p class="mt-2 font-mono text-xl">{{ state?.telemetry ? `${state.telemetry.latencyMs} ms` : '—' }}</p></div>
            <div><p class="text-xs text-muted">Server version</p><p class="mt-2 break-words font-mono text-sm">{{ state?.telemetry?.version || '—' }}</p></div>
          </div>
          <p v-if="state?.telemetry?.motd" class="mt-6 text-sm text-soft">{{ state.telemetry.motd }}</p>
          <p class="mt-8 text-xs leading-6 text-muted">{{ lastChecked ? `Last checked ${lastChecked}. Refreshes every 10 seconds.` : 'Checking the server through the secure control API…' }}</p>
        </section>
        <section class="rounded-xl border border-line bg-panel p-6 md:p-8" aria-labelledby="controls-title">
          <p class="eyebrow mb-4">CONTROLS</p><h2 id="controls-title" class="!text-2xl !tracking-tight">Build. Play. Rest.</h2>
          <button class="primary-button mt-7 w-full disabled:cursor-not-allowed disabled:opacity-40" :disabled="!canLaunch" @click="act('deploy')">{{ requesting ? 'Sending request…' : 'Launch Server' }}</button>
          <p v-if="state && !state.acceptEula" class="mt-4 text-xs leading-6 text-muted">Owner setup required: accept the <a class="underline" href="https://aka.ms/MinecraftEULA" target="_blank" rel="noopener noreferrer">Minecraft EULA</a>, set MINECRAFT_ACCEPT_EULA=true, and run infrastructure deployment.</p>
          <p class="mt-5 text-xs leading-6 text-muted">Provisioning and first startup can take several minutes. Compute, disk, and public IPv4 charges apply while deployed.</p>
          <div class="mt-7 border-t border-line pt-6"><p class="text-sm font-medium text-red-200">Destructive shutdown</p><p class="mt-3 text-xs leading-6 text-muted">Destroy permanently deletes this server and its world disk. A later launch starts a fresh world.</p><label class="mt-4 flex items-start gap-3 text-xs leading-6 text-soft"><input v-model="confirmDestroy" type="checkbox" class="mt-1 h-4 w-4 shrink-0 accent-red-300" :disabled="busy" />I understand the server and world data will be deleted.</label><button class="mt-5 w-full rounded border border-red-300/50 px-4 py-3 text-sm text-red-200 transition hover:bg-red-300/10 disabled:cursor-not-allowed disabled:opacity-40" :disabled="!canDestroy || !confirmDestroy" @click="act('destroy')">Stop / Destroy Server</button></div>
          <a v-if="workflowUrl" :href="workflowUrl" target="_blank" rel="noopener noreferrer" class="text-link mt-6 inline-block">View active workflow ↗</a>
        </section>
      </div>
    </section>
  </WorkspaceLayout>
</template>
