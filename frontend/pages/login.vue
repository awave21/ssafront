<template>
  <div class="min-h-screen bg-slate-50">
    <AuthModal
      :is-open="true"
      :disable-close="true"
      @authenticated="handleAuthenticated"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AuthModal from '~/components/AuthModal.vue'
import {
  ensureFreshAccessToken,
  getStoredAccessToken,
  isAccessTokenExpired
} from '~/composables/authSessionManager'

definePageMeta({
  layout: false
})

const router = useRouter()

const redirectToDashboard = async () => {
  await router.replace('/dashboard')
}

const restoreSessionIfPossible = async () => {
  const token = getStoredAccessToken()
  if (token && !isAccessTokenExpired(token)) {
    await redirectToDashboard()
    return
  }

  const ensuredToken = await ensureFreshAccessToken({ forceRefresh: true })
  if (ensuredToken.token) {
    await redirectToDashboard()
  }
}

const handleAuthenticated = () => {
  void redirectToDashboard()
}

onMounted(() => {
  void restoreSessionIfPossible()
})
</script>
