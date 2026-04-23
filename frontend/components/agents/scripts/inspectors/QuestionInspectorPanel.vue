<template>
  <QuestionNodePanel v-if="localNodeType === 'question'" />
  <ConditionNodePanel v-else />
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { SCRIPT_FLOW_INSPECTOR_KEY } from '~/composables/useScriptFlowInspectorModel'
import QuestionNodePanel from './QuestionNodePanel.vue'
import ConditionNodePanel from './ConditionNodePanel.vue'

const { localNodeType } = inject(SCRIPT_FLOW_INSPECTOR_KEY)!
</script>
