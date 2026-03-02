<template>
  <Dialog :open="open" @update:open="handleClose">
    <DialogContent class="sm:max-w-lg" :show-close-button="false">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2">
          <CheckCircle2 class="h-5 w-5 text-green-500" />
          Ключ создан
        </DialogTitle>
        <DialogDescription>
          Скопируйте и сохраните ключ — он показывается <strong class="text-slate-900">только один раз</strong>.
          После закрытия этого окна восстановить его будет невозможно.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <!-- Secret key display -->
        <div class="relative">
          <div class="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
            <code class="flex-1 text-sm font-mono break-all select-all text-slate-800">{{ apiKey }}</code>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              @click="copyKey"
              class="shrink-0"
            >
              <Check v-if="isCopied" class="h-4 w-4 text-green-500" />
              <Copy v-else class="h-4 w-4" />
            </Button>
          </div>
          <p v-if="isCopied" class="mt-1 text-xs text-green-600">Скопировано в буфер обмена</p>
        </div>

        <!-- Usage docs -->
        <details class="group">
          <summary class="cursor-pointer text-sm font-medium text-indigo-600 hover:text-indigo-700 select-none">
            Как использовать ключ
          </summary>
          <div class="mt-3 space-y-4 text-sm">
            <div>
              <p class="font-medium text-slate-700 mb-1.5">Отправка сообщения:</p>
              <pre class="rounded-lg bg-slate-900 text-slate-100 p-3 text-xs overflow-x-auto whitespace-pre-wrap"><code>curl -X POST {{ apiHost }}/api/v1/integrations/chat \
  -H "x-api-key: {{ apiKey }}" \
  -H "Content-Type: application/json" \
  -d '{"message": "Привет!", "session_id": "optional-session-id"}'</code></pre>
            </div>

            <div>
              <p class="font-medium text-slate-700 mb-1.5">Пример ответа:</p>
              <pre class="rounded-lg bg-slate-900 text-slate-100 p-3 text-xs overflow-x-auto"><code>{
  "response": "Здравствуйте! Чем могу помочь?",
  "session_id": "integration:...:...",
  "run_id": "..."
}</code></pre>
            </div>

            <div>
              <p class="font-medium text-slate-700 mb-1.5">Стриминг (SSE):</p>
              <pre class="rounded-lg bg-slate-900 text-slate-100 p-3 text-xs overflow-x-auto whitespace-pre-wrap"><code>POST {{ apiHost }}/api/v1/integrations/chat/stream
Header: x-api-key: {{ apiKey }}
Body: {"message": "...", "session_id": "..."}
→ SSE events: start → result / error</code></pre>
            </div>

            <div>
              <p class="font-medium text-slate-700 mb-1.5">История диалога:</p>
              <pre class="rounded-lg bg-slate-900 text-slate-100 p-3 text-xs overflow-x-auto whitespace-pre-wrap"><code>GET {{ apiHost }}/api/v1/integrations/chat/history?session_id={id}&amp;limit=50
Header: x-api-key: {{ apiKey }}</code></pre>
            </div>
          </div>
        </details>
      </div>

      <DialogFooter>
        <Button @click="handleClose(false)" class="w-full sm:w-auto">
          Готово, ключ сохранён
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { CheckCircle2, Copy, Check } from 'lucide-vue-next'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '~/components/ui/dialog'
import { Button } from '~/components/ui/button'

const props = defineProps<{
  open: boolean
  apiKey: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'done': []
}>()

const isCopied = ref(false)

const { public: { apiBase, siteUrl } } = useRuntimeConfig()
const apiHost = computed(() => {
  if (siteUrl && siteUrl !== 'http://localhost:3000') return siteUrl
  return window.location.origin
})

const copyKey = async () => {
  try {
    await navigator.clipboard.writeText(props.apiKey)
    isCopied.value = true
    setTimeout(() => { isCopied.value = false }, 2000)
  } catch {
    // fallback
    const ta = document.createElement('textarea')
    ta.value = props.apiKey
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    isCopied.value = true
    setTimeout(() => { isCopied.value = false }, 2000)
  }
}

const handleClose = (val: boolean) => {
  if (!val) {
    isCopied.value = false
    emit('done')
    emit('update:open', false)
  }
}
</script>
