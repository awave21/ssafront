<template>
  <AgentPageShell title="Настройки" :hide-actions="true">
    <AgentSettingsPanel />
  </AgentPageShell>
</template>

<script setup lang="ts">
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentSettingsPanel from '~/components/agents/AgentSettingsPanel.vue'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})
</script>
