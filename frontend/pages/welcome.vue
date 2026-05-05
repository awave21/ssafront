<script setup lang="ts">
import Header from '~/components/welcome/Header.vue'
import Hero from '~/components/welcome/Hero.vue'
import Features from '~/components/welcome/Features.vue'
import Analytics from '~/components/welcome/Analytics.vue'
import Integrations from '~/components/welcome/Integrations.vue'
import Steps from '~/components/welcome/Steps.vue'
import CtaBanner from '~/components/welcome/CtaBanner.vue'
import FooterSection from '~/components/welcome/Footer.vue'
import HairlineRule from '~/components/welcome/HairlineRule.vue'

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
  link: [{ rel: 'preconnect', href: 'https://fonts.googleapis.com' }, { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' }],
})
</script>

<template>
  <div class="welcome-root min-h-screen">
    <Header />
    <main>
      <Hero />
      <HairlineRule label="что внутри" />
      <Features />
      <HairlineRule />
      <Analytics />
      <HairlineRule />
      <Integrations />
      <HairlineRule label="процесс внедрения" />
      <Steps />
      <CtaBanner />
    </main>
    <FooterSection />
  </div>
</template>

<style src="~/assets/css/welcome.css"></style>

<style>
html { scroll-behavior: smooth; scroll-padding-top: 64px; }
</style>
