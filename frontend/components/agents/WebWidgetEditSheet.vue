<template>
  <Teleport to="body">
    <Transition name="overlay-fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[60] bg-black/40"
        aria-hidden="true"
        @click="emit('update:open', false)"
      />
    </Transition>

    <Transition name="panel-slide">
      <div
        v-if="open"
        class="fixed right-0 top-0 bottom-0 z-[61] w-full max-w-lg bg-white shadow-xl border-l border-slate-200 flex flex-col max-h-full overflow-hidden"
        aria-modal="true"
        role="dialog"
        @click.stop
      >
        <!-- Header -->
        <div class="flex items-center justify-between shrink-0 px-6 py-4 border-b border-slate-200">
          <div>
            <h2 class="text-lg font-bold text-slate-900">Виджет на сайт</h2>
            <p class="text-sm text-slate-500 mt-0.5">Настройте внешний вид и получите код для встраивания</p>
          </div>
          <button type="button" aria-label="Закрыть" @click="emit('update:open', false)"
            class="p-2 rounded-lg hover:bg-slate-100 transition-colors">
            <X class="w-5 h-5 text-slate-500" />
          </button>
        </div>

        <!-- Body -->
        <div class="flex-1 overflow-y-auto px-6 py-5 space-y-6">

          <!-- One-time key alert -->
          <div v-if="newRawKey" class="rounded-xl border border-amber-200 bg-amber-50 p-4">
            <div class="flex items-start gap-3">
              <AlertTriangle class="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
              <div class="flex-1 min-w-0">
                <p class="text-sm font-bold text-amber-800">Сохраните API-ключ</p>
                <p class="text-xs text-amber-700 mt-0.5">Ключ показывается только один раз. После закрытия его нельзя восстановить.</p>
                <div class="mt-2 flex items-center gap-2 rounded-lg bg-white border border-amber-200 px-3 py-2">
                  <code class="flex-1 text-xs font-mono text-slate-800 break-all select-all">{{ newRawKey }}</code>
                  <button @click="copyKey(newRawKey!)" class="p-1 hover:text-primary transition-colors flex-shrink-0">
                    <Copy class="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Embed snippet -->
          <div v-if="channel" class="space-y-2">
            <label class="text-xs font-black uppercase tracking-wider text-slate-500">Код для встраивания</label>
            <div class="flex items-start gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
              <code class="flex-1 text-xs font-mono text-slate-700 break-all">{{ embedSnippet }}</code>
              <button @click="copySnippet" class="p-1 hover:text-primary transition-colors flex-shrink-0 mt-0.5">
                <Copy class="w-4 h-4" />
              </button>
            </div>
            <p class="text-xs text-slate-400">Вставьте перед закрывающим тегом &lt;/body&gt; на вашем сайте.</p>
          </div>

          <!-- Settings form -->
          <div class="space-y-4">
            <div class="space-y-1.5">
              <label class="text-xs font-black uppercase tracking-wider text-slate-500">Заголовок чата</label>
              <input
                v-model="form.title"
                type="text"
                maxlength="60"
                placeholder="Чат с нами"
                class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
            </div>

            <div class="space-y-1.5">
              <label class="text-xs font-black uppercase tracking-wider text-slate-500">Подзаголовок</label>
              <input
                v-model="form.subtitle"
                type="text"
                maxlength="100"
                placeholder="Обычно отвечаем за несколько минут"
                class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
            </div>

            <div class="space-y-1.5">
              <label class="text-xs font-black uppercase tracking-wider text-slate-500">Приветственное сообщение</label>
              <textarea
                v-model="form.welcome_message"
                rows="2"
                maxlength="500"
                placeholder="Здравствуйте! Чем могу помочь?"
                class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-none"
              />
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div class="space-y-1.5">
                <label class="text-xs font-black uppercase tracking-wider text-slate-500">Основной цвет</label>
                <div class="flex items-center gap-2">
                  <input
                    v-model="form.primary_color"
                    type="color"
                    class="w-10 h-10 rounded-lg border border-slate-200 cursor-pointer p-1 bg-white"
                  />
                  <input
                    v-model="form.primary_color"
                    type="text"
                    maxlength="7"
                    placeholder="#3B82F6"
                    class="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                  />
                </div>
              </div>

              <div class="space-y-1.5">
                <label class="text-xs font-black uppercase tracking-wider text-slate-500">Позиция</label>
                <div class="flex gap-2">
                  <button
                    v-for="pos in positions"
                    :key="pos.value"
                    @click="form.position = pos.value"
                    :class="[
                      'flex-1 py-2 rounded-xl border text-xs font-bold transition-all',
                      form.position === pos.value
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-slate-200 text-slate-500 hover:border-slate-300'
                    ]"
                  >
                    {{ pos.label }}
                  </button>
                </div>
              </div>
            </div>

            <div class="space-y-2">
              <label class="text-xs font-black uppercase tracking-wider text-slate-500">Иконка кнопки</label>
              <div class="flex gap-3">
                <button
                  v-for="icon in launcherIcons"
                  :key="icon.value"
                  @click="form.launcher_icon = icon.value"
                  :class="[
                    'flex flex-col items-center gap-1.5 px-4 py-3 rounded-xl border text-xs font-semibold transition-all',
                    form.launcher_icon === icon.value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-slate-200 text-slate-500 hover:border-slate-300'
                  ]"
                >
                  <component :is="icon.component" class="w-5 h-5" />
                  {{ icon.label }}
                </button>
              </div>
            </div>

            <div class="space-y-1.5">
              <label class="text-xs font-black uppercase tracking-wider text-slate-500">
                Разрешённые домены
                <span class="font-normal normal-case tracking-normal text-slate-400 ml-1">(необязательно)</span>
              </label>
              <div class="space-y-2">
                <div v-for="(origin, idx) in form.allowed_origins" :key="idx" class="flex items-center gap-2">
                  <input
                    v-model="form.allowed_origins[idx]"
                    type="text"
                    placeholder="example.com"
                    class="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                  />
                  <button @click="removeOrigin(idx)" class="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500 transition-colors">
                    <X class="w-4 h-4" />
                  </button>
                </div>
                <button @click="addOrigin" class="text-xs font-semibold text-primary hover:text-primary/80 transition-colors flex items-center gap-1">
                  <Plus class="w-3.5 h-3.5" />
                  Добавить домен
                </button>
              </div>
              <p class="text-xs text-slate-400">Пусто — виджет работает на любом сайте.</p>
            </div>
          </div>

          <!-- Preview -->
          <div class="space-y-2">
            <label class="text-xs font-black uppercase tracking-wider text-slate-500">Предпросмотр кнопки</label>
            <div class="rounded-xl border border-slate-100 bg-slate-50 h-24 relative overflow-hidden">
              <div
                class="absolute bottom-4 w-14 h-14 rounded-full shadow-lg flex items-center justify-center cursor-pointer transition-transform hover:scale-105"
                :style="{ backgroundColor: form.primary_color, [form.position === 'bottom-right' ? 'right' : 'left']: '16px' }"
              >
                <component :is="currentIconComponent" class="w-6 h-6 text-white" />
              </div>
            </div>
          </div>

        </div>

        <!-- Footer -->
        <div class="shrink-0 px-6 py-4 border-t border-slate-200 flex items-center justify-between gap-3">
          <button
            v-if="channel"
            @click="handleDisconnect"
            :disabled="isSaving || isDisconnecting"
            class="px-4 py-2 rounded-xl border border-red-200 text-sm font-semibold text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            <Loader2 v-if="isDisconnecting" class="w-4 h-4 animate-spin" />
            <span v-else>Отключить</span>
          </button>
          <div v-else />

          <div class="flex items-center gap-2">
            <button
              v-if="channel"
              @click="handleRotateKey"
              :disabled="isSaving || isRotatingKey"
              class="px-3 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50"
            >
              <Loader2 v-if="isRotatingKey" class="w-3.5 h-3.5 animate-spin" />
              <span v-else>Перевыпустить ключ</span>
            </button>

            <button
              @click="handleSave"
              :disabled="isSaving"
              class="px-4 py-2 rounded-xl bg-primary text-sm font-semibold text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              <Loader2 v-if="isSaving" class="w-4 h-4 animate-spin" />
              <span v-else>Сохранить</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { AlertTriangle, Copy, Loader2, MessageCircle, Plus, Sparkles, X } from 'lucide-vue-next'
import { useAgentEditorStore, type WebWidgetChannel, type WidgetSettings } from '~/composables/useAgentEditorStore'
import { useToast } from '~/composables/useToast'

const props = defineProps<{
  open: boolean
  channel: WebWidgetChannel | null
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'connected'): void
  (e: 'disconnected'): void
}>()

const store = useAgentEditorStore()
const { success: toastSuccess, error: toastError } = useToast()

const isSaving = ref(false)
const isDisconnecting = ref(false)
const isRotatingKey = ref(false)
const newRawKey = ref<string | null>(null)

const positions = [
  { value: 'bottom-right' as const, label: 'Справа' },
  { value: 'bottom-left' as const, label: 'Слева' },
]

const launcherIcons = [
  { value: 'chat' as const, label: 'Чат', component: MessageCircle },
  { value: 'bubble' as const, label: 'Пузырь', component: MessageCircle },
  { value: 'sparkle' as const, label: 'Искра', component: Sparkles },
]

const defaultForm = (): WidgetSettings & { allowed_origins: string[] } => ({
  title: 'Чат с нами',
  subtitle: '',
  welcome_message: '',
  primary_color: '#3B82F6',
  position: 'bottom-right',
  launcher_icon: 'chat',
  allowed_origins: [],
})

const form = ref(defaultForm())

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    newRawKey.value = null
    if (props.channel) {
      const s = props.channel.widget_settings
      form.value = {
        title: s.title ?? 'Чат с нами',
        subtitle: s.subtitle ?? '',
        welcome_message: s.welcome_message ?? '',
        primary_color: s.primary_color ?? '#3B82F6',
        position: s.position ?? 'bottom-right',
        launcher_icon: s.launcher_icon ?? 'chat',
        allowed_origins: [...(props.channel.widget_allowed_origins ?? [])],
      }
    } else {
      form.value = defaultForm()
    }
  }
})

const currentIconComponent = computed(() => {
  const icon = launcherIcons.find(i => i.value === form.value.launcher_icon)
  return icon?.component ?? MessageCircle
})

const embedSnippet = computed(() => {
  if (!props.channel) return ''
  const host = window.location.origin
  return `<script src="${host}/widget/loader.js" data-key="···${props.channel.widget_api_key_last4 ?? '????'}"><\/script>`
})

const addOrigin = () => form.value.allowed_origins.push('')
const removeOrigin = (idx: number) => form.value.allowed_origins.splice(idx, 1)

const copyKey = async (key: string) => {
  await navigator.clipboard.writeText(key)
  toastSuccess('Ключ скопирован')
}

const copySnippet = async () => {
  if (!props.channel) return
  const host = window.location.origin
  // We need real key for the snippet — show placeholder if not available
  const snippet = `<script src="${host}/widget/loader.js" data-key="···${props.channel.widget_api_key_last4 ?? '????'}"><\/script>`
  await navigator.clipboard.writeText(snippet)
  toastSuccess('Сниппет скопирован')
}

const handleSave = async () => {
  isSaving.value = true
  try {
    const settings: WidgetSettings = {
      title: form.value.title,
      subtitle: form.value.subtitle || null,
      welcome_message: form.value.welcome_message || null,
      primary_color: form.value.primary_color,
      position: form.value.position,
      launcher_icon: form.value.launcher_icon,
    }
    const origins = form.value.allowed_origins.filter(o => o.trim())
    await store.updateWidgetSettings(settings, origins)
    toastSuccess('Настройки виджета сохранены')
    emit('connected')
  } catch (err: any) {
    toastError(err?.data?.detail ?? err?.message ?? 'Ошибка сохранения')
  } finally {
    isSaving.value = false
  }
}

const handleDisconnect = async () => {
  if (!confirm('Отключить виджет? Встроенный на сайте виджет перестанет работать.')) return
  isDisconnecting.value = true
  try {
    await store.disconnectChannel('web_widget')
    toastSuccess('Виджет отключён')
    emit('disconnected')
  } catch (err: any) {
    toastError(err?.data?.detail ?? err?.message ?? 'Ошибка отключения')
  } finally {
    isDisconnecting.value = false
  }
}

const handleRotateKey = async () => {
  if (!confirm('Перевыпустить ключ? Текущий ключ перестанет работать немедленно.')) return
  isRotatingKey.value = true
  try {
    const result = await store.rotateWebWidgetKey()
    if (result) {
      newRawKey.value = result.raw_api_key
      await store.fetchChannels()
      toastSuccess('Ключ перевыпущен')
    }
  } catch (err: any) {
    toastError(err?.data?.detail ?? err?.message ?? 'Ошибка перевыпуска ключа')
  } finally {
    isRotatingKey.value = false
  }
}
</script>

<style scoped>
.overlay-fade-enter-active,
.overlay-fade-leave-active {
  transition: opacity 0.2s ease;
}
.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
}

.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: transform 0.25s ease;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  transform: translateX(100%);
}
</style>
