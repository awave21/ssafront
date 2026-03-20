<template>
  <AgentPageShell title="База знаний" :hide-actions="true">
    <AgentKnowledgePanel />
  </AgentPageShell>
</template>

<script setup lang="ts">
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentKnowledgePanel from '~/components/agents/AgentKnowledgePanel.vue'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})
</script>
