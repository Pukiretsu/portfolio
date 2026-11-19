<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSession, signIn } from '../auth/cognito'
import WorkspaceLayout from '../components/WorkspaceLayout.vue'

const route = useRoute()
const router = useRouter()
const busy = ref(false)
const error = ref(route.query.error === 'callback' ? 'Sign-in could not be completed. Please start again.' : '')

onMounted(async () => {
  try {
    if (await getSession()) await router.replace('/tools')
  } catch (problem) {
    error.value = problem.message
  }
})
async function login() {
  busy.value = true
  error.value = ''
  try { await signIn() }
  catch (problem) { error.value = problem.message; busy.value = false }
}
</script>

<template>
  <WorkspaceLayout>
    <div class="mx-auto grid max-w-5xl items-center gap-12 lg:grid-cols-2 lg:gap-20">
      <section>
        <p class="eyebrow mb-6">A LITTLE SPACE TO GET THINGS DONE</p>
        <h1 class="font-display text-5xl font-medium leading-tight tracking-tighter md:text-6xl">The workshop.<br /><span class="text-accent">Just for you.</span></h1>
        <p class="mt-7 max-w-md leading-8 text-muted">A personal workspace for useful little tools, experiments, and everyday tasks. A quieter corner behind the portfolio.</p>
        <RouterLink to="/" class="text-link mt-8 inline-block">Back to the portfolio</RouterLink>
      </section>
      <section class="rounded-xl border border-line bg-panel p-7 md:p-10" aria-labelledby="login-title">
        <div class="mb-8 flex h-12 w-12 items-center justify-center rounded-lg border border-accent/30 bg-accent/10 text-accent" aria-hidden="true"><svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2" /></svg></div>
        <h2 id="login-title" class="!text-2xl !tracking-tight">Welcome back.</h2>
        <p class="mt-3 text-sm leading-7 text-muted">Sign in with your invited account. You'll continue to a secure sign-in page, then return to your tools.</p>
        <p v-if="error" role="alert" class="mt-6 rounded-md border border-red-400/30 bg-red-400/10 p-4 text-sm leading-6 text-red-200">{{ error }}</p>
        <button type="button" class="primary-button mt-8 w-full disabled:cursor-wait disabled:opacity-60" :disabled="busy" @click="login">{{ busy ? 'Opening secure sign-in…' : 'Continue to sign in' }}<span aria-hidden="true">↗</span></button>
        <p class="mt-5 text-xs leading-6 text-muted">Personal access only. New accounts are created by invitation.</p>
      </section>
    </div>
  </WorkspaceLayout>
</template>
