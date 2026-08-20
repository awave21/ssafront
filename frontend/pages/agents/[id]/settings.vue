<template>
  <AgentPageShell title="Настройки" :hide-actions="true">
    <AgentSettingsWorkspace v-if="newInterface" />
    <AgentSettingsPanel v-else />
  </AgentPageShell>
</template>

<script setup lang="ts">
import { useLayoutState } from '~/composables/useLayoutState'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentSettingsPanel from '~/components/agents/AgentSettingsPanel.vue'
import AgentSettingsWorkspace from '~/components/agents/settings/AgentSettingsWorkspace.vue'

const { newInterface } = useLayoutState()

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})
</script>
