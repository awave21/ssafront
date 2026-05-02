<template>
  <div class="flex flex-wrap items-center gap-2">
    <!-- "Создать поток" — кнопка, видна только на странице списка потоков -->
    <button
      v-if="active === 'flows'"
      type="button"
      class="inline-flex h-10 w-[180px] shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-indigo-600 px-4 text-sm font-bold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
      :disabled="creating"
      @click="$emit('create')"
    >
      <Plus class="h-4 w-4" />
      {{ creating ? 'Создаём…' : 'Создать поток' }}
    </button>
    <NuxtLink
      v-else
      :to="`/agents/${agentId}/scripts`"
      class="inline-flex h-10 w-[180px] shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
    >
      <Workflow class="h-4 w-4" />
      Потоки
    </NuxtLink>

    <NuxtLink
      :to="`/agents/${agentId}/scripts/library`"
      class="inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl border px-4 text-sm font-semibold transition-colors"
      :class="active === 'library'
        ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
        : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'"
      title="Общая библиотека сущностей (Motive / Argument / Proof / Objection / Constraint / Outcome)"
    >
      <Library class="h-4 w-4" />
      Библиотека
    </NuxtLink>

    <NuxtLink
      :to="`/agents/${agentId}/scripts/coverage`"
      class="inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl border px-4 text-sm font-semibold transition-colors"
      :class="active === 'coverage'
        ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
        : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'"
      title="Аналитика покрытия: какие тактики применяются и каких не хватает"
    >
      <BarChart3 class="h-4 w-4" />
      Аналитика
    </NuxtLink>
  </div>
</template>

<script setup lang="ts">
import { BarChart3, Library, Plus, Workflow } from 'lucide-vue-next'

defineProps<{
  agentId: string
  active: 'flows' | 'library' | 'coverage'
  creating?: boolean
}>()

defineEmits<{
  (e: 'create'): void
}>()
</script>
