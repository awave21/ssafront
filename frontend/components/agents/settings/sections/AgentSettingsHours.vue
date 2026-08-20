<template>
  <div class="flex flex-col gap-5">
    <div class="flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
      <div class="flex items-center gap-2.5">
        <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Calendar class="h-4 w-4" />
        </div>
        <h1 class="text-lg font-semibold text-slate-900">Рабочее время</h1>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:border-primary/40 hover:text-primary transition-colors"
        @click="helpOpen = !helpOpen"
      >
        <BookOpen class="h-3.5 w-3.5" />
        Помощь по разделу
      </button>
    </div>

    <div
      v-if="helpOpen"
      class="rounded-2xl border border-slate-100 bg-slate-100 p-5 text-sm leading-relaxed text-slate-700"
    >
      <p class="mb-2 font-medium text-slate-900">Как работает часовой пояс</p>
      <p>
        Часовой пояс подставляется в системный промпт агента, чтобы он корректно
        интерпретировал даты и время (например, при записи на приём). Расписание
        рабочих часов (окна активности) появится в следующем релизе.
      </p>
    </div>

    <!-- Часовой пояс -->
    <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-slate-900">Часовой пояс</span>
        <span class="text-xs text-slate-500">Влияет на подстановку даты/времени в промпт</span>
      </div>
      <Popover v-model:open="tzOpen">
        <PopoverTrigger as-child>
          <button
            type="button"
            role="combobox"
            :aria-expanded="tzOpen"
            :disabled="!canEditAgents"
            class="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 transition-colors hover:border-primary/30 focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60 sm:max-w-md"
          >
            <span :class="form.timezone ? 'text-slate-900' : 'text-slate-400'">
              {{ selectedTimezoneLabel }}
            </span>
            <ChevronsUpDown class="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </button>
        </PopoverTrigger>
        <PopoverContent class="w-[--reka-popper-anchor-width] p-0" align="start">
          <Command v-model="form.timezone" @update:model-value="tzOpen = false">
            <CommandInput placeholder="Поиск часового пояса..." />
            <CommandEmpty>Часовой пояс не найден</CommandEmpty>
            <CommandList>
              <CommandGroup>
                <CommandItem
                  v-for="tz in timezoneOptions"
                  :key="tz.value"
                  :value="tz.value"
                >
                  <Check
                    class="mr-2 h-4 w-4"
                    :class="form.timezone === tz.value ? 'opacity-100' : 'opacity-0'"
                  />
                  {{ tz.label }}
                </CommandItem>
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>

    <!-- Расписание — заглушка -->
    <div class="rounded-2xl border border-dashed border-slate-200 bg-slate-100 p-6">
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-slate-700">Расписание работы</span>
        <span class="rounded-full bg-slate-200/70 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-500">Скоро</span>
      </div>
      <p class="mt-2 text-xs leading-relaxed text-slate-500">
        Указание окон, когда агент активно отвечает (например, с 9:00 до 22:00). Вне
        окна — авто-ответ «мы отвечаем с 9:00 до 22:00». Ждёт колонку
        <code class="rounded bg-white px-1 py-0.5 text-[11px]">working_hours: JSONB</code> и учёт в pipeline входящих.
      </p>
    </div>

    <div class="flex items-center justify-end text-xs text-slate-500">
      <span v-if="store.isAutoSaving" class="inline-flex items-center gap-1.5">
        <Loader2 class="h-3 w-3 animate-spin" />
        Сохранение…
      </span>
      <span v-else-if="store.lastAutoSavedAt" class="inline-flex items-center gap-1.5 text-emerald-600">
        <Check class="h-3 w-3" />
        Сохранено
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { Calendar, BookOpen, Check, ChevronsUpDown, Loader2 } from 'lucide-vue-next'
import { Popover, PopoverContent, PopoverTrigger } from '~/components/ui/popover'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '~/components/ui/command'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { usePermissions } from '~/composables/usePermissions'

const store = useAgentEditorStore()
const { form } = storeToRefs(store)
const { canEditAgents } = usePermissions()
const tzOpen = ref(false)
const helpOpen = ref(false)

const timezoneOptions = [
  { value: 'Europe/Moscow', label: 'Москва (UTC+3)' },
  { value: 'Europe/Kaliningrad', label: 'Калининград (UTC+2)' },
  { value: 'Asia/Yekaterinburg', label: 'Екатеринбург (UTC+5)' },
  { value: 'Asia/Omsk', label: 'Омск (UTC+6)' },
  { value: 'Asia/Novosibirsk', label: 'Новосибирск (UTC+7)' },
  { value: 'Asia/Krasnoyarsk', label: 'Красноярск (UTC+7)' },
  { value: 'Asia/Irkutsk', label: 'Иркутск (UTC+8)' },
  { value: 'Asia/Yakutsk', label: 'Якутск (UTC+9)' },
  { value: 'Asia/Vladivostok', label: 'Владивосток (UTC+10)' },
  { value: 'Asia/Magadan', label: 'Магадан (UTC+11)' },
  { value: 'Asia/Kamchatka', label: 'Камчатка (UTC+12)' },
  { value: 'UTC', label: 'UTC' },
  { value: 'Europe/London', label: 'Лондон (UTC+0)' },
  { value: 'Europe/Berlin', label: 'Берлин (UTC+1)' },
  { value: 'Europe/Istanbul', label: 'Стамбул (UTC+3)' },
  { value: 'Asia/Dubai', label: 'Дубай (UTC+4)' },
  { value: 'Asia/Almaty', label: 'Алматы (UTC+6)' },
  { value: 'Asia/Bangkok', label: 'Бангкок (UTC+7)' },
  { value: 'Asia/Shanghai', label: 'Шанхай (UTC+8)' },
  { value: 'Asia/Tokyo', label: 'Токио (UTC+9)' },
  { value: 'America/New_York', label: 'Нью-Йорк (UTC-5)' },
  { value: 'America/Los_Angeles', label: 'Лос-Анджелес (UTC-8)' },
]

const selectedTimezoneLabel = computed(
  () => timezoneOptions.find((tz) => tz.value === form.value.timezone)?.label ?? 'Выберите часовой пояс',
)
</script>
