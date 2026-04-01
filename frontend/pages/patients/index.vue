<template>
  <div class="min-h-screen w-full bg-[#f8fafc]">
    <div
      class="flex w-full max-w-none flex-col gap-4 px-3 py-6 sm:gap-6 sm:px-4 sm:py-8 lg:gap-6 lg:px-3 lg:py-10"
    >
      <div
        v-if="agentsLoadPending"
        class="flex items-center gap-2 rounded-2xl border border-slate-100 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm"
      >
        <Loader2 class="h-4 w-4 shrink-0 animate-spin text-primary" aria-hidden="true" />
        Загрузка списка агентов…
      </div>

      <template v-else-if="!agents.length">
        <div
          class="rounded-2xl border border-amber-100 bg-amber-50/80 px-4 py-3 text-sm text-amber-900"
          role="status"
        >
          Нет доступных агентов. Создайте агента в разделе «Агенты», затем вернитесь к списку пациентов.
        </div>
      </template>

      <template v-else>
        <div
          class="w-full max-w-md rounded-3xl border border-slate-100 bg-white p-4 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
        >
          <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">
            Агент
          </label>
          <Select :model-value="selectedAgentId ?? undefined" @update:model-value="onAgentChange">
            <SelectTrigger
              class="h-11 w-full rounded-xl border-slate-100 bg-slate-50/50 focus:ring-2 focus:ring-primary/20"
            >
              <SelectValue placeholder="Выберите агента" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="agent in agents" :key="agent.id" :value="agent.id">
                {{ agent.name }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <AgentPatientsPanel v-if="selectedAgentId" :agent-id="selectedAgentId" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import AgentPatientsPanel from '~/components/agents/AgentPatientsPanel.vue'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '~/components/ui/select'
import { useAgents } from '~/composables/useAgents'
import { useLayoutState } from '~/composables/useLayoutState'
import { routerReplaceSafe } from '~/utils/routerSafe'

definePageMeta({
  middleware: 'auth',
})

const route = useRoute()
const router = useRouter()
const { pageTitle } = useLayoutState()
const { agents, fetchAgents } = useAgents()

const agentsLoadPending = ref(true)

const queryAgentId = computed(() => {
  const q = route.query.agent
  if (typeof q === 'string' && q.length > 0) return q
  if (Array.isArray(q) && typeof q[0] === 'string' && q[0].length > 0) return q[0]
  return null
})

const selectedAgentId = computed(() => {
  if (!agents.value.length) return null
  const q = queryAgentId.value
  if (q && agents.value.some((a) => a.id === q)) return q
  return agents.value[0]?.id ?? null
})

const drillQueryParams = computed(() => {
  const out: Record<string, string> = {}
  const vf = route.query.vf
  const vt = route.query.vt
  const vc = route.query.vc
  const tz = route.query.tz
  const channel = route.query.channel
  const tags = route.query.tags
  const rb = route.query.revenue_basis
  const resource = route.query.resource
  if (typeof vf === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(vf)) out.vf = vf
  if (typeof vt === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(vt)) out.vt = vt
  if (typeof vc === 'string' && vc.trim()) out.vc = vc.trim()
  if (typeof tz === 'string' && tz.trim()) out.tz = tz.trim()
  if (typeof channel === 'string' && channel.trim()) out.channel = channel.trim()
  if (typeof tags === 'string' && tags.trim()) out.tags = tags
  if (typeof resource === 'string' && /^\d+$/.test(resource.trim())) out.resource = resource.trim()
  const rb0 = Array.isArray(rb) ? rb[0] : rb
  if (rb0 === 'all') out.revenue_basis = 'all'
  return out
})

const syncQueryToDefaultAgent = () => {
  if (!import.meta.client) return
  if (!agents.value.length) return
  const q = queryAgentId.value
  const valid = q && agents.value.some((a) => a.id === q)
  if (valid) return
  const first = agents.value[0].id
  void routerReplaceSafe(router, { path: '/patients', query: { agent: first, ...drillQueryParams.value } })
}

onMounted(async () => {
  pageTitle.value = 'Пациенты'
  try {
    await fetchAgents({ limit: 200 })
  } catch {
    // Ошибка уже в useAgents.error; не даём необработанному reject ломать навигацию
  } finally {
    agentsLoadPending.value = false
  }
})

watch(
  () => [agents.value.map((a) => a.id).join(','), route.query.agent] as const,
  () => {
    syncQueryToDefaultAgent()
  },
)

const onAgentChange = (value: unknown) => {
  const id = typeof value === 'string' ? value : String(value ?? '')
  if (!id) return
  void routerReplaceSafe(router, { path: '/patients', query: { agent: id, ...drillQueryParams.value } })
}
</script>
