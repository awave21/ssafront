<template>
  <AgentPageShell title="Сценарии" :hide-actions="true" :contained="true">
    <div class="flex min-h-0 min-w-0 w-full flex-1 flex-col gap-5">
      <div class="flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
        <div class="flex items-center gap-2.5">
          <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <GitBranch class="h-4 w-4" />
          </div>
          <h1 class="text-lg font-semibold text-slate-900">Каталог сценариев</h1>
        </div>
      </div>

      <div>
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-primary/40 hover:text-primary"
          @click="navigateBack"
        >
          <ChevronLeft class="h-3.5 w-3.5" />
          Назад к сценариям
        </button>
      </div>

      <p class="text-sm text-slate-500">
        Нажмите на сценарий, чтобы добавить его в список и настроить.
      </p>

      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <button
          v-for="preset in scenarioPresets"
          :key="preset.id"
          type="button"
          class="group flex flex-col items-start gap-2 rounded-2xl border border-slate-100 bg-white p-5 text-left shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-300 hover:-translate-y-1 hover:border-primary/30 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
          @click="applyPreset(preset.id)"
        >
          <span class="text-2xl leading-none transition-transform duration-300 group-hover:scale-110">
            {{ preset.emoji }}
          </span>
          <span class="text-sm font-semibold text-slate-900 transition-colors group-hover:text-primary">
            {{ preset.title }}
          </span>
          <span class="text-xs leading-relaxed text-slate-500">{{ preset.description }}</span>
        </button>
      </div>
    </div>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronLeft, GitBranch } from 'lucide-vue-next'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import { scenarioPresets } from '~/utils/scenarioPresets'

const route = useRoute()
const router = useRouter()
const agentId = computed(() => (route.params.id as string) || '')

const navigateBack = () => {
  router.push(`/agents/${agentId.value}/scenarios`)
}

// Сценарии создаются в панели поверх списка, а не отдельной страницей, поэтому
// возвращаемся на список с preset в query — он откроет редактор уже заполненным.
const applyPreset = (presetId: string) => {
  router.push(`/agents/${agentId.value}/scenarios?preset=${presetId}`)
}

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})
</script>
