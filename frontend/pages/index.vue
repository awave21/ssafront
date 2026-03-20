<template>
  <div class="min-h-screen flex items-center justify-center bg-slate-50 px-4">
    <p class="text-slate-600">Переадресация...</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ensureFreshAccessToken,
  getStoredAccessToken,
  isAccessTokenExpired
} from '~/composables/authSessionManager'

definePageMeta({
  layout: false
})

const router = useRouter()

onMounted(async () => {
  const accessToken = getStoredAccessToken()
  if (accessToken && !isAccessTokenExpired(accessToken)) {
    await router.replace('/dashboard')
    return
  }

  const ensuredToken = await ensureFreshAccessToken({ forceRefresh: true })
  await router.replace(ensuredToken.token ? '/dashboard' : '/login')
})
</script>