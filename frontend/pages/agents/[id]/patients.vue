<template>
  <span class="sr-only">Перенаправление…</span>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { navigateTo } from '#app'

definePageMeta({
  middleware: 'auth',
})

const route = useRoute()
const raw = route.params.id
const id = raw ? (Array.isArray(raw) ? raw[0] : raw) : undefined

await navigateTo(
  id ? { path: '/patients', query: { agent: String(id) } } : '/patients',
  { replace: true },
)
</script>
