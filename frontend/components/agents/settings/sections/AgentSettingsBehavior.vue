<template>
  <div class="flex flex-col gap-5">
    <!-- Header -->
    <div class="flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
      <div class="flex items-center gap-2.5">
        <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <SlidersHorizontal class="h-4 w-4" />
        </div>
        <h1 class="text-lg font-semibold text-slate-900">Параметры поведения</h1>
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
      <p class="mb-2 font-medium text-slate-900">Как работают паузы и передача оператору</p>
      <p>
        Автопауза срабатывает, когда в диалог пишет сотрудник — бот замолкает на заданное
        время, чтобы не мешать. Уведомления в Telegram приходят в момент постановки диалога
        на паузу правилом (тег «эскалация»). Ручной глобальный тумблер «Отключить агента» —
        аварийный: бот перестаёт отвечать во всех диалогах.
      </p>
    </div>

    <!-- Название агента -->
    <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-slate-900">Название агента</span>
        <span class="text-xs text-slate-500">Отображается в списке агентов и в интерфейсе</span>
      </div>
      <input
        v-model="form.name"
        :disabled="!canEditAgents"
        type="text"
        placeholder="Например: Консультант, Стилия, Приёмная"
        maxlength="200"
        class="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60"
      />
    </div>

    <!-- Автопауза после ответа оператора -->
    <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-slate-900">Автопауза после ответа оператора</span>
        <span class="text-xs text-slate-500">Пауза в конкретном диалоге, автоматически возобновляется</span>
      </div>
      <div class="grid gap-3 sm:grid-cols-[220px_1fr]">
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-700">Длительность паузы (минуты)</label>
          <input
            v-model.number="form.manager_pause_minutes"
            :disabled="!canEditAgents"
            type="number"
            min="1"
            max="1440"
            step="1"
            class="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60"
          />
        </div>
        <p class="self-end text-xs text-slate-500">
          После сообщения оператора бот временно не отвечает в этом диалоге и автоматически возобновляет ответы по таймеру.
        </p>
      </div>
    </div>

    <!-- Уведомления менеджеру в Telegram -->
    <div class="space-y-4 rounded-2xl bg-slate-100 p-5">
      <div class="flex items-start justify-between gap-4">
        <div class="min-w-0">
          <div class="text-sm font-semibold text-slate-900">Уведомления менеджеру в Telegram</div>
          <p class="mt-1 text-xs text-slate-500">
            Когда правило ставит диалог на паузу, платформа отправит уведомление в чат менеджера. Требуется бот и chat_id.
          </p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <span
            class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
            :class="form.admin_notification_enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'"
          >
            <span
              class="mr-1 h-1.5 w-1.5 rounded-full"
              :class="form.admin_notification_enabled ? 'bg-emerald-500' : 'bg-slate-400'"
            />
            {{ form.admin_notification_enabled ? 'Включены' : 'Выключены' }}
          </span>
          <Switch
            :model-value="form.admin_notification_enabled"
            :disabled="!canEditAgents"
            @update:model-value="(enabled: boolean) => { form.admin_notification_enabled = enabled }"
          />
        </div>
      </div>
      <div v-if="form.admin_notification_enabled" class="grid gap-3 sm:grid-cols-2">
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-700">Токен Telegram-бота</label>
          <input
            v-model="form.admin_notification_bot_token"
            :disabled="!canEditAgents"
            type="text"
            placeholder="1234567890:AA..."
            class="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 font-mono text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60"
          />
          <p class="text-[11px] text-slate-500">Создайте отдельного бота через @BotFather. Токен вида 1234567890:AA...</p>
        </div>
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-700">Chat ID менеджера</label>
          <input
            v-model="form.admin_notification_chat_id"
            :disabled="!canEditAgents"
            type="text"
            placeholder="123456789 или -1001234567890"
            class="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 font-mono text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60"
          />
          <p class="text-[11px] text-slate-500">Менеджер должен один раз написать боту «Старт». Chat ID — через @userinfobot.</p>
        </div>
      </div>
    </div>

    <!-- Отключить агента -->
    <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
      <div class="flex items-start justify-between gap-4">
        <div class="min-w-0">
          <div class="text-sm font-semibold text-slate-900">Отключить агента</div>
          <p class="mt-1 text-xs text-slate-500">
            Аварийный глобальный тумблер. Бот перестанет отвечать во всех диалогах. Входящие сообщения продолжают сохраняться.
          </p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <span
            class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
            :class="form.is_disabled ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'"
          >
            <span
              class="mr-1 h-1.5 w-1.5 rounded-full"
              :class="form.is_disabled ? 'bg-amber-500' : 'bg-emerald-500'"
            />
            {{ form.is_disabled ? 'Выключен' : 'Включён' }}
          </span>
          <Switch
            :model-value="!form.is_disabled"
            :disabled="!canEditAgents"
            @update:model-value="(enabled: boolean) => { form.is_disabled = !enabled }"
          />
        </div>
      </div>
    </div>

    <!-- Опасная зона -->
    <div v-if="canEditAgents" class="space-y-3 rounded-2xl border border-red-100 bg-red-50/40 p-5">
      <div class="flex items-center gap-2">
        <AlertTriangle class="h-4 w-4 text-red-600" />
        <span class="text-sm font-semibold text-red-700">Опасная зона</span>
      </div>
      <p class="text-xs text-slate-600">Удаление агента приведёт к безвозвратной потере всех его настроек и истории.</p>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-xl border border-red-200 bg-white px-3 py-1.5 text-sm font-semibold text-red-600 hover:bg-red-50 transition-colors"
        @click="handleDelete"
      >
        <Trash2 class="h-3.5 w-3.5" />
        Удалить агента
      </button>
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
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { navigateTo } from '#app'
import { SlidersHorizontal, BookOpen, Trash2, AlertTriangle, Loader2, Check } from 'lucide-vue-next'
import { Switch } from '~/components/ui/switch'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { usePermissions } from '~/composables/usePermissions'

const store = useAgentEditorStore()
const { form } = storeToRefs(store)
const { canEditAgents } = usePermissions()
const helpOpen = ref(false)

const handleDelete = async () => {
  if (!confirm('Вы уверены, что хотите удалить этого агента? Это действие нельзя отменить.')) return
  const success = await store.removeAgent()
  if (success) {
    navigateTo('/agents')
  }
}
</script>
