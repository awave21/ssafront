<template>
  <span
    v-if="count > 0"
    class="shrink-0 inline-flex items-center gap-0.5 rounded-full bg-indigo-50 px-1.5 py-0.5 text-[9px] font-semibold text-indigo-700 border border-indigo-200"
    :title="`${count} связей с библиотекой`"
  >
    <span class="leading-none">🔗</span>
    {{ count }}
  </span>
  <span
    v-else-if="needs"
    class="shrink-0 inline-flex items-center rounded-full bg-amber-50 px-1.5 py-0.5 text-[9px] font-semibold text-amber-700 border border-amber-200"
    title="Добавьте связи с библиотекой"
  >
    без связей
  </span>
</template>

<script setup lang="ts">
defineProps<{
  count: number
  needs: boolean
}>()
</script>
