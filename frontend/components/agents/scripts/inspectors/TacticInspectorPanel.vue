<template>
  <TriggerNodePanel v-if="localNodeType === 'trigger'" />
  <ExpertiseNodePanel v-else-if="localNodeType === 'expertise'" />
  <GotoNodePanel v-else-if="localNodeType === 'goto'" />
  <EndNodePanel v-else-if="localNodeType === 'end'" />
  <ExpertiseNodePanel v-else />
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { SCRIPT_FLOW_INSPECTOR_KEY } from '~/composables/useScriptFlowInspectorModel'
import TriggerNodePanel from './TriggerNodePanel.vue'
import ExpertiseNodePanel from './ExpertiseNodePanel.vue'
import GotoNodePanel from './GotoNodePanel.vue'
import EndNodePanel from './EndNodePanel.vue'

const { localNodeType } = inject(SCRIPT_FLOW_INSPECTOR_KEY)!
</script>
