<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { completeSignIn } from '../auth/cognito'
import WorkspaceLayout from '../components/WorkspaceLayout.vue'

const router = useRouter()
onMounted(async () => {
  try {
    await completeSignIn()
    await router.replace('/tools')
  } catch {
    // Strip authorization codes and provider errors from browser history.
    window.history.replaceState({}, '', '/auth/callback')
    await router.replace({ path: '/login', query: { error: 'callback' } })
  }
})
</script>

<template>
  <WorkspaceLayout><section class="mx-auto max-w-lg py-12 text-center" role="status"><p class="eyebrow mb-5">ONE MOMENT</p><h1 class="font-display text-4xl tracking-tight">Opening your workspace.</h1><p class="mt-5 text-muted">Completing secure sign-in…</p></section></WorkspaceLayout>
</template>
