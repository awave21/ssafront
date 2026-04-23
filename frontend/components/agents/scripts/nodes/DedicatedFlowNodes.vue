<!--
  Wave 6.2: типизированные обёртки над ExpertNode для канваса — позволяют
  развести презентацию по типам без дубля шаблонов карточек здесь.
-->
<script setup lang="ts">
import type { ScriptNodeData } from '~/types/scriptFlow'
import ExpertNode from '../ExpertNode.vue'

defineProps<{
  id: string
  data: ScriptNodeData & { content?: string }
  selected?: boolean
}>()
</script>

<template>
  <ExpertNode :id="id" :data="data" :selected="selected" />
</template>
