<template>
  <div
    class="rounded-2xl border border-dashed border-slate-200 bg-white p-12 text-center shadow-sm"
  >
    <p class="text-sm font-medium text-slate-400">Пациент не найден для выбранного агента.</p>
    <Button class="mt-4 rounded-xl font-bold" variant="outline" type="button" @click="emit('back')">
      К списку
    </Button>
  </div>
</template>

<script setup lang="ts">
import Button from '~/components/ui/button/Button.vue'

const emit = defineEmits<{
  back: []
}>()
</script>
