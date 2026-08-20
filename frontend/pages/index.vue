<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  getStoredAccessToken,
  isAccessTokenExpired,
} from '~/composables/authSessionManager'
import WelcomeHeader from '~/components/welcome/Header.vue'
import WelcomeHero from '~/components/welcome/Hero.vue'
import WelcomeFeatures from '~/components/welcome/Features.vue'
import WelcomeAnalytics from '~/components/welcome/Analytics.vue'
import WelcomeIntegrations from '~/components/welcome/Integrations.vue'
import WelcomeSteps from '~/components/welcome/Steps.vue'
import WelcomeCtaBanner from '~/components/welcome/CtaBanner.vue'
import WelcomeFooter from '~/components/welcome/Footer.vue'
import WelcomeHairline from '~/components/welcome/HairlineRule.vue'

definePageMeta({
  layout: false,
})

useHead({
  title: 'chatmedbot — ИИ-агенты для медицинских клиник',
  meta: [
    {
      name: 'description',
      content:
        'Умные ИИ-агенты для вашей клиники. Запись пациентов, аналитика, интеграции с МИС и CRM. Без шаблонных «здравствуйте, я бот».',
    },
  ],
  link: [
    { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
    { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
  ],
})

const router = useRouter()
const showLanding = ref(false)
const config = useRuntimeConfig()

onMounted(() => {
  if (config.public.landingMode === 'true' || config.public.landingMode === true) {
    showLanding.value = true
    return
  }
  const accessToken = getStoredAccessToken()
  if (accessToken && !isAccessTokenExpired(accessToken)) {
    router.replace('/dashboard')
    return
  }
  // lk.chatmedbot.ru — отправляем на красивую точку входа
  router.replace('/login')
})
</script>

<template>
  <div v-if="showLanding" class="welcome-root min-h-screen">
    <WelcomeHeader />
    <main>
      <WelcomeHero />
      <WelcomeHairline label="что внутри" />
      <WelcomeFeatures />
      <WelcomeHairline />
      <WelcomeAnalytics />
      <WelcomeHairline />
      <WelcomeIntegrations />
      <WelcomeHairline label="процесс внедрения" />
      <WelcomeSteps />
      <WelcomeCtaBanner />
    </main>
    <WelcomeFooter />
  </div>
  <div v-else class="min-h-screen flex items-center justify-center" style="background:#FAF7F2">
    <p class="mono" style="font-family:'JetBrains Mono',monospace;letter-spacing:.12em;text-transform:uppercase;font-size:11px;color:#5A5F5C">загрузка</p>
  </div>
</template>

<style src="~/assets/css/welcome.css"></style>

<style>
html { scroll-behavior: smooth; scroll-padding-top: 64px; }
</style>
