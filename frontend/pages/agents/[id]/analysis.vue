<template>
  <AgentPageShell title="Анализ" :hide-actions="true">
    <div class="h-full min-h-0 overflow-hidden">
      <AgentAnalysisPanel />
    </div>
  </AgentPageShell>
</template>

<script setup lang="ts">
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentAnalysisPanel from '~/components/agents/AgentAnalysisPanel.vue'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})
</script>
