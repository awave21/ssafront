<template>
  <AgentPageShell title="Чат" :hide-actions="true">
    <AgentChatPanel />
  </AgentPageShell>
</template>

<script setup lang="ts">
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentChatPanel from '~/components/agents/AgentChatPanel.vue'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})
</script>
