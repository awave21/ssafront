<template>
  <div
    class="flex min-h-[320px] min-w-0 w-full max-w-full flex-col overflow-hidden rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
  >
    <div class="flex flex-wrap gap-1 border-b border-slate-100 bg-slate-50/80 px-2 pt-2 sm:gap-6 sm:px-6">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        class="relative px-3 py-3 text-xs font-bold transition-colors sm:px-0 sm:py-4 sm:text-sm"
        :class="
          modelValue === tab.id
            ? 'text-slate-900 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:rounded-full after:bg-primary sm:after:left-0 sm:after:right-0'
            : 'text-slate-400 hover:text-slate-600'
        "
        @click="emit('update:modelValue', tab.id)"
      >
        {{ tab.label }}
        <span
          v-if="tab.badge != null"
          class="ml-1.5 rounded-full bg-slate-200/80 px-1.5 py-0.5 text-[10px] font-bold text-slate-600"
        >
          {{ tab.badge }}
        </span>
      </button>
    </div>

    <div v-if="modelValue === 'visits'" class="flex flex-1 flex-col">
      <div
        class="hidden border-b border-slate-100 bg-slate-50/50 px-6 py-3 text-[10px] font-black uppercase tracking-widest text-slate-400 sm:flex sm:items-center sm:gap-4"
      >
        <div class="w-[130px] shrink-0">Дата и время</div>
        <div class="min-w-0 flex-1">Услуга и врач</div>
        <div class="w-[120px] shrink-0 text-right">Стоимость</div>
        <div class="w-[110px] shrink-0 text-right">Статус</div>
      </div>

      <div v-if="visitsPending" class="space-y-2 p-4">
        <Skeleton v-for="n in 5" :key="n" class="h-16 w-full rounded-2xl" />
      </div>
      <div
        v-else-if="!sortedVisits.length"
        class="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-16 text-center"
      >
        <div class="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400">
          <CalendarRange class="h-6 w-6" />
        </div>
        <p class="text-sm font-medium text-slate-400">
          Нет визитов для этого пациента. Синхронизируйте данные интеграции.
        </p>
      </div>
      <div v-else class="flex flex-1 flex-col">
        <div class="max-h-[400px] overflow-y-auto">
          <PatientVisitRow v-for="v in visibleVisits" :key="v.id" :visit="v" />
        </div>

        <div
          v-if="sortedVisits.length > previewLimit"
          class="shrink-0 border-t border-slate-50 py-3 text-center"
        >
          <Button
            variant="ghost"
            type="button"
            class="rounded-xl text-xs font-bold text-slate-500 hover:bg-slate-50 hover:text-slate-900"
            @click="emit('update:expandVisits', !expandVisits)"
          >
            {{
              expandVisits
                ? 'Свернуть'
                : `Показать все визиты (ещё ${sortedVisits.length - previewLimit})`
            }}
            <ChevronDown
              class="ml-1 h-4 w-4 transition-transform"
              :class="expandVisits ? 'rotate-180' : ''"
            />
          </Button>
        </div>
      </div>
    </div>

    <div
      v-else
      class="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-20 text-center"
    >
      <div class="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400">
        <MessageSquare class="h-6 w-6" />
      </div>
      <p class="max-w-sm text-sm font-medium text-slate-400">
        Раздел «{{ tabs.find((t) => t.id === modelValue)?.label }}» появится в следующей версии.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CalendarRange, ChevronDown, MessageSquare } from 'lucide-vue-next'
import PatientVisitRow from '~/components/patients/PatientVisitRow.vue'
import Button from '~/components/ui/button/Button.vue'
import Skeleton from '~/components/ui/skeleton/Skeleton.vue'
import type { SqnsClientCachedVisitItem } from '~/types/patient-directory'
import type { PatientDetailTabId, PatientDetailTabVm } from '~/utils/patientDetailFormat'

const props = defineProps<{
  modelValue: PatientDetailTabId
  tabs: PatientDetailTabVm[]
  visitsPending: boolean
  sortedVisits: SqnsClientCachedVisitItem[]
  expandVisits: boolean
  previewLimit: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: PatientDetailTabId]
  'update:expandVisits': [value: boolean]
}>()

const visibleVisits = computed(() => {
  if (props.expandVisits) return props.sortedVisits
  return props.sortedVisits.slice(0, props.previewLimit)
})
</script>
