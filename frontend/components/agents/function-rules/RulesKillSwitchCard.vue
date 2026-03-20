<template>
  <div class="rounded-md border border-slate-200 bg-white p-4">
    <div class="mb-1 text-sm font-semibold text-slate-900">Kill switch правил</div>
    <p class="mb-3 text-sm text-slate-600">
      Отключает все активные сценарии для текущего агента.
    </p>
    <Button variant="destructive" :disabled="loading || !canEdit" @click="$emit('kill-switch')">
      Отключить все правила
    </Button>
  </div>
</template>

<script setup lang="ts">
import { Button } from '~/components/ui/button'

defineProps<{
  loading: boolean
  canEdit: boolean
}>()

defineEmits<{
  'kill-switch': []
}>()
</script>
