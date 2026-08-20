<template>
  <nav class="w-full lg:w-64 shrink-0" aria-label="Разделы настроек">
    <ul class="flex flex-col gap-1.5">
      <li v-for="item in items" :key="item.id">
        <NuxtLink
          :to="{ query: { ...currentQuery, section: item.id } }"
          replace
          class="group flex items-start gap-3 rounded-2xl border border-transparent px-3 py-2.5 transition-all duration-200"
          :class="[
            isActive(item.id)
              ? 'border-primary/20 bg-primary/10 text-primary shadow-[0_2px_8px_-4px_rgba(59,130,246,0.15)]'
              : 'text-slate-600 hover:border-slate-100 hover:bg-slate-50 hover:text-primary'
          ]"
          :aria-current="isActive(item.id) ? 'page' : undefined"
        >
          <div
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-colors"
            :class="[
              isActive(item.id)
                ? 'bg-white text-primary shadow-[0_1px_3px_-1px_rgba(0,0,0,0.08)]'
                : 'bg-slate-100 text-slate-500 group-hover:bg-white group-hover:text-primary'
            ]"
          >
            <component :is="item.icon" class="h-4 w-4" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5">
              <span class="text-sm font-semibold leading-tight">{{ item.label }}</span>
              <span
                v-if="item.soon"
                class="rounded-full bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-500"
              >Скоро</span>
            </div>
            <div class="mt-0.5 text-xs leading-tight text-slate-400">{{ item.hint }}</div>
          </div>
        </NuxtLink>
      </li>
    </ul>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Sun,
  SlidersHorizontal,
  DollarSign,
  Clock3,
  Calendar,
  Braces,
  KeyRound,
} from 'lucide-vue-next'

type SubNavItem = {
  id: string
  label: string
  hint: string
  icon: unknown
  soon?: boolean
}

const props = defineProps<{
  activeSection: string
}>()

const route = useRoute()

const items = computed<SubNavItem[]>(() => [
  { id: 'model', label: 'Параметры модели', hint: 'Модель, пресет и температура', icon: Sun },
  { id: 'behavior', label: 'Параметры поведения', hint: 'Паузы и передача оператору', icon: SlidersHorizontal },
  { id: 'budget', label: 'Бюджет', hint: 'Расход агента и баланс', icon: DollarSign },
  { id: 'followup', label: 'Возврат клиентов', hint: 'Follow-up после паузы', icon: Clock3, soon: true },
  { id: 'hours', label: 'Рабочее время', hint: 'Расписание и часовой пояс', icon: Calendar },
  { id: 'variables', label: 'Пользовательские переменные', hint: 'Данные для промпта и функций', icon: Braces, soon: true },
  { id: 'apikeys', label: 'API-ключи', hint: 'Ключи интеграций с агентом', icon: KeyRound },
])

const currentQuery = computed(() => ({ ...route.query }))

const isActive = (id: string) => props.activeSection === id
</script>
