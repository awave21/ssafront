<template>
  <AgentPageShell title="Настройки" :hide-actions="true">
    <AgentSettingsWorkspace />
  </AgentPageShell>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentSettingsWorkspace from '~/components/agents/settings/AgentSettingsWorkspace.vue'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})

const route = useRoute()
const router = useRouter()

// Редирект на /settings?section=apikeys, чтобы sub-nav сразу подсветил нужный пункт.
onMounted(() => {
  if (!route.query.section) {
    router.replace({ path: route.path.replace(/\/api-keys$/, '/settings'), query: { section: 'apikeys' } })
  }
})
</script>
