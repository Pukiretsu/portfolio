<script setup>
import { computed, ref } from 'vue'
import { auth, signOut } from '../auth/cognito'
import WorkspaceLayout from '../components/WorkspaceLayout.vue'

const name = computed(() => auth.user?.profile.email || 'your account')
const input = ref('')
const message = ref('')
const invalid = ref(false)
const signingOut = ref(false)
function formatJson() {
  try {
    input.value = JSON.stringify(JSON.parse(input.value), null, 2)
    invalid.value = false
    message.value = 'JSON formatted successfully.'
  } catch {
    invalid.value = true
    message.value = 'This is not valid JSON. Check the syntax and try again.'
  }
}
async function copy() {
  try {
    await navigator.clipboard.writeText(input.value)
    invalid.value = false
    message.value = 'Copied to clipboard.'
  } catch { invalid.value = true; message.value = 'Clipboard unavailable. Select and copy the text manually.' }
}
async function logout() {
  signingOut.value = true
  try { await signOut() }
  catch { signingOut.value = false; message.value = 'Could not finish signing out. Please try again.' }
}
</script>

<template>
  <WorkspaceLayout>
    <template #actions><button class="header-github disabled:opacity-60" :disabled="signingOut" @click="logout">{{ signingOut ? 'Signing out…' : 'Sign out' }}</button></template>
    <section>
      <p class="eyebrow mb-5">YOUR PERSONAL WORKSPACE</p>
      <h1 class="font-display text-5xl font-medium tracking-tighter md:text-6xl">A place to <span class="text-accent">make things.</span></h1>
      <p class="mt-5 break-words text-sm text-muted">Signed in as <span class="text-soft">{{ name }}</span></p>
    </section>
    <RouterLink to="/tools/minecraft" class="mt-10 block max-w-4xl rounded-xl border border-line bg-panel p-6 transition hover:border-accent/60 md:p-8">
      <span class="eyebrow">ON-DEMAND SERVER</span>
      <h2 class="mt-3 !text-2xl !tracking-tight">Minecraft</h2>
      <p class="mt-3 text-sm leading-7 text-muted">Launch a world, check live server status, and destroy the server when you're done.</p>
      <span class="text-link mt-4 inline-block">Open launcher ↗</span>
    </RouterLink>
    <section class="mt-8 max-w-4xl rounded-xl border border-line bg-panel p-6 md:p-8" aria-labelledby="json-title">
      <div class="flex flex-wrap items-start justify-between gap-4"><div><h2 id="json-title" class="!text-2xl !tracking-tight">JSON workbench</h2><p class="mt-2 text-sm leading-7 text-muted">Format and inspect JSON. Everything stays in this browser tab.</p></div><span class="tag">LOCAL ONLY</span></div>
      <label for="json-input" class="mb-3 mt-7 block text-sm text-soft">Your JSON</label>
      <textarea id="json-input" v-model="input" rows="13" spellcheck="false" placeholder='{"hello": "world"}' class="w-full rounded-lg border border-line bg-base p-4 font-mono text-sm leading-6 text-ink" :aria-invalid="invalid" aria-describedby="json-status"></textarea>
      <div class="mt-5 flex flex-wrap items-center gap-3"><button class="primary-button" @click="formatJson">Format JSON</button><button class="filter-button" :disabled="!input" @click="copy">Copy</button><button class="filter-button" @click="input = ''; message = ''; invalid = false">Clear</button></div>
      <p id="json-status" role="status" class="mt-4 min-h-6 text-sm" :class="invalid ? 'text-red-200' : 'text-accent'">{{ message }}</p>
    </section>
    <p class="mt-8 text-sm text-muted">Your workshop starts here. More tools can be added as you need them.</p>
  </WorkspaceLayout>
</template>
