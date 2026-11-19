<script setup>
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { auth } from './auth/cognito'

const route = useRoute()
const router = useRouter()
watch(() => auth.user, user => {
  if (!user && route.meta.requiresAuth) void router.replace('/login')
})
</script>

<template>
  <RouterView />
</template>
