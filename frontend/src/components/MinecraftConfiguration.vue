<script setup>
import { computed, onMounted, ref } from 'vue'
import { minecraftRequest } from '../api/minecraft'
const props = defineProps({ state: Object })
const emit = defineEmits(['saved'])
const config = ref(null), applied = ref(null), options = ref({ minecraft: [], loaders: [], fabricApi: [] })
const files = ref('{}'), error = ref(''), notice = ref(''), saving = ref(false)
const editable = computed(() => props.state && !props.state.resourcesExist && !props.state.busy && !saving.value)
async function versions(changed = false) {
  try {
    options.value = await minecraftRequest(`versions?minecraft=${encodeURIComponent(config.value.minecraftVersion)}`)
    if (changed && options.value.fabricApi?.length) config.value.fabricApiVersion = options.value.fabricApi[0]
  } catch { notice.value = 'Release suggestions are unavailable. Enter exact compatible versions; Start validates them before creating EC2.' }
}
async function load() {
  try { const value = await minecraftRequest('config'); config.value = value.desired; applied.value = value.applied; files.value = JSON.stringify(value.desired.modFiles, null, 2); versions() }
  catch (problem) { error.value = problem.message }
}
async function save() {
  if (!editable.value) return
  saving.value = true; error.value = ''; notice.value = ''
  try {
    const value = { ...config.value, modFiles: JSON.parse(files.value) }
    config.value = (await minecraftRequest('config', { method: 'POST', body: value })).desired
    emit('saved', config.value)
    notice.value = 'Configuration saved in S3. The next Start uses these settings.'
  } catch (problem) { error.value = problem.message }
  finally { saving.value = false }
}
onMounted(load)
</script>
<template>
  <section class="rounded-xl border border-line bg-panel p-6 md:p-8" aria-labelledby="config-title">
    <p class="eyebrow mb-4">SERVER BLUEPRINT</p><h2 id="config-title" class="!text-2xl !tracking-tight">Configuration</h2>
    <p class="mt-4 text-sm leading-7 text-muted">Settings are stored in S3 and loaded before Minecraft starts. Stop the server to edit. Heap and CPU limits stay tuned for the 4 GB ARM64 instance.</p>
    <p v-if="!editable && config" role="status" class="mt-4 text-sm text-amber-200">Stop the server and wait for the current operation to finish before editing.</p>
    <p v-if="applied" class="mt-4 text-xs text-muted">Running snapshot: Minecraft {{ applied.minecraftVersion }} · Fabric {{ applied.fabricLoaderVersion }} · API {{ applied.fabricApiVersion }}. These are the settings used at launch.</p>
    <p v-if="error" role="alert" class="mt-4 text-sm text-red-200">{{ error }}</p><p v-if="notice" role="status" class="mt-4 text-sm text-accent">{{ notice }}</p>
    <form v-if="config" class="mt-7" @submit.prevent="save">
      <fieldset :disabled="!editable" class="disabled:opacity-60">
        <legend class="text-sm font-medium text-ink">Versions</legend>
        <div class="mt-4 grid gap-4 sm:grid-cols-2">
          <label class="mc-label">Minecraft Java<input v-model="config.minecraftVersion" list="mc-releases" class="mc-input" required @change="versions(true)" /><datalist id="mc-releases"><option v-for="version in options.minecraft" :key="version" :value="version" /></datalist></label>
          <label class="mc-label">Fabric loader<input v-model="config.fabricLoaderVersion" list="mc-loaders" class="mc-input" required /><datalist id="mc-loaders"><option v-for="version in options.loaders" :key="version" :value="version" /></datalist></label>
          <label class="mc-label">Fabric API<input v-model="config.fabricApiVersion" list="mc-api-releases" class="mc-input" required /><datalist id="mc-api-releases"><option v-for="version in options.fabricApi" :key="version" :value="version" /></datalist></label>
          <label class="mc-label">Fabric installer<input v-model="config.fabricInstallerVersion" class="mc-input" required /></label>
        </div>
        <p class="mt-3 text-xs leading-6 text-amber-200">Use a world compatible with the selected version. Downgrading a world can corrupt it. Start checks required mod releases before provisioning.</p>
        <h3 class="mt-8 text-sm font-medium text-ink">server.properties</h3>
        <div class="mt-4 grid gap-4 sm:grid-cols-2">
          <label class="mc-label sm:col-span-2">Server message<input v-model="config.properties.motd" class="mc-input" maxlength="100" required /></label>
          <label v-for="[key, label, min, max] in [['max-players','Maximum players',1,20], ['view-distance','View distance',2,8], ['simulation-distance','Simulation distance',2,6], ['spawn-protection','Spawn protection',0,64]]" :key="key" class="mc-label">{{ label }}<input v-model.number="config.properties[key]" type="number" :min="min" :max="max" class="mc-input" required /></label>
          <label class="mc-label">Difficulty<select v-model="config.properties.difficulty" class="mc-input"><option v-for="value in ['peaceful','easy','normal','hard']" :key="value">{{ value }}</option></select></label>
          <label class="mc-label">Game mode<select v-model="config.properties.gamemode" class="mc-input"><option v-for="value in ['survival','creative','adventure','spectator']" :key="value">{{ value }}</option></select></label>
        </div>
        <div class="mt-5 flex flex-wrap gap-6"><label v-for="[key,label] in [['pvp','PvP'], ['online-mode','Verify Microsoft accounts'], ['white-list','Whitelist']]" :key="key" class="flex items-center gap-3 text-xs text-soft"><input v-model="config.properties[key]" type="checkbox" class="accent-accent" />{{ label }}</label></div>
        <p class="mt-3 text-xs leading-6 text-muted">Enabling the whitelist requires adding player entries through the server console/SSH.</p>
        <h3 class="mt-8 text-sm font-medium text-ink">Fabric mods</h3><p class="mt-3 text-xs text-muted">Fabric API is required. Enabled mods resolve compatible releases at launch.</p>
        <div class="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3"><label v-for="(_, name) in config.mods" :key="name" class="flex items-center gap-3 text-xs text-soft"><input v-model="config.mods[name]" type="checkbox" class="accent-accent" />{{ name }}</label></div>
        <label class="mc-label mt-6 block">C2ME workers<select v-model.number="config.c2meWorkers" class="mc-input"><option :value="1">1 — recommended</option><option :value="2">2</option></select></label>
        <label class="mc-label mt-7 block">Additional mod configuration files<textarea v-model="files" rows="9" class="mc-input font-mono" spellcheck="false" aria-describedby="mod-files-help"></textarea></label>
        <p id="mod-files-help" class="mt-2 text-xs leading-6 text-muted">JSON object mapping filenames to text, for example {"lithium.properties":"mixin.ai=true\n"}. Files go under config/. JSON, TOML, and properties files only; 4 KiB each. c2me.toml is managed by the worker setting.</p>
      </fieldset>
      <button class="primary-button mt-7 disabled:opacity-40" :disabled="!editable" type="submit">{{ saving ? 'Saving…' : 'Save configuration to S3' }}</button>
    </form>
    <p v-else class="mt-6 text-sm text-muted">Loading the S3 configuration…</p>
  </section>
</template>
<style scoped>
.mc-label { font-size:.78rem; color:var(--color-soft); }
.mc-input { display:block; width:100%; margin-top:.65rem; border:1px solid var(--color-line); background:var(--color-base); color:var(--color-ink); border-radius:.35rem; padding:.75rem; font-size:.85rem; }
</style>
