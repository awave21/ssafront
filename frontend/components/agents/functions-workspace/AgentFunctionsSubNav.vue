<template>
  <nav class="w-full lg:w-64 shrink-0" aria-label="Разделы функций">
    <ul class="flex flex-col gap-1.5">
      <li v-for="item in items" :key="item.id">
        <NuxtLink
          :to="item.path"
          class="group flex items-start gap-3 rounded-2xl border border-transparent px-3 py-2.5 transition-all duration-200"
          :class="[
            isActive(item)
              ? 'border-primary/20 bg-primary/10 text-primary shadow-[0_2px_8px_-4px_rgba(59,130,246,0.15)]'
              : 'text-slate-600 hover:border-slate-100 hover:bg-slate-50 hover:text-primary'
          ]"
          :aria-current="isActive(item) ? 'page' : undefined"
        >
          <div
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-colors"
            :class="[
              isActive(item)
                ? 'bg-white text-primary shadow-[0_1px_3px_-1px_rgba(0,0,0,0.08)]'
                : 'bg-slate-100 text-slate-500 group-hover:bg-white group-hover:text-primary'
            ]"
          >
            <component :is="item.icon" class="h-4 w-4" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-sm font-semibold leading-tight">{{ item.label }}</div>
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
import { Zap, Webhook } from 'lucide-vue-next'

type SubNavItem = {
  id: string
  label: string
  hint: string
  icon: unknown
  path: string
  /** префиксы роутов, при попадании в которые пункт считается активным */
  match: string[]
}

const props = defineProps<{
  agentId: string
}>()

const route = useRoute()

const items = computed<SubNavItem[]>(() => {
  const id = props.agentId
  return [
    {
      id: 'functions',
      label: 'Функции',
      hint: 'Правила и логика поведения',
      icon: Zap,
      path: `/agents/${id}/functions`,
      match: [`/agents/${id}/functions`, `/agents/${id}/function-rules`],
    },
    {
      id: 'webhook',
      label: 'Webhook',
      hint: 'Внешние функции по HTTP',
      icon: Webhook,
      path: `/agents/${id}/webhook`,
      match: [`/agents/${id}/webhook`],
    },
  ]
})

const isActive = (item: SubNavItem) => {
  const current = (route.path || '').replace(/\/+$/, '')
  return item.match.some(prefix => {
    const norm = prefix.replace(/\/+$/, '')
    return current === norm || current.startsWith(`${norm}/`)
  })
}
</script>
