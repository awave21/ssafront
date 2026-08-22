<template>
  <div class="flex flex-col gap-6 lg:flex-row lg:items-start">
    <div v-if="agentId" class="lg:sticky lg:top-4">
      <AgentFunctionsSubNav :agent-id="agentId" />
    </div>

    <div class="min-w-0 flex-1">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AgentFunctionsSubNav from './AgentFunctionsSubNav.vue'
import { useLayoutState } from '~/composables/useLayoutState'

const route = useRoute()
const agentId = computed(() => {
  const id = route.params.id
  return Array.isArray(id) ? id[0] : id
})
</script>
