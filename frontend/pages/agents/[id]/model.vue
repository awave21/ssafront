<template>
  <AgentPageShell title="Модель" :hide-actions="true">
    <AgentModelPanel />
  </AgentPageShell>
</template>

<script setup lang="ts">
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentModelPanel from '~/components/agents/AgentModelPanel.vue'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})
</script>
