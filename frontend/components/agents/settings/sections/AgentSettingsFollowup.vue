<template>
  <div class="flex flex-col gap-5">
    <div class="flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
      <div class="flex items-center gap-2.5">
        <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Clock3 class="h-4 w-4" />
        </div>
        <h1 class="text-lg font-semibold text-slate-900">Возврат клиентов</h1>
      </div>
    </div>

    <div class="rounded-2xl border border-dashed border-slate-200 bg-slate-100 p-8 text-center">
      <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-slate-400 shadow-[0_2px_8px_-4px_rgba(0,0,0,0.06)]">
        <Clock3 class="h-5 w-5" />
      </div>
      <div class="mb-1 text-sm font-semibold text-slate-700">Follow-up после паузы — в следующем релизе</div>
      <p class="mx-auto max-w-md text-xs leading-relaxed text-slate-500">
        Автоматическое возвращение клиента в разговор, если он замолчал: гибкое расписание,
        сообщения по шаблонам, ограничение попыток. Пока follow-up доступен точечно через
        функции и сценарии.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Clock3 } from 'lucide-vue-next'
</script>
