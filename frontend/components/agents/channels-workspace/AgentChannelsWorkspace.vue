<template>
  <div class="flex flex-col gap-6 lg:flex-row lg:items-start">
    <div class="lg:sticky lg:top-4">
      <AgentChannelsSubNav :active-section="activeSection" />
    </div>

    <div class="min-w-0 flex-1">
      <AgentChannelsPanel v-if="activeSection === 'channels'" />
      <AgentConnectionsPanel v-else-if="activeSection === 'integrations'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AgentChannelsSubNav from './AgentChannelsSubNav.vue'
import AgentChannelsPanel from '~/components/agents/AgentChannelsPanel.vue'
import AgentConnectionsPanel from '~/components/agents/AgentConnectionsPanel.vue'

const SECTIONS = ['channels', 'integrations'] as const
type Section = typeof SECTIONS[number]

const props = defineProps<{
  defaultSection?: Section
}>()

const route = useRoute()

const activeSection = computed<Section>(() => {
  const raw = String(route.query.section || props.defaultSection || 'channels')
  return (SECTIONS as readonly string[]).includes(raw) ? (raw as Section) : 'channels'
})
</script>
