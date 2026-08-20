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
            <h2 class="text-lg font-bold text-slate-900">Jivo</h2>
            <p class="text-sm text-slate-500 mt-0.5">Онлайн-чат и мессенджеры Jivo — ответы агентом</p>
          </div>
          <button
            type="button"
            aria-label="Закрыть"
            @click="emit('update:open', false)"
            class="p-2 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X class="w-5 h-5 text-slate-500" />
          </button>
        </div>

        <!-- Tabs -->
        <div class="shrink-0 px-6 pt-4">
          <div class="flex gap-6 border-b border-slate-200">
            <button
              v-for="tab in tabs"
              :key="tab.value"
              @click="activeTab = tab.value"
              :class="[
                'pb-3 -mb-px text-sm font-bold border-b-2 transition-colors',
                activeTab === tab.value
                  ? 'border-primary text-primary'
                  : 'border-transparent text-slate-400 hover:text-slate-600'
              ]"
            >
              {{ tab.label }}
            </button>
          </div>
        </div>

        <!-- Body -->
        <div class="flex-1 overflow-y-auto px-6 py-5 space-y-6">
          <div v-if="isPreparing" class="flex justify-center py-12">
            <Loader2 class="w-8 h-8 animate-spin text-primary" />
          </div>

          <template v-else>
            <!-- === Подключение === -->
            <div v-show="activeTab === 'connect'" class="space-y-4">
              <div class="space-y-1.5">
                <label class="text-xs font-black uppercase tracking-wider text-slate-500">ID провайдера</label>
                <input
                  v-model="providerId"
                  type="text"
                  placeholder="Например: 123456"
                  class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                />
              </div>

              <div class="space-y-1.5">
                <label class="text-xs font-black uppercase tracking-wider text-slate-500">Путь к ответу</label>
                <input
                  v-model="replyBaseUrl"
                  type="text"
                  placeholder="https://bot.jivosite.com/webhooks"
                  class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                />
                <p class="text-xs text-slate-400">
                  ID провайдера и путь к ответу выдаёт Jivo после подключения (см. вкладку
                  «Инструкция по подключению»).
                </p>
              </div>
            </div>

            <!-- === Инструкция по подключению === -->
            <div v-show="activeTab === 'instruction'" class="space-y-4">
              <div class="rounded-xl border border-sky-100 bg-sky-50/60 p-4">
                <div class="flex items-start gap-3">
                  <Mail class="w-5 h-5 text-sky-500 flex-shrink-0 mt-0.5" />
                  <p class="text-xs text-sky-800 leading-relaxed">
                    Для подключения напишите на
                    <span class="font-bold">info@jivosite.com</span> с темой
                    <span class="font-bold">«Подключение агента»</span> и текстом ниже. Впишите свою почту
                    от аккаунта Jivo и нужный канал.
                  </p>
                </div>
              </div>

              <div class="space-y-2">
                <label class="text-xs font-black uppercase tracking-wider text-slate-500">Webhook-URL для Jivo</label>
                <div class="flex items-start gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
                  <code class="flex-1 text-xs font-mono text-slate-700 break-all">{{ prepared?.webhook_url }}</code>
                  <button
                    @click="copyText(prepared?.webhook_url ?? '', 'URL скопирован')"
                    class="p-1 hover:text-primary transition-colors flex-shrink-0 mt-0.5"
                    aria-label="Скопировать URL"
                  >
                    <Copy class="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div class="space-y-2">
                <label class="text-xs font-black uppercase tracking-wider text-slate-500">Текст письма</label>
                <pre class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-mono text-slate-700 whitespace-pre-wrap break-all">{{ emailText }}</pre>
                <button
                  @click="copyText(emailText, 'Текст скопирован')"
                  class="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  <Copy class="w-3.5 h-3.5" />
                  Скопировать текст
                </button>
              </div>
            </div>
          </template>
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

          <button
            @click="handleSave"
            :disabled="isSaving || isPreparing"
            class="px-4 py-2 rounded-xl bg-primary text-sm font-semibold text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            <Loader2 v-if="isSaving" class="w-4 h-4 animate-spin" />
            <span v-else>{{ isConfigured ? 'Сохранить' : 'Подключить' }}</span>
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Copy, Loader2, Mail, X } from 'lucide-vue-next'
import { useAgentEditorStore, type JivoChannel, type JivoPrepareResult } from '~/composables/useAgentEditorStore'
import { useToast } from '~/composables/useToast'

const props = defineProps<{
  open: boolean
  channel: JivoChannel | null
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'connected'): void
  (e: 'disconnected'): void
}>()

const store = useAgentEditorStore()
const { success: toastSuccess, error: toastError } = useToast()

const DEFAULT_REPLY_BASE = 'https://bot.jivosite.com/webhooks'

const tabs = [
  { value: 'connect' as const, label: 'Подключение' },
  { value: 'instruction' as const, label: 'Инструкция по подключению' },
]

const activeTab = ref<'connect' | 'instruction'>('connect')
const isPreparing = ref(false)
const isSaving = ref(false)
const isDisconnecting = ref(false)
const prepared = ref<JivoPrepareResult | null>(null)
const providerId = ref('')
const replyBaseUrl = ref('')

const isConfigured = computed(() => Boolean(props.channel?.provider_id && props.channel?.reply_base_url))

const webhookBase = computed(() => {
  const url = prepared.value?.webhook_url ?? ''
  const tok = prepared.value?.provider_token ?? ''
  return tok && url.endsWith(tok) ? url.slice(0, url.length - tok.length) : url
})

const emailText = computed(() => {
  const full = prepared.value?.webhook_url ?? ''
  const tok = prepared.value?.provider_token ?? ''
  return [
    'Здравствуйте, хотелось бы подключить агента',
    '',
    'Вот данные:',
    `1) URL куда отправлять сообщения от клиентов - ${webhookBase.value}`,
    `Ссылка в формате ${webhookBase.value}TOKEN`,
    `Полноценная ссылка - ${full}`,
    '',
    `2) Токен описывался в первом пункте -`,
    tok,
    '',
    '3) Моя почта к аккаунту Jivo - (УКАЗЫВАЕТЕ ПОЧТУ)',
    'Канал к которому нужно подключить агента - (ПИШЕТЕ КАНАЛ Jivo)',
  ].join('\n')
})

watch(() => props.open, async (isOpen) => {
  if (!isOpen) return
  activeTab.value = 'connect'
  providerId.value = props.channel?.provider_id ?? ''
  replyBaseUrl.value = props.channel?.reply_base_url ?? DEFAULT_REPLY_BASE
  isPreparing.value = true
  try {
    prepared.value = await store.prepareJivoChannel()
  } catch (err: any) {
    toastError(err?.data?.detail ?? err?.message ?? 'Не удалось подготовить подключение Jivo')
  } finally {
    isPreparing.value = false
  }
})

const copyText = async (text: string, message: string) => {
  if (!text) return
  await navigator.clipboard.writeText(text)
  toastSuccess(message)
}

const handleSave = async () => {
  const trimmedProviderId = providerId.value.trim()
  const trimmedReplyBase = replyBaseUrl.value.trim()
  if (!trimmedProviderId) {
    toastError('Укажите ID провайдера', 'Его выдаёт Jivo после подключения')
    activeTab.value = 'connect'
    return
  }
  if (!trimmedReplyBase) {
    toastError('Укажите путь к ответу')
    activeTab.value = 'connect'
    return
  }
  isSaving.value = true
  try {
    await store.finalizeJivoChannel(trimmedProviderId, trimmedReplyBase)
    toastSuccess('Jivo подключён', 'Агент будет отвечать на сообщения из Jivo')
    emit('connected')
  } catch (err: any) {
    toastError(err?.data?.detail ?? err?.message ?? 'Не удалось сохранить настройки Jivo')
  } finally {
    isSaving.value = false
  }
}

const handleDisconnect = async () => {
  if (!confirm('Отключить Jivo? Агент перестанет отвечать на сообщения из Jivo.')) return
  isDisconnecting.value = true
  try {
    await store.disconnectChannel('jivo')
    toastSuccess('Jivo отключён')
    emit('disconnected')
  } catch (err: any) {
    toastError(err?.data?.detail ?? err?.message ?? 'Не удалось отключить Jivo')
  } finally {
    isDisconnecting.value = false
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
