<template>
  <div class="bg-background rounded-md border border-border p-4 sm:p-5 space-y-6">
    <!-- Auto-save indicator -->
    <div class="flex items-center justify-end mb-4">
      <span v-if="store.isAutoSaving" class="flex items-center gap-1.5 text-xs text-blue-600">
        <Loader2 class="h-3 w-3 animate-spin" />
        Сохранение...
      </span>
      <span v-else-if="store.lastAutoSavedAt" class="flex items-center gap-1.5 text-xs text-green-600">
        <Check class="h-3 w-3" />
        Сохранено
      </span>
    </div>
    
    <div class="max-w-2xl space-y-8">
      <div>
        <label class="block text-sm font-bold text-slate-900 mb-3">Название агента</label>
        <input
          v-model="form.name"
          :disabled="!canEditAgents"
          type="text"
          class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-md focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          placeholder="Введите название..."
        />
      </div>

      <div>
        <label class="block text-sm font-bold text-slate-900 mb-3">Часовой пояс</label>
        <Popover v-model:open="tzOpen">
          <PopoverTrigger as-child>
            <button
              type="button"
              role="combobox"
              :aria-expanded="tzOpen"
              :disabled="!canEditAgents"
              class="w-full flex items-center justify-between px-4 py-3 bg-slate-50 border border-slate-200 rounded-md text-sm transition-all hover:bg-white disabled:opacity-60 disabled:cursor-not-allowed"
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
        <p class="mt-1.5 text-xs text-slate-400">Часовой пояс используется агентом при работе с датами и временем</p>
      </div>

      <div>
        <label class="block text-sm font-bold text-slate-900 mb-3">Статус агента</label>
        <div class="flex gap-4">
          <button
            type="button"
            :disabled="!canEditAgents"
            @click="form.status = 'draft'"
            class="flex-1 flex flex-col p-4 border-2 rounded-lg transition-all text-left disabled:opacity-60 disabled:cursor-not-allowed"
            :class="[
              form.status === 'draft'
                ? 'border-indigo-600 bg-indigo-50/50 ring-4 ring-indigo-50'
                : 'border-slate-100 hover:border-slate-200 bg-white'
            ]"
          >
            <span class="font-bold text-slate-900">Черновик</span>
            <span class="text-xs text-slate-500 mt-1">Агент доступен только вам для тестирования</span>
          </button>
          <button
            type="button"
            :disabled="!canEditAgents"
            @click="form.status = 'published'"
            class="flex-1 flex flex-col p-4 border-2 rounded-lg transition-all text-left disabled:opacity-60 disabled:cursor-not-allowed"
            :class="[
              form.status === 'published'
                ? 'border-emerald-500 bg-emerald-50/50 ring-4 ring-emerald-50'
                : 'border-slate-100 hover:border-slate-200 bg-white'
            ]"
          >
            <span class="font-bold text-slate-900">Опубликован</span>
            <span class="text-xs text-slate-500 mt-1">Агент доступен всем сотрудникам клиники</span>
          </button>
        </div>
      </div>

      <div>
        <label class="block text-sm font-bold text-slate-900 mb-3">Автопауза после ответа оператора</label>
        <div class="flex items-center gap-3">
          <input
            v-model.number="form.manager_pause_minutes"
            :disabled="!canEditAgents"
            type="number"
            min="1"
            max="1440"
            step="1"
            class="w-40 px-4 py-3 bg-slate-50 border border-slate-200 rounded-md focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          />
          <span class="text-sm text-slate-500">минут</span>
        </div>
        <p class="mt-1.5 text-xs text-slate-400">
          После сообщения оператора бот временно не отвечает в этом диалоге и автоматически возобновляет ответы по таймеру.
        </p>
      </div>

      <div class="rounded-md border border-slate-200 bg-slate-50/60 p-4">
        <div class="flex items-start justify-between gap-4">
          <div class="space-y-1">
            <label class="block text-sm font-bold text-slate-900">Отключить агента</label>
            <p class="text-xs text-slate-500">
              При отключении агент временно не инициирует новые ответы. Входящие сообщения продолжают поступать.
            </p>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <span
              class="inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium"
              :class="form.is_disabled ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'"
            >
              {{ form.is_disabled ? 'Выключен' : 'Включен' }}
            </span>
            <Switch
              :model-value="!form.is_disabled"
              :disabled="!canEditAgents"
              @update:model-value="(enabled: boolean) => { form.is_disabled = !enabled }"
            />
          </div>
        </div>
      </div>

      <div v-if="canEditAgents" class="pt-8 border-t border-red-50">
        <h4 class="text-sm font-bold text-red-600 mb-2">Опасная зона</h4>
        <p class="text-xs text-slate-500 mb-4">Удаление агента приведет к безвозвратной потере всех его настроек и истории.</p>
        <button
          type="button"
          @click="handleDelete"
          class="px-6 py-2.5 bg-white border border-red-200 text-red-600 rounded-md text-sm font-bold hover:bg-red-50 transition-colors"
        >
          Удалить агента
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { navigateTo } from '#app'
import { Check, ChevronsUpDown, Loader2 } from 'lucide-vue-next'
import { Popover, PopoverContent, PopoverTrigger } from '~/components/ui/popover'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '~/components/ui/command'
import { Switch } from '~/components/ui/switch'
import { usePermissions } from '~/composables/usePermissions'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'

const store = useAgentEditorStore()
const { form } = storeToRefs(store)
const { canEditAgents } = usePermissions()

const tzOpen = ref(false)
const selectedTimezoneLabel = computed(() =>
  timezoneOptions.find(tz => tz.value === form.value.timezone)?.label ?? 'Выберите часовой пояс'
)

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

const handleDelete = async () => {
  if (!confirm('Вы уверены, что хотите удалить этого агента? Это действие нельзя отменить.')) return
  const success = await store.removeAgent()
  if (success) {
    navigateTo('/agents')
  }
}
</script>
