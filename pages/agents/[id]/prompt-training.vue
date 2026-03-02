<template>
  <AgentPageShell title="Обучение промпта" :hide-actions="true">
    <AgentPromptTrainingPanel />
  </AgentPageShell>
</template>

<script setup lang="ts">
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentPromptTrainingPanel from '~/components/agents/AgentPromptTrainingPanel.vue'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})
</script>
