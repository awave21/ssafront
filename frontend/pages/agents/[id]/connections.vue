<template>
  <AgentPageShell title="Каналы и интеграции" :hide-actions="true">
    <AgentChannelsWorkspace default-section="integrations" />
  </AgentPageShell>
</template>

<script setup lang="ts">
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentChannelsWorkspace from '~/components/agents/channels-workspace/AgentChannelsWorkspace.vue'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})
</script>
