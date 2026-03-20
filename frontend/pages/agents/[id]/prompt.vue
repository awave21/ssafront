<template>
  <AgentPageShell title="Системный промпт" :hide-actions="true">
    <AgentPromptPanel />
  </AgentPageShell>
</template>

<script setup lang="ts">
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentPromptPanel from '~/components/agents/AgentPromptPanel.vue'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})
</script>
