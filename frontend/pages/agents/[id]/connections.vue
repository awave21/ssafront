<template>
  <AgentPageShell title="Интеграции" :hide-actions="true">
    <AgentConnectionsPanel />
  </AgentPageShell>
</template>

<script setup lang="ts">
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentConnectionsPanel from '~/components/agents/AgentConnectionsPanel.vue'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})
</script>
