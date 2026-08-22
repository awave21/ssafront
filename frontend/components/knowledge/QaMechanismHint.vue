<template>
  <div
    class="group relative mb-4 overflow-hidden rounded-3xl border border-slate-100 bg-white p-4 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
  >
    <div
      class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-primary/5 transition-transform duration-700 group-hover:scale-150"
    />
    <div class="relative flex items-start gap-3">
      <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/5">
        <Lightbulb class="h-4 w-4 text-primary" />
      </div>
      <div class="min-w-0 flex-1">
        <p class="text-sm font-semibold text-foreground">
          Прямые вопросы или справочники — что выбрать
        </p>
        <p class="mt-1 text-xs leading-relaxed text-muted-foreground">
          Оба механизма отвечают на частые вопросы. Разница — в объёме и в том,
          что должно происходить после ответа.
        </p>

        <div class="mt-3 grid gap-2 sm:grid-cols-2">
          <div
            class="rounded-2xl px-3 py-2.5"
            :class="current === 'direct_questions' ? 'bg-sky-50/60 ring-1 ring-sky-100' : 'bg-slate-50/60'"
          >
            <p class="text-[9px] font-black uppercase tracking-wider text-sky-700">
              Прямые вопросы · когда их немного
            </p>
            <p class="mt-1 text-xs text-slate-600">
              До нескольких десятков. Умеют маленькие сценарии: напомнить,
              если клиент замолчал, поставить диалог на паузу, позвать администратора.
            </p>
          </div>

          <div
            class="rounded-2xl px-3 py-2.5"
            :class="current === 'directories' ? 'bg-violet-50/60 ring-1 ring-violet-100' : 'bg-slate-50/60'"
          >
            <p class="text-[9px] font-black uppercase tracking-wider text-violet-700">
              Справочники · когда их много
            </p>
            <p class="mt-1 text-xs text-slate-600">
              Сотни записей по разным темам. Разбиваются на отдельные справочники,
              и агент ищет внутри нужной темы, а не по всему списку сразу.
            </p>
          </div>
        </div>

        <p class="mt-2.5 text-xs text-slate-400">
          Один и тот же вопрос заводить в обоих местах не нужно — агент найдёт дубль
          дважды и может ответить по устаревшей записи.
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Lightbulb } from 'lucide-vue-next'

type Props = {
  /** Какой раздел открыт — он подсвечивается в подсказке */
  current: 'direct_questions' | 'directories'
}

defineProps<Props>()
</script>
