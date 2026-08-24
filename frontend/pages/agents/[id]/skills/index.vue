<template>
  <AgentPageShell title="Навыки эксперта" :hide-actions="true" :contained="true">
    <SkillList :agent-id="agentId" />
  </AgentPageShell>
</template>

<script setup lang="ts">
import { useRoute } from '#app'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import SkillList from '~/components/agents/skills/SkillList.vue'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})

const route = useRoute()
const agentId = route.params.id as string
</script>
