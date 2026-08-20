<template>
  <div class="flex flex-col gap-6 lg:flex-row lg:items-start">
    <div class="lg:sticky lg:top-4">
      <AgentSettingsSubNav :active-section="activeSection" />
    </div>

    <div class="min-w-0 flex-1">
      <component :is="activeComponent" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AgentSettingsSubNav from './AgentSettingsSubNav.vue'
import AgentSettingsModel from './sections/AgentSettingsModel.vue'
import AgentSettingsBehavior from './sections/AgentSettingsBehavior.vue'
import AgentSettingsBudget from './sections/AgentSettingsBudget.vue'
import AgentSettingsFollowup from './sections/AgentSettingsFollowup.vue'
import AgentSettingsHours from './sections/AgentSettingsHours.vue'
import AgentSettingsVariables from './sections/AgentSettingsVariables.vue'
import AgentSettingsApiKeys from './sections/AgentSettingsApiKeys.vue'

const SECTIONS = ['model', 'behavior', 'budget', 'followup', 'hours', 'variables', 'apikeys'] as const
type Section = typeof SECTIONS[number]

const route = useRoute()

const activeSection = computed<Section>(() => {
  const raw = String(route.query.section || 'model')
  return (SECTIONS as readonly string[]).includes(raw) ? (raw as Section) : 'model'
})

const componentBySection: Record<Section, unknown> = {
  model: AgentSettingsModel,
  behavior: AgentSettingsBehavior,
  budget: AgentSettingsBudget,
  followup: AgentSettingsFollowup,
  hours: AgentSettingsHours,
  variables: AgentSettingsVariables,
  apikeys: AgentSettingsApiKeys,
}

const activeComponent = computed(() => componentBySection[activeSection.value])
</script>
