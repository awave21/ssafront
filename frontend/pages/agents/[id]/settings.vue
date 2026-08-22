<template>
  <AgentPageShell title="Настройки" :hide-actions="true">
    <AgentSettingsWorkspace />
  </AgentPageShell>
</template>

<script setup lang="ts">
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentSettingsWorkspace from '~/components/agents/settings/AgentSettingsWorkspace.vue'


definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})
</script>
