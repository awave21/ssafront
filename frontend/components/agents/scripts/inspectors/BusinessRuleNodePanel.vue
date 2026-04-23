<template>
  <div class="script-flow-node-panel">
    <div class="rounded-xl border border-sky-500/35 bg-sky-500/[0.06] px-4 py-3 text-[11px] leading-snug text-muted-foreground shadow-sm dark:bg-sky-950/20">
      <p class="font-semibold text-foreground">Правило клиники или каталога</p>
      <p class="mt-1 leading-relaxed">
        Здесь задается не ход разговора, а правило вида «если ситуация такая — ассистент действует вот так».
        Удобно для приоритетов записи, ограничений, быстрых слотов и точных ответов по услугам или сотрудникам.
      </p>
    </div>
    <div class="flex items-center justify-between rounded-xl border border-border/80 bg-background/95 px-3 py-2.5 shadow-sm">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">1. Где показывать это правило</p>
        <span class="text-[11px] font-semibold leading-snug max-w-[220px] block">Показывать как правило каталога, а не как шаг на карте</span>
      </div>
      <button
        type="button"
        class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors"
        :class="localIsCatalogRule ? 'bg-primary' : 'bg-muted-foreground/30'"
        @click="localIsCatalogRule = !localIsCatalogRule; flushNode()"
      >
        <span
          class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
          :class="localIsCatalogRule ? 'translate-x-4' : 'translate-x-1'"
        />
      </button>
    </div>
    <div class="rounded-xl border border-border/80 bg-background/95 px-4 py-4 shadow-sm space-y-3">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">2. К чему относится это правило</p>
        <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
          Выберите источник данных, сущность и приоритет, чтобы ассистент правильно применял правило.
        </p>
      </div>
      <div class="space-y-1">
        <label class="insp-label">Откуда берутся данные для правила</label>
        <select v-model="localDataSource" class="insp-input" @change="flushNode">
          <option value="sqns_resources">Сотрудники</option>
          <option value="sqns_services">Услуги</option>
          <option value="custom_table">Другое</option>
        </select>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div class="space-y-1">
          <label class="insp-label">С чем связано правило</label>
          <select v-model="localEntityType" class="insp-input" @change="flushNode">
            <option value="employee">Сотрудник</option>
            <option value="service">Услуга</option>
            <option value="custom">Custom</option>
          </select>
        </div>
        <div class="space-y-1">
          <label class="insp-label">Приоритет правила</label>
          <input v-model.number="localRulePriority" type="number" min="1" max="999" class="insp-input" @input="flushNode">
        </div>
      </div>
      <div class="space-y-1">
        <label class="insp-label">Конкретная сущность</label>
        <ScriptFlowEntityCombobox
          v-if="localEntityType !== 'custom'"
          :model-value="localEntityId"
          :options="baseEntityOptions"
          :search-placeholder="localEntityType === 'employee' ? 'Поиск сотрудника…' : 'Поиск услуги…'"
          @update:model-value="setEntityId"
          @picked="onEntityPick"
        />
        <input v-else v-model="localEntityId" class="insp-input" placeholder="ID" @input="flushNode">
      </div>
    </div>
    <div
      v-if="localEntityId && localEntityType !== 'custom' && (patchSpecialistProfile || patchServiceDescription)"
      class="space-y-1 rounded-xl border border-border/80 bg-background/95 p-3 shadow-sm"
    >
      <label class="insp-label">Расширенное описание в справочнике</label>
      <textarea
        v-model="sqnsProfileDraft"
        rows="5"
        class="insp-input resize-none text-[11px]"
        placeholder="Более подробное описание сущности; сохранится в справочник при паузе ввода"
        @input="debouncedSaveSqnsProfile"
      />
      <p v-if="sqnsProfileSaving" class="text-[10px] text-muted-foreground">Сохранение в справочник…</p>
    </div>
    <div class="rounded-xl border border-border/80 bg-background/95 px-4 py-4 shadow-sm space-y-3">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">3. Когда правило срабатывает и что делать</p>
        <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
          Опишите условие, нужный контекст и действие ассистента, которое должно произойти по этому правилу.
        </p>
      </div>
      <div class="space-y-1">
        <label class="insp-label">Когда это правило должно сработать</label>
        <textarea v-model="localRuleCondition" rows="3" class="insp-input resize-none" @input="flushNode" />
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div class="space-y-1">
          <label class="insp-label">Какой контекст обязателен</label>
          <select v-model="localRequiresEntity" class="insp-input" @change="flushNode">
            <option value="none">Не требуется</option>
            <option value="service">Услуга</option>
            <option value="employee">Сотрудник</option>
            <option value="both">Оба</option>
          </select>
        </div>
        <div class="space-y-1">
          <label class="insp-label">После каких шагов это особенно уместно</label>
          <div class="max-h-28 overflow-auto rounded-xl border border-border/80 bg-background/95 p-2 shadow-sm">
            <button
              v-for="nref in flowNodeRefOptions.filter((n) => n.id !== props.nodeId)"
              :key="nref.id"
              type="button"
              class="mb-1 mr-1 rounded-full border px-2 py-0.5 text-[10px]"
              :class="localMustFollowNodeRefs.includes(nref.id) ? 'border-primary bg-primary/10' : 'border-border'"
              @click="toggleMustFollowNodeRef(nref.id)"
            >
              {{ nref.title }}
            </button>
          </div>
        </div>
      </div>
      <div class="space-y-1">
        <label class="insp-label">Что ассистент должен сделать по этому правилу</label>
        <textarea v-model="localRuleAction" rows="4" class="insp-input resize-none" @input="flushNode" />
      </div>
    </div>
    <div class="flex items-center justify-between rounded-xl border border-border/80 bg-background/95 px-3 py-2.5 shadow-sm">
      <span class="text-[11px] font-semibold">Правило активно и участвует в работе ассистента</span>
      <button
        type="button"
        class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors"
        :class="localRuleActive ? 'bg-primary' : 'bg-muted-foreground/30'"
        @click="localRuleActive = !localRuleActive; flushNode()"
      >
        <span
          class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
          :class="localRuleActive ? 'translate-x-4' : 'translate-x-1'"
        />
      </button>
    </div>
    <div class="border-t border-border pt-4">
      <InspectorKgLinks />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref, watch, type ComputedRef, type Ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { SCRIPT_FLOW_INSPECTOR_KEY } from '~/composables/useScriptFlowInspectorModel'
import InspectorKgLinks from './InspectorKgLinks.vue'
import ScriptFlowEntityCombobox from './ScriptFlowEntityCombobox.vue'

const props = defineProps<{
  nodeId: string | null
}>()

const {
  localDataSource,
  localEntityType,
  localEntityId,
  localRuleCondition,
  localRuleAction,
  localRulePriority,
  localRuleActive,
  localRequiresEntity,
  localMustFollowNodeRefs,
  localIsCatalogRule,
  flushNode,
  toggleMustFollowNodeRef,
} = inject(SCRIPT_FLOW_INSPECTOR_KEY)!

const flowServiceOptions = inject<Ref<Array<{ id: string; name: string }>>>(
  'flowServiceOptions',
  ref([]),
)
const flowEmployeeOptions = inject<Ref<Array<{ id: string; name: string; active?: boolean }>>>(
  'flowEmployeeOptions',
  ref([]),
)
const flowNodeRefOptions = inject<Ref<Array<{ id: string; title: string; node_type: string }>>>(
  'flowNodeRefOptions',
  ref([]),
)

const catalogSpecialistMap = inject<ComputedRef<Record<string, { information?: string | null }>>>(
  'catalogSpecialistMap',
  computed(() => ({})),
)
const catalogServiceMap = inject<ComputedRef<Record<string, { description?: string | null }>>>(
  'catalogServiceMap',
  computed(() => ({})),
)

type PatchProfileFn = (id: string, text: string) => Promise<void>
const patchSpecialistProfile = inject<PatchProfileFn | undefined>('sqnsPatchSpecialistProfile', undefined)
const patchServiceDescription = inject<PatchProfileFn | undefined>('sqnsPatchServiceDescription', undefined)

const sqnsProfileDraft = ref('')
const sqnsProfileSaving = ref(false)
const syncingProfileFromMaps = ref(false)

const baseEntityOptions = computed(() =>
  localEntityType.value === 'employee' ? flowEmployeeOptions.value : flowServiceOptions.value,
)

const setEntityId = (id: string) => {
  localEntityId.value = id
}

const onEntityPick = () => {
  flushNode()
  syncSqnsDraftFromMaps()
}

const readProfileFromMaps = (): string => {
  const id = localEntityId.value
  if (!id || localEntityType.value === 'custom') return ''
  if (localEntityType.value === 'employee')
    return catalogSpecialistMap.value[id]?.information ?? ''
  return catalogServiceMap.value[id]?.description ?? ''
}

const syncSqnsDraftFromMaps = () => {
  syncingProfileFromMaps.value = true
  sqnsProfileDraft.value = readProfileFromMaps()
  syncingProfileFromMaps.value = false
}

watch(
  () => [localEntityId.value, localEntityType.value, catalogSpecialistMap.value, catalogServiceMap.value] as const,
  () => {
    if (syncingProfileFromMaps.value) return
    syncSqnsDraftFromMaps()
  },
  { immediate: true },
)

const persistSqnsProfile = async () => {
  if (syncingProfileFromMaps.value) return
  const id = localEntityId.value
  if (!id || localEntityType.value === 'custom') return
  try {
    sqnsProfileSaving.value = true
    if (localEntityType.value === 'employee' && patchSpecialistProfile)
      await patchSpecialistProfile(id, sqnsProfileDraft.value)
    else if (localEntityType.value === 'service' && patchServiceDescription)
      await patchServiceDescription(id, sqnsProfileDraft.value)
  }
  finally {
    sqnsProfileSaving.value = false
  }
}

const debouncedSaveSqnsProfile = useDebounceFn(persistSqnsProfile, 650)
</script>
