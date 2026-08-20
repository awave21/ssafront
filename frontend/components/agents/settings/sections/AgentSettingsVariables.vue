<template>
  <div class="flex flex-col gap-5">
    <div class="flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
      <div class="flex items-center gap-2.5">
        <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Braces class="h-4 w-4" />
        </div>
        <h1 class="text-lg font-semibold text-slate-900">Пользовательские переменные</h1>
      </div>
    </div>

    <div class="rounded-2xl border border-dashed border-slate-200 bg-slate-100 p-8 text-center">
      <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-slate-400 shadow-[0_2px_8px_-4px_rgba(0,0,0,0.06)]">
        <Braces class="h-5 w-5" />
      </div>
      <div class="mb-1 text-sm font-semibold text-slate-700">Пользовательские переменные — в следующем релизе</div>
      <p class="mx-auto max-w-md text-xs leading-relaxed text-slate-500">
        Хранить произвольные значения (название клиники, часы работы, ссылки) и подставлять
        их в системный промпт через <code v-pre class="rounded bg-white px-1 py-0.5 text-[11px]">{{ variable_name }}</code> — чтобы менять данные без правки промпта.
        Ждёт колонку <code class="rounded bg-white px-1 py-0.5 text-[11px]">custom_variables: JSONB</code> и подстановку в оркестраторе.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Braces } from 'lucide-vue-next'
</script>
