<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import MinecraftConfiguration from '../components/MinecraftConfiguration.vue'
import WorkspaceLayout from '../components/WorkspaceLayout.vue'
import MinecraftBackups from '../components/MinecraftBackups.vue'
import { minecraftRequest } from '../api/minecraft'

const route = useRoute()
const menuOpen = ref(false)
const views = [{ id: 'status', label: 'Dashboard' }, { id: 'server', label: 'Start / Stop' }, { id: 'config', label: 'Configuration' }, { id: 'worlds', label: 'Worlds' }]
const view = computed(() => views.some(item => item.id === route.hash.slice(1)) ? route.hash.slice(1) : 'status')
const blueprint = ref(null)
const effectiveConfig = computed(() => blueprint.value?.applied || blueprint.value?.desired)
async function loadBlueprint() { try { blueprint.value = await minecraftRequest('config') } catch { /* Status remains usable if the config request fails. */ } }
watch(() => route.hash, loadBlueprint)
const state = ref(null)
const error = ref('')
const notice = ref('')
const requesting = ref(false)
const confirmDestroy = ref(false)
const lastChecked = ref('')
const clock = ref(Date.now())
const serverOffset = ref(0)
let clockTimer
let timer
let stopped = false
let pollController
let actionController
const phase = computed(() => state.value?.phase || 'checking')
const labels = { checking: 'Checking status', offline: 'Offline', provisioning: 'Provisioning', online: 'Online', destroying: 'Destroying', backing_up: 'Saving backup', restoring: 'Restoring world', uploading: 'Uploading world', configuring: 'Saving configuration', error: 'Needs attention' }
const busy = computed(() => requesting.value || state.value?.busy)
const canLaunch = computed(() => state.value && !busy.value && !state.value.resourcesExist && state.value.acceptEula)
const canDestroy = computed(() => state.value && !busy.value && (state.value.resourcesExist || phase.value === 'error'))
const workflowUrl = computed(() => /^https:\/\/github\.com\/Pukiretsu\/portfolio\/actions\/runs\/\d+$/.test(state.value?.workflowUrl || '') ? state.value.workflowUrl : '')
const remaining = computed(() => state.value?.idle?.deleteAt ? Math.max(0, Math.ceil((state.value.idle.deleteAt * 1000 - clock.value - serverOffset.value) / 1000)) : null)
const countdown = computed(() => remaining.value === null ? '—' : `${Math.floor(remaining.value / 60).toString().padStart(2, '0')}:${(remaining.value % 60).toString().padStart(2, '0')}`)

async function poll() {
  pollController = new AbortController()
  const timeout = setTimeout(() => pollController.abort(), 12000)
  try {
    const result = await minecraftRequest('status', { signal: pollController.signal })
    if (stopped) return
    state.value = result
    serverOffset.value = result.updatedAt * 1000 - Date.now()
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
    notice.value = action === 'deploy' ? 'Launch requested. The workflow will provision EC2, DNS, and the Minecraft server.' : 'Stop requested. The world will be saved to S3 before Terraform removes the server.'
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
onMounted(() => { poll(); loadBlueprint(); clockTimer = setInterval(() => { clock.value = Date.now() }, 1000) })
onUnmounted(() => { stopped = true; clearTimeout(timer); clearInterval(clockTimer); pollController?.abort(); actionController?.abort() })
</script>

<template>
  <WorkspaceLayout>
    <template #actions><RouterLink to="/tools" class="header-github">All tools</RouterLink></template>
    <div class="mc-workspace">
      <aside class="mc-sidebar">
        <button class="mc-menu-button" :aria-expanded="menuOpen" aria-controls="minecraft-nav" @click="menuOpen = !menuOpen"><span aria-hidden="true">☰</span> Minecraft menu</button>
        <nav id="minecraft-nav" aria-label="Minecraft workspace" :class="{ 'mc-nav-open': menuOpen }" class="mc-nav">
          <p class="eyebrow mb-5 hidden lg:block">MINECRAFT TOOLS</p>
          <RouterLink v-for="(item, index) in views" :key="item.id" :to="{ path: '/tools/minecraft', hash: '#' + item.id }" :aria-current="view === item.id ? 'page' : undefined" class="mc-nav-link" :class="{ 'mc-nav-active': view === item.id }" @click="menuOpen = false"><span class="font-mono text-xs opacity-50">0{{ index + 1 }}</span>{{ item.label }}</RouterLink>
        </nav>
      </aside>
      <section class="min-w-0 flex-1">
      <p class="eyebrow mb-5">YOUR ON-DEMAND WORLD</p>
      <div class="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
        <div><h1 class="font-display text-5xl font-medium tracking-tighter md:text-6xl">Minecraft<span class="text-accent">.</span></h1><p class="mt-5 max-w-xl text-sm leading-7 text-muted">Your server, settings, and S3 worlds in one workspace.</p></div>
        <span role="status" class="inline-flex w-fit items-center gap-3 rounded-full border border-line bg-panel px-5 py-3 text-sm" :class="phase === 'online' ? 'text-accent' : 'text-soft'"><span aria-hidden="true" class="h-2 w-2 rounded-full" :class="phase === 'online' ? 'bg-accent' : phase === 'error' ? 'bg-red-300' : 'bg-muted'"></span>{{ labels[phase] || 'Unknown' }}</span>
      </div>
      <p v-if="error" role="alert" class="mt-7 rounded-lg border border-red-400/30 bg-red-400/10 p-4 text-sm leading-6 text-red-200">{{ error }}</p>
      <p v-if="notice" role="status" class="mt-6 text-sm leading-6 text-accent">{{ notice }}</p>
      <p v-if="state?.message" class="mt-5 text-sm leading-7 text-muted">{{ state.message }}</p>
      <div class="mt-8">
        <section v-if="view === 'status'" class="rounded-xl border border-line bg-panel p-6 md:p-8" aria-labelledby="server-title">
          <p class="eyebrow mb-4">CONNECTION</p><h2 id="server-title" class="!text-2xl !tracking-tight">Your next adventure.</h2>
          <div class="mt-6 rounded-lg border border-line bg-base p-5"><p class="break-all font-mono text-lg text-accent">{{ state?.address || 'Loading address…' }}</p><p class="mt-2 text-xs leading-6 text-muted">Fabric Java Edition · TCP 25565 · direct IPv6 + IPv4 connection</p><p class="mt-2 text-xs leading-6 text-amber-200">{{ effectiveConfig?.properties['online-mode'] ? 'Account verification enabled' : 'Account verification disabled' }} · {{ effectiveConfig?.properties['white-list'] ? 'Whitelist enabled' : 'No whitelist' }}</p></div>
          <button v-if="state?.address" class="text-link mt-4" @click="copyAddress">Copy connection address</button>
          <div class="mt-8 grid grid-cols-2 gap-5 border-t border-line pt-6 sm:grid-cols-3">
            <div><p class="text-xs text-muted">Players</p><p class="mt-2 font-mono text-xl">{{ state?.telemetry ? `${state.telemetry.playersOnline} / ${state.telemetry.playersMax}` : '—' }}</p></div>
            <div><p class="text-xs text-muted">Probe latency</p><p class="mt-2 font-mono text-xl">{{ state?.telemetry ? `${state.telemetry.latencyMs} ms` : '—' }}</p></div>
            <div><p class="text-xs text-muted">Server version</p><p class="mt-2 break-words font-mono text-sm">{{ state?.telemetry?.version || effectiveConfig?.minecraftVersion || '—' }}</p></div>
          </div>
          <p v-if="effectiveConfig" class="mt-6 text-xs leading-6 text-muted">Fabric {{ effectiveConfig.fabricLoaderVersion }} · View {{ effectiveConfig.properties['view-distance'] }} · Simulation {{ effectiveConfig.properties['simulation-distance'] }} · {{ Object.values(effectiveConfig.mods).filter(Boolean).length }} optional mods enabled</p>
          <p v-if="state?.telemetry?.motd" class="mt-6 text-sm text-soft">{{ state.telemetry.motd }}</p>
          <section v-if="state?.resourcesExist" class="mt-7 rounded-lg border border-line bg-base p-5" aria-labelledby="idle-title">
            <h3 id="idle-title" class="text-sm font-medium">Automatic Terraform cleanup</h3>
            <template v-if="['backing_up', 'restoring'].includes(phase)"><p role="status" class="mt-3 text-sm text-accent">Map maintenance in progress. Idle cleanup pauses while the world is being transferred.</p></template>
            <template v-else-if="state?.idle?.shutdownRequested"><p role="status" class="mt-3 text-sm text-amber-200">Minecraft has stopped gracefully. The Terraform destroy workflow is being requested.</p></template>
            <template v-else-if="state?.idle?.monitoringHealthy">
              <p v-if="remaining !== null" class="mt-4 font-mono text-3xl tabular-nums" :class="remaining <= 60 ? 'text-red-200' : 'text-accent'" aria-label="Time until automatic deletion">{{ countdown }}</p>
              <p class="mt-3 text-xs leading-6 text-muted">{{ remaining === null ? 'Players are connected. The idle countdown is paused.' : state.idle.hasPlayed ? 'The server is empty. It will be deleted after 10 empty minutes.' : 'Nobody has joined yet. It will be deleted after 30 empty minutes.' }}</p>
              <p v-if="remaining !== null && remaining <= 60" role="alert" class="mt-3 text-sm text-red-200">Deletion is imminent. Join now to keep the world active.</p>
            </template>
            <p v-else class="mt-3 text-xs leading-6 text-amber-200">Waiting for a fresh activity heartbeat. Automatic deletion is blocked while monitoring is unavailable.</p>
            <p class="mt-3 text-xs leading-6 text-muted">Runs even when this page is closed. Automatic deletion removes the world disk permanently. Save a backup to keep your map.</p>
          </section>
          <p class="mt-8 text-xs leading-6 text-muted">{{ lastChecked ? `Last checked ${lastChecked}. Refreshes every 10 seconds.` : 'Checking the server through the secure control API…' }}</p>
        </section>
        <section v-if="view === 'server'" class="rounded-xl border border-line bg-panel p-6 md:p-8" aria-labelledby="controls-title">
          <p class="eyebrow mb-4">CONTROLS</p><h2 id="controls-title" class="!text-2xl !tracking-tight">Build. Play. Rest.</h2>
          <p v-if="blueprint" class="mt-5 text-sm leading-7 text-muted">Next Start: Minecraft {{ blueprint.desired.minecraftVersion }} · {{ blueprint.desired.worldKey ? 'Selected S3 world' : 'Generate a new world' }}. Change the blueprint in Configuration and Worlds.</p>
          <button class="primary-button mt-7 w-full disabled:cursor-not-allowed disabled:opacity-40" :disabled="!canLaunch" @click="act('deploy')">{{ requesting ? 'Sending request…' : 'Launch Server' }}</button>
          <p v-if="state && !state.acceptEula" class="mt-4 text-xs leading-6 text-muted">Owner setup required: accept the <a class="underline" href="https://aka.ms/MinecraftEULA" target="_blank" rel="noopener noreferrer">Minecraft EULA</a>, set MINECRAFT_ACCEPT_EULA=true, and run infrastructure deployment.</p>
          <p class="mt-5 text-xs leading-6 text-muted">Provisioning and first startup can take several minutes. Compute, disk, and public IPv4 charges apply while deployed.</p>
          <div class="mt-7 border-t border-line pt-6"><p class="text-sm font-medium text-red-200">Destructive shutdown</p><p class="mt-3 text-xs leading-6 text-muted">Stop saves the map to S3, then Terraform removes compute and the world disk. Start loads the selected S3 world with your saved configuration.</p><label class="mt-4 flex items-start gap-3 text-xs leading-6 text-soft"><input v-model="confirmDestroy" type="checkbox" class="mt-1 h-4 w-4 shrink-0 accent-red-300" :disabled="busy" />Save my world to S3 and remove the server resources.</label><button class="mt-5 w-full rounded border border-red-300/50 px-4 py-3 text-sm text-red-200 transition hover:bg-red-300/10 disabled:cursor-not-allowed disabled:opacity-40" :disabled="!canDestroy || !confirmDestroy" @click="act('destroy')">Save world & Stop Server</button></div>
          <a v-if="workflowUrl" :href="workflowUrl" target="_blank" rel="noopener noreferrer" class="text-link mt-6 inline-block">View active workflow ↗</a>
        </section>
      </div>
      <MinecraftConfiguration v-if="view === 'config'" :state="state" @saved="value => { blueprint = { desired: value, applied: null } }" />
      <MinecraftBackups v-if="view === 'worlds'" :state="state" @operation="result => { state = { ...state, ...result, busy: result.busy ?? true } }" />
      </section>
    </div>
  </WorkspaceLayout>
</template>

<style scoped>
.mc-workspace { display:flex; align-items:flex-start; gap:2rem; }
.mc-sidebar { width:12rem; flex-shrink:0; position:sticky; top:2rem; }
.mc-nav { display:flex; flex-direction:column; gap:.5rem; }
.mc-nav-link { display:flex; gap:1rem; align-items:center; padding:.9rem; border:1px solid transparent; border-radius:.5rem; color:var(--color-muted); font-size:.82rem; }
.mc-nav-link:hover,.mc-nav-active { background:var(--color-panel); border-color:var(--color-line); color:var(--color-accent); }
.mc-menu-button { display:none; }
@media(max-width:1023px) { .mc-workspace { display:block; } .mc-sidebar { width:100%; position:static; margin-bottom:2rem; } .mc-menu-button { display:flex; align-items:center; gap:.75rem; padding:.8rem 1rem; border:1px solid var(--color-line); border-radius:.4rem; font-size:.85rem; } .mc-nav { display:none; margin-top:.8rem; padding:.6rem; border:1px solid var(--color-line); border-radius:.5rem; } .mc-nav-open { display:flex; } }
</style>
