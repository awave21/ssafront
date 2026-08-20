<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>Услуги навыка</DialogTitle>
        <DialogDescription>
          Навык применяется, когда в диалоге определена одна из привязанных услуг.
          Выберите услуги, которыми этот навык помогает вести пациента.
        </DialogDescription>
      </DialogHeader>

      <div class="relative">
        <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          v-model="query"
          type="text"
          placeholder="Поиск услуги по названию…"
          class="h-10 w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm outline-none transition-all duration-300 focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
        >
      </div>

      <div v-if="selected.length" class="flex flex-wrap gap-1.5">
        <span
          v-for="ext in selected"
          :key="`sel-${ext}`"
          class="inline-flex items-center gap-1 rounded-2xl bg-indigo-50/70 px-2.5 py-1 text-xs font-medium text-indigo-700"
        >
          {{ nameFor(ext) }}
          <button type="button" class="text-indigo-400 hover:text-indigo-700" @click="toggle(ext)">
            <X class="h-3 w-3" />
          </button>
        </span>
      </div>

      <div class="max-h-72 space-y-1 overflow-y-auto pr-1">
        <div v-if="loading" class="flex justify-center py-8">
          <Loader2 class="h-6 w-6 animate-spin text-indigo-600" />
        </div>
        <p v-else-if="!filtered.length" class="py-8 text-center text-sm text-slate-400">
          Ничего не найдено
        </p>
        <button
          v-for="svc in filtered"
          v-else
          :key="svc.external_id"
          type="button"
          class="flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left transition-colors"
          :class="isSelected(svc.external_id)
            ? 'border-indigo-200 bg-indigo-50/60'
            : 'border-transparent hover:bg-slate-50'"
          @click="toggle(String(svc.external_id))"
        >
          <span
            class="flex h-5 w-5 shrink-0 items-center justify-center rounded-md border"
            :class="isSelected(svc.external_id)
              ? 'border-indigo-500 bg-indigo-500 text-white'
              : 'border-slate-300 bg-white'"
          >
            <Check v-if="isSelected(svc.external_id)" class="h-3.5 w-3.5" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="block truncate text-sm text-slate-800">{{ stripCode(svc.name) }}</span>
            <span class="block text-[11px] text-slate-400">
              #{{ svc.external_id }}<span v-if="svc.price"> · {{ formatPrice(svc.price) }}</span>
              <span v-if="!svc.is_enabled" class="text-amber-500"> · выключена</span>
            </span>
          </span>
        </button>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="$emit('update:open', false)">Отмена</Button>
        <Button :disabled="saving" @click="save">
          <Loader2 v-if="saving" class="mr-1.5 h-4 w-4 animate-spin" />
          Сохранить{{ selected.length ? ` (${selected.length})` : '' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, Loader2, Search, X } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '~/components/ui/dialog'
import { useAgents } from '~/composables/useAgents'

type CachedService = {
  external_id: number
  name: string
  price: number | null
  is_enabled: boolean
}

const props = defineProps<{
  open: boolean
  agentId: string
  /** Текущие привязанные external_id (строки). */
  modelValue: string[]
  saving?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', v: boolean): void
  (e: 'save', v: string[]): void
}>()

const { fetchSqnsServicesCached } = useAgents()

const services = ref<CachedService[]>([])
const loading = ref(false)
const query = ref('')
const selected = ref<string[]>([])

const load = async () => {
  loading.value = true
  try {
    const acc: CachedService[] = []
    let offset = 0
    // тянем страницами по 1000 (лимит бэкенда)
    for (let page = 0; page < 5; page++) {
      const res = await fetchSqnsServicesCached(props.agentId, { limit: 1000, offset })
      const batch = (res?.services ?? []) as CachedService[]
      acc.push(...batch)
      if (batch.length < 1000) break
      offset += 1000
    }
    services.value = acc
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      selected.value = [...(props.modelValue || [])]
      query.value = ''
      if (!services.value.length) void load()
    }
  },
  { immediate: true },
)

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  const list = q
    ? services.value.filter((s) => s.name.toLowerCase().includes(q) || String(s.external_id).includes(q))
    : services.value
  return list.slice(0, 200)
})

const isSelected = (ext: number | string) => selected.value.includes(String(ext))

const toggle = (ext: string) => {
  if (selected.value.includes(ext)) selected.value = selected.value.filter((x) => x !== ext)
  else selected.value = [...selected.value, ext]
}

const nameFor = (ext: string) => {
  const svc = services.value.find((s) => String(s.external_id) === ext)
  return svc ? stripCode(svc.name) : `#${ext}`
}

/** Убрать медкод типа «А11.01.12 » в начале названия. */
const stripCode = (name: string) => name.replace(/^[A-Za-zА-Яа-я]?\d{2}\.\d{2}\.\d{2,3}\s*/u, '').trim() || name

const formatPrice = (price: number) =>
  new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(price)

const save = () => emit('save', [...selected.value])
</script>
