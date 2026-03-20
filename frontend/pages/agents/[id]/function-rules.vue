<template>
  <AgentPageShell title="Сценарии" :hide-actions="true">
    <AgentFunctionRulesPanel :agent-id="route.params.id as string" />
  </AgentPageShell>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentFunctionRulesPanel from '~/components/agents/AgentFunctionRulesPanel.vue'

const route = useRoute()

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})
</script>
