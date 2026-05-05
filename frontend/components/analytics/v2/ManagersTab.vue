<template>
  <div class="space-y-8">
    <div v-if="loading && !overview" class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div v-for="i in 3" :key="i" class="h-28 animate-pulse rounded-3xl bg-white"></div>
    </div>

    <template v-else-if="overview">
      <section class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <KpiTile
          label="Менеджеров активно"
          :value="overview.managers_total"
          :icon="Users"
          accent="primary"
        />
        <KpiTile
          label="Ручных вмешательств"
          :value="overview.overrides_total"
          :icon="MessageSquare"
          accent="amber"
        />
        <KpiTile
          label="Отключений бота"
          :value="overview.bot_disable_total"
          :icon="PowerOff"
          accent="rose"
        />
      </section>

      <section v-if="overview.items.length" class="rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div class="px-6 py-4">
          <h3 class="text-sm font-bold uppercase tracking-widest text-slate-500">Активность операторов</h3>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-y border-slate-100 bg-slate-50/50 text-[10px] font-black uppercase tracking-wider text-slate-500">
                <th class="px-6 py-3 text-left">Оператор</th>
                <th class="px-3 py-3 text-right">Сообщений в чат</th>
                <th class="px-3 py-3 text-right">Отключений бота</th>
                <th class="px-3 py-3 text-right">Последняя активность</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in overview.items" :key="String(m.user_id)" class="border-b border-slate-50">
                <td class="px-6 py-3">
                  <div class="font-bold text-slate-900">{{ m.full_name }}</div>
                  <div v-if="m.email" class="text-xs text-slate-400">{{ m.email }}</div>
                </td>
                <td class="px-3 py-3 text-right tabular-nums font-bold text-slate-900">{{ m.overrides_count }}</td>
                <td class="px-3 py-3 text-right tabular-nums" :class="m.bot_disable_count > 0 ? 'text-rose-600 font-bold' : 'text-slate-500'">
                  {{ m.bot_disable_count }}
                </td>
                <td class="px-3 py-3 text-right text-xs text-slate-500">
                  {{ formatDate(m.last_active_at) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="timeline?.events?.length" class="rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <h3 class="mb-4 text-sm font-bold uppercase tracking-widest text-slate-500">История вмешательств</h3>
        <ol class="relative space-y-4 border-l border-slate-100 pl-6">
          <li v-for="(ev, idx) in timeline.events.slice(0, 30)" :key="idx" class="relative">
            <span
              class="absolute -left-[27px] mt-1 flex h-3 w-3 items-center justify-center rounded-full ring-4 ring-white"
              :class="eventColor(ev.event_type)"
            ></span>
            <div class="text-xs text-slate-400">{{ formatDate(ev.happened_at) }}</div>
            <div class="text-sm font-bold text-slate-900">
              {{ eventLabel(ev.event_type) }}
              <span v-if="ev.full_name" class="font-medium text-slate-600">— {{ ev.full_name }}</span>
            </div>
            <p v-if="ev.text_preview" class="mt-1 text-xs text-slate-500">{{ ev.text_preview }}</p>
          </li>
        </ol>
      </section>
    </template>

    <div v-else class="rounded-3xl border border-slate-100 bg-white p-10 text-center text-sm text-slate-400">
      За выбранный период менеджеры не вмешивались в диалоги.
    </div>
  </div>
</template>

<script setup lang="ts">
import { Users, MessageSquare, PowerOff } from 'lucide-vue-next'
import KpiTile from './KpiTile.vue'
import type { ManagersOverviewResponse, ManagersTimelineResponse } from '~/types/analytics'

defineProps<{
  overview: ManagersOverviewResponse | null
  timeline: ManagersTimelineResponse | null
  loading: boolean
}>()

const eventLabel = (t: string) => {
  if (t === 'manager_message') return 'Менеджер написал клиенту'
  if (t === 'bot_disabled') return 'Отключён бот'
  return 'Диалог поставлен на паузу'
}

const eventColor = (t: string) => {
  if (t === 'bot_disabled') return 'bg-rose-500'
  if (t === 'manager_message') return 'bg-amber-500'
  return 'bg-slate-300'
}

const formatDate = (s: string | null) => {
  if (!s) return '—'
  try {
    const d = new Date(s)
    return d.toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
  } catch {
    return s
  }
}
</script>
