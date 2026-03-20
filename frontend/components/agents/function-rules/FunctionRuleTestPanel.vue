<template>
  <div class="space-y-4">
    <div class="grid gap-4 rounded-md border border-slate-200 p-4">
      <div class="grid gap-2">
        <label class="text-sm font-medium text-slate-900">Тестовое сообщение</label>
        <Textarea v-model="local.message" placeholder="Напишите тестовое сообщение..." />
      </div>
      <div class="grid gap-2 md:grid-cols-2">
        <div class="grid gap-2">
          <label class="text-sm font-medium text-slate-900">Session ID</label>
          <Input v-model="local.session_id" placeholder="session_123" />
        </div>
        <div class="flex items-center justify-between rounded-md border border-slate-200 p-3 md:mt-7">
          <div class="text-sm text-slate-700">Выполнять реальные вызовы</div>
          <Switch :model-value="local.execute_tool_calls" @update:model-value="local.execute_tool_calls = !!$event" />
        </div>
      </div>
      <div class="grid gap-2">
        <label class="text-sm font-medium text-slate-900">История сообщений (JSON, опционально)</label>
        <Textarea v-model="historicalMessagesText" placeholder="[{&quot;role&quot;:&quot;user&quot;,&quot;content&quot;:&quot;...&quot;}]" />
      </div>
      <div class="flex justify-end">
        <Button :disabled="loading" @click="submit">Запустить тест</Button>
      </div>
    </div>

    <div v-if="result" class="grid gap-3 rounded-md border border-slate-200 p-4">
      <div class="text-sm font-semibold text-slate-900">Результат теста</div>
      <div class="grid gap-1 text-sm text-slate-700">
        <div>Trace ID: <span class="font-mono">{{ result.trace_id }}</span></div>
        <div>Нужна пауза: <span class="font-medium">{{ result.should_pause ? 'Да' : 'Нет' }}</span></div>
        <div>Теги: <span class="font-mono">{{ result.tags_created.join(', ') || '—' }}</span></div>
      </div>
      <div>
        <div class="mb-1 text-xs font-semibold uppercase text-slate-500">Условия</div>
        <pre class="overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-100">{{ JSON.stringify(result.rules, null, 2) }}</pre>
      </div>
      <div>
        <div class="mb-1 text-xs font-semibold uppercase text-slate-500">Действия</div>
        <pre class="overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-100">{{ JSON.stringify(result.actions, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Textarea } from '~/components/ui/textarea'
import { Switch } from '~/components/ui/switch'
import type { FunctionRuleTestRequest, FunctionRuleTestResponse } from '~/types/functionRuleTest'

const props = defineProps<{
  loading: boolean
  result: FunctionRuleTestResponse | null
}>()

const emit = defineEmits<{
  submit: [payload: FunctionRuleTestRequest]
}>()

const local = reactive<FunctionRuleTestRequest>({
  message: '',
  session_id: '',
  execute_tool_calls: false,
})

const historicalMessagesText = ref('')

const submit = () => {
  let historicalMessages: FunctionRuleTestRequest['historical_messages'] | undefined
  if (historicalMessagesText.value.trim()) {
    try {
      historicalMessages = JSON.parse(historicalMessagesText.value)
    } catch {
      historicalMessages = []
    }
  }
  emit('submit', {
    ...local,
    historical_messages: historicalMessages,
  })
}
</script>
