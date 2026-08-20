<template>
  <AgentPageShell title="Каналы и интеграции" :hide-actions="true">
    <AgentChannelsWorkspace v-if="newInterface" default-section="channels" />
    <AgentChannelsPanel v-else />
  </AgentPageShell>
</template>

<script setup lang="ts">
import { useLayoutState } from '~/composables/useLayoutState'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentChannelsPanel from '~/components/agents/AgentChannelsPanel.vue'
import AgentChannelsWorkspace from '~/components/agents/channels-workspace/AgentChannelsWorkspace.vue'

const { newInterface } = useLayoutState()

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})
</script>
