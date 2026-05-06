<template>
  <Sheet :open="open" @update:open="(v) => !v && $emit('close')">
    <SheetContent side="right" class="w-full max-w-md overflow-y-auto">
      <SheetHeader class="pb-4">
        <SheetTitle class="text-base font-bold">Правила мотивации врачей</SheetTitle>
      </SheetHeader>

      <div class="space-y-6">
        <!-- Первичка -->
        <div class="rounded-2xl bg-slate-50 p-4 space-y-3">
          <div class="text-[10px] font-black uppercase tracking-wider text-slate-500">Первичные визиты</div>
          <div class="flex items-center gap-3">
            <label class="w-40 text-xs text-slate-600">% от выручки</label>
            <input
              v-model.number="form.primary_pct"
              type="number" min="0" max="100" step="0.5"
              class="w-20 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-bold tabular-nums focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <span class="text-sm text-slate-400">%</span>
          </div>
        </div>

        <!-- Пороги среднего чека -->
        <div class="rounded-2xl bg-slate-50 p-4 space-y-3">
          <div class="text-[10px] font-black uppercase tracking-wider text-slate-500">Диапазон нормы среднего чека первичных</div>
          <div class="flex items-center gap-3">
            <label class="w-40 text-xs text-slate-600">Нижняя граница (₽)</label>
            <input
              v-model.number="form.avg_check_low"
              type="number" min="0" step="1000"
              class="w-28 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-bold tabular-nums focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div class="flex items-center gap-3">
            <label class="w-40 text-xs text-slate-600">Верхняя граница (₽)</label>
            <input
              v-model.number="form.avg_check_high"
              type="number" min="0" step="1000"
              class="w-28 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-bold tabular-nums focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
        </div>

        <!-- Вторичка — три уровня -->
        <div class="rounded-2xl bg-slate-50 p-4 space-y-3">
          <div class="text-[10px] font-black uppercase tracking-wider text-slate-500">Вторичные визиты — % по уровням</div>

          <div class="flex items-center gap-3">
            <span class="flex w-40 items-center gap-1.5 text-xs">
              <span class="inline-block h-2 w-2 rounded-full bg-rose-400"></span>
              Ниже нормы
            </span>
            <input
              v-model.number="form.repeat_pct_low"
              type="number" min="0" max="100" step="0.5"
              class="w-20 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-bold tabular-nums focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <span class="text-sm text-slate-400">%</span>
          </div>

          <div class="flex items-center gap-3">
            <span class="flex w-40 items-center gap-1.5 text-xs">
              <span class="inline-block h-2 w-2 rounded-full bg-slate-400"></span>
              Норма
            </span>
            <input
              v-model.number="form.repeat_pct_norm"
              type="number" min="0" max="100" step="0.5"
              class="w-20 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-bold tabular-nums focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <span class="text-sm text-slate-400">%</span>
          </div>

          <div class="flex items-center gap-3">
            <span class="flex w-40 items-center gap-1.5 text-xs">
              <span class="inline-block h-2 w-2 rounded-full bg-emerald-400"></span>
              Выше нормы (бонус)
            </span>
            <input
              v-model.number="form.repeat_pct_high"
              type="number" min="0" max="100" step="0.5"
              class="w-20 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-bold tabular-nums focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <span class="text-sm text-slate-400">%</span>
          </div>
        </div>

        <!-- Действия -->
        <div class="flex gap-3 pt-2">
          <button
            :disabled="saving"
            class="flex-1 rounded-2xl bg-primary py-2.5 text-sm font-bold text-white transition hover:opacity-90 disabled:opacity-50"
            @click="save"
          >
            {{ saving ? 'Сохранение…' : 'Сохранить' }}
          </button>
          <button
            class="rounded-2xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-600 transition hover:bg-slate-50"
            @click="$emit('close')"
          >
            Отмена
          </button>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '~/components/ui/sheet'
import type { MotivationRule } from '~/types/analytics'

const props = defineProps<{
  open: boolean
  rule: MotivationRule
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved', rule: MotivationRule): void
}>()

const form = reactive({ ...props.rule })
const saving = ref(false)

watch(
  () => props.rule,
  (r) => Object.assign(form, r),
  { deep: true },
)

async function save() {
  saving.value = true
  try {
    emit('saved', { ...form })
  } finally {
    saving.value = false
  }
}
</script>
