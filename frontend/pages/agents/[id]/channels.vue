<template>
  <AgentPageShell title="Каналы" :hide-actions="true">
    <AgentChannelsPanel />
  </AgentPageShell>
</template>

<script setup lang="ts">
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentChannelsPanel from '~/components/agents/AgentChannelsPanel.vue'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})
</script>
