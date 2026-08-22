<template>
  <AgentPageShell title="Функции" :hide-actions="true">
    <AgentFunctionsWorkspace>
      <div class="flex flex-col gap-5">
        <div class="flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div class="flex items-center gap-2.5">
            <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Zap class="h-4 w-4" />
            </div>
            <h1 class="text-lg font-semibold text-slate-900">Каталог функций</h1>
          </div>
        </div>

        <div>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-primary/40 hover:text-primary"
            @click="navigateBack"
          >
            <ChevronLeft class="h-3.5 w-3.5" />
            Назад к функциям
          </button>
        </div>

        <p class="text-sm text-slate-500">
          Нажмите на функцию, чтобы добавить её в список и настроить.
        </p>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <button
            v-for="preset in functionPresets"
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
    </AgentFunctionsWorkspace>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronLeft, Zap } from 'lucide-vue-next'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentFunctionsWorkspace from '~/components/agents/functions-workspace/AgentFunctionsWorkspace.vue'
import { functionPresets } from '~/utils/functionPresets'

const route = useRoute()
const router = useRouter()
const agentId = computed(() => (route.params.id as string) || '')

const navigateBack = () => {
  router.push(`/agents/${agentId.value}/functions`)
}

// Заготовку передаём через query, а не через store: так ссылка на конкретный
// шаблон остаётся рабочей и переживает перезагрузку страницы.
const applyPreset = (presetId: string) => {
  router.push(`/agents/${agentId.value}/functions/new?preset=${presetId}`)
}

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})
</script>
