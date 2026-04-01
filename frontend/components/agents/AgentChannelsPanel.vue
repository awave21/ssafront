<template>
  <div class="bg-background rounded-md border border-border p-4 sm:p-5 space-y-5">
    <div class="mb-6">
      <h3 class="text-lg font-bold text-slate-900">Каналы связи</h3>
      <p class="text-sm text-slate-500 mt-1">
        Подключите мессенджеры и другие каналы для общения с вашими клиентами через агента.
      </p>
    </div>

    <div v-if="isLoadingChannels" class="flex justify-center py-12">
      <Loader2 class="w-8 h-8 animate-spin text-indigo-600" />
    </div>

    <div v-else class="space-y-5">
      <div
        class="p-4 border rounded-lg transition-all"
        :class="[
          telegramChannel
            ? 'border-indigo-100 bg-indigo-50/30'
            : 'border-slate-100 bg-white hover:border-slate-200'
        ]"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="flex gap-4 min-w-0">
            <div class="w-12 h-12 bg-gradient-to-br from-blue-400 to-blue-600 rounded-md flex items-center justify-center">
              <Send class="w-6 h-6 text-white" />
            </div>
            <div class="min-w-0">
              <h4 class="font-bold text-slate-900">Подключение Telegram бота</h4>
              <p class="text-sm text-slate-500 mt-1">
                Подключите Telegram-бота для автоматического общения с клиентами.
              </p>
              <div v-if="telegramChannel" class="mt-3">
                <span
                  class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase"
                  :class="telegramChannel.webhook_enabled ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'"
                >
                  {{ telegramChannel.webhook_enabled ? 'Активен' : 'Неактивен' }}
                </span>
              </div>
            </div>
          </div>

          <button
            v-if="canEditAgents"
            @click="showChannelEditSheet = true"
            class="px-4 py-2 rounded-md text-sm font-bold transition-colors"
            :class="telegramChannel ? 'bg-indigo-600 text-white hover:bg-indigo-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
          >
            {{ telegramChannel ? 'Настроить' : 'Подключить' }}
          </button>
        </div>
      </div>

      <AgentChannelActionCard
        title="Подключение номера мессенджера Telegram"
        description="Подключение личного Telegram-аккаунта для обработки сообщений клиентов."
        :icon="MessageCircle"
        icon-class="bg-gradient-to-br from-cyan-400 to-cyan-600"
        :connected="Boolean(telegramPhoneChannel)"
        :is-authorized="Boolean(telegramPhoneChannel?.is_authorized)"
        :show-authorization-state="Boolean(telegramPhoneChannel)"
        :loading="channelLoading.telegramPhone"
        :show-authorize-button="Boolean(telegramPhoneChannel) && !Boolean(telegramPhoneChannel?.is_authorized)"
        :authorize-loading="qrLoading.telegramPhone"
        :can-edit="canEditAgents"
        disconnect-label="Выйти"
        @connect="connectPhoneChannel('telegramPhone', 'Telegram_Phone', 'номер Telegram')"
        @disconnect="disconnectPhoneChannel('telegramPhone', 'telegram_phone', 'номер Telegram')"
        @authorize="authorizePhoneChannel('telegramPhone', 'telegram_phone', 'Telegram')"
      />

      <AgentChannelActionCard
        title="Подключение номера мессенджера WhatsApp"
        description="Подключение номера WhatsApp для обработки сообщений клиентов."
        :icon="MessageSquare"
        icon-class="bg-gradient-to-br from-green-400 to-green-600"
        :connected="Boolean(whatsappPhoneChannel)"
        :is-authorized="Boolean(whatsappPhoneChannel?.is_authorized)"
        :show-authorization-state="Boolean(whatsappPhoneChannel)"
        :loading="channelLoading.whatsappPhone"
        :show-authorize-button="Boolean(whatsappPhoneChannel) && !Boolean(whatsappPhoneChannel?.is_authorized)"
        :authorize-loading="qrLoading.whatsappPhone"
        :can-edit="canEditAgents"
        disconnect-label="Выйти"
        @connect="connectPhoneChannel('whatsappPhone', 'Whatsapp_Phone', 'номер WhatsApp')"
        @disconnect="disconnectPhoneChannel('whatsappPhone', 'whatsapp', 'номер WhatsApp')"
        @authorize="authorizePhoneChannel('whatsappPhone', 'whatsapp', 'WhatsApp')"
      />

      <AgentChannelActionCard
        title="Подключение номера мессенджера MAX"
        description="Подключение аккаунта MAX для обработки сообщений клиентов."
        :icon="Smartphone"
        icon-class="bg-gradient-to-br from-violet-400 to-violet-600"
        :connected="Boolean(maxPhoneChannel)"
        :is-authorized="Boolean(maxPhoneChannel?.is_authorized)"
        :show-authorization-state="Boolean(maxPhoneChannel)"
        :loading="channelLoading.maxPhone"
        :show-authorize-button="Boolean(maxPhoneChannel) && !Boolean(maxPhoneChannel?.is_authorized)"
        :authorize-loading="qrLoading.maxPhone"
        :can-edit="canEditAgents"
        disconnect-label="Выйти"
        @connect="connectPhoneChannel('maxPhone', 'Max_Phone', 'номер MAX')"
        @disconnect="disconnectPhoneChannel('maxPhone', 'max', 'номер MAX')"
        @authorize="authorizePhoneChannel('maxPhone', 'max', 'MAX')"
      />

      <div class="p-4 border border-slate-100 rounded-lg bg-slate-50/50 opacity-60">
        <div class="flex items-start justify-between">
          <div class="flex gap-4">
            <div class="w-12 h-12 bg-gradient-to-br from-purple-400 to-purple-600 rounded-md flex items-center justify-center">
              <MessageSquare class="w-6 h-6 text-white" />
            </div>
            <div>
              <h4 class="font-bold text-slate-900">Виджет на сайт</h4>
              <p class="text-sm text-slate-500 mt-1">
                Встраиваемый чат-виджет для вашего сайта.
              </p>
            </div>
          </div>
          <span class="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-200 text-slate-500 uppercase">
            Скоро
          </span>
        </div>
      </div>
    </div>

    <AgentChannelQrModal
      :open="showQrModal"
      :title="qrModalTitle"
      :qr-code="qrCodeImage"
      @update:open="showQrModal = $event"
    />
    <AgentChannelTwoFactorModal
      :open="showTwoFactorModal"
      :title="twoFactorModalTitle"
      :detail="twoFactorDetail"
      :error-message="twoFactorError"
      :loading="twoFactorLoading"
      @update:open="showTwoFactorModal = $event"
      @submit="submitTwoFactorPassword"
    />

    <ChannelEditSheet
      v-if="agent"
      :open="showChannelEditSheet"
      :agent-id="agent.id"
      :current-token="telegramChannel?.bot_token ?? undefined"
      @update:open="showChannelEditSheet = $event"
      @saved="handleChannelSaved"
      @deleted="handleChannelDeleted"
    />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { Loader2, MessageCircle, MessageSquare, Send, Smartphone } from 'lucide-vue-next'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { usePermissions } from '~/composables/usePermissions'
import { useToast } from '~/composables/useToast'
import ChannelEditSheet from '~/components/ChannelEditSheet.vue'
import AgentChannelActionCard from '~/components/agents/AgentChannelActionCard.vue'
import AgentChannelQrModal from '~/components/agents/AgentChannelQrModal.vue'
import AgentChannelTwoFactorModal from '~/components/agents/AgentChannelTwoFactorModal.vue'

type PhoneChannelKey = 'telegramPhone' | 'whatsappPhone' | 'maxPhone'
type PhoneChannelPublic = 'Telegram_Phone' | 'Whatsapp_Phone' | 'Max_Phone'
type PhoneChannelPath = 'telegram_phone' | 'whatsapp' | 'max'

const store = useAgentEditorStore()
const {
  agent,
  telegramChannel,
  telegramPhoneChannel,
  whatsappPhoneChannel,
  maxPhoneChannel,
  isLoadingChannels
} = storeToRefs(store)
const { canEditAgents } = usePermissions()
const { success: toastSuccess, error: toastError } = useToast()

const showChannelEditSheet = ref(false)
const channelLoading = ref<Record<PhoneChannelKey, boolean>>({
  telegramPhone: false,
  whatsappPhone: false,
  maxPhone: false
})
const qrLoading = ref<Record<PhoneChannelKey, boolean>>({
  telegramPhone: false,
  whatsappPhone: false,
  maxPhone: false
})
const showQrModal = ref(false)
const qrModalTitle = ref('Авторизация по QR')
const qrCodeImage = ref<string | null>(null)
const activeQrChannel = ref<PhoneChannelKey | null>(null)
const activeQrTitle = ref<string>('')
const activeTwoFactorChannelType = ref<PhoneChannelPath | null>(null)
const qrPollingTimer = ref<number | null>(null)
const showTwoFactorModal = ref(false)
const twoFactorModalTitle = ref('Введите пароль 2FA')
const twoFactorDetail = ref<string | null>(null)
const twoFactorError = ref<string | null>(null)
const twoFactorLoading = ref(false)

watch(agent, (value) => {
  if (value) {
    store.ensureChannelsLoaded()
  }
}, { immediate: true })

watch([showQrModal, showTwoFactorModal], ([isQrOpen, isTwoFactorOpen]) => {
  if (isQrOpen || isTwoFactorOpen) return
  if (qrPollingTimer.value !== null) {
    window.clearInterval(qrPollingTimer.value)
    qrPollingTimer.value = null
  }
  qrCodeImage.value = null
  activeQrChannel.value = null
  activeQrTitle.value = ''
  activeTwoFactorChannelType.value = null
  twoFactorModalTitle.value = 'Введите пароль 2FA'
  twoFactorDetail.value = null
  twoFactorError.value = null
  twoFactorLoading.value = false
})

const getErrorMessage = (err: any, fallback: string) => {
  const msg = err?.data?.detail ?? err?.data?.message ?? err?.message ?? fallback
  return typeof msg === 'string' ? msg : JSON.stringify(msg)
}

const isTwoFactorPasswordError = (message: string) => {
  const normalized = (message || '').toLowerCase()
  if (!normalized) return false
  if (normalized.includes('2fa_error')) return true
  return normalized.includes('2fa') && (
    normalized.includes('неверн')
    || normalized.includes('invalid')
    || normalized.includes('wrong')
  )
}

const getPhoneChannelByKey = (key: PhoneChannelKey) => {
  if (key === 'telegramPhone') return telegramPhoneChannel.value
  if (key === 'whatsappPhone') return whatsappPhoneChannel.value
  return maxPhoneChannel.value
}

const getPhoneChannelPathByKey = (key: PhoneChannelKey): PhoneChannelPath => {
  if (key === 'telegramPhone') return 'telegram_phone'
  if (key === 'whatsappPhone') return 'whatsapp'
  return 'max'
}

const handleAuthorizationSuccess = () => {
  const title = activeQrTitle.value || 'Канал'
  stopQrAuthorizationPolling()
  showQrModal.value = false
  showTwoFactorModal.value = false
  toastSuccess('Канал авторизован', `${title} успешно авторизован`)
}

const requestFreshQrAfterTwoFactorError = async () => {
  if (!activeTwoFactorChannelType.value) return
  const response = await store.fetchChannelAuthQr(activeTwoFactorChannelType.value)
  if (response.requires_2fa) {
    twoFactorDetail.value = response.detail ?? twoFactorDetail.value
    return
  }
  if (!response.qr_code) return

  qrModalTitle.value = `Авторизация ${activeQrTitle.value || 'канала'} по QR`
  qrCodeImage.value = response.qr_code
  showTwoFactorModal.value = false
  showQrModal.value = true
  startQrAuthorizationPolling()
  void pollQrAuthorizationStatus()
  toastSuccess('Получен новый QR-код', 'Повторите авторизацию через QR')
}

const stopQrAuthorizationPolling = () => {
  if (qrPollingTimer.value === null) return
  window.clearInterval(qrPollingTimer.value)
  qrPollingTimer.value = null
}

const pollQrAuthorizationStatus = async () => {
  if (!activeQrChannel.value) return
  try {
    await store.fetchChannels()
    const channel = getPhoneChannelByKey(activeQrChannel.value)
    if (channel?.is_authorized) {
      handleAuthorizationSuccess()
      return
    }

    if (showQrModal.value) {
      const channelPath = getPhoneChannelPathByKey(activeQrChannel.value)
      const authResponse = await store.fetchChannelAuthQr(channelPath)
      if (authResponse.requires_2fa) {
        showQrModal.value = false
        activeTwoFactorChannelType.value = channelPath
        twoFactorModalTitle.value = `Авторизация ${activeQrTitle.value}: пароль 2FA`
        twoFactorDetail.value = authResponse.detail ?? '2FA'
        twoFactorError.value = null
        showTwoFactorModal.value = true
        return
      }
      if (!authResponse.qr_code) {
        await store.fetchChannels()
        const refreshedChannel = getPhoneChannelByKey(activeQrChannel.value)
        if (refreshedChannel?.is_authorized) {
          handleAuthorizationSuccess()
          return
        }
      }
    }
  } catch {
    // Ошибки фонового опроса не блокируют пользователя.
  }
}

const startQrAuthorizationPolling = () => {
  stopQrAuthorizationPolling()
  qrPollingTimer.value = window.setInterval(() => {
    void pollQrAuthorizationStatus()
  }, 5000)
}

const connectPhoneChannel = async (
  key: PhoneChannelKey,
  publicType: PhoneChannelPublic,
  title: string
) => {
  channelLoading.value[key] = true
  try {
    await store.connectChannel({
      type: publicType,
      telegram_bot_token: null,
      whatsapp_phone: null
    })
    toastSuccess('Канал подключён', `${title} успешно подключен`)
  } catch (err: any) {
    toastError('Ошибка подключения', getErrorMessage(err, `Не удалось подключить ${title}`))
  } finally {
    channelLoading.value[key] = false
  }
}

const disconnectPhoneChannel = async (
  key: PhoneChannelKey,
  channelType: PhoneChannelPath,
  title: string
) => {
  channelLoading.value[key] = true
  try {
    await store.disconnectChannel(channelType)
    toastSuccess('Выход выполнен', `${title}: выполнен logout, можно авторизоваться снова`)
  } catch (err: any) {
    toastError('Ошибка отключения', getErrorMessage(err, `Не удалось отключить ${title}`))
  } finally {
    channelLoading.value[key] = false
  }
}

const authorizePhoneChannel = async (
  key: PhoneChannelKey,
  channelType: PhoneChannelPath,
  title: string
) => {
  qrLoading.value[key] = true
  try {
    const response = await store.fetchChannelAuthQr(channelType)
    activeQrChannel.value = key
    activeQrTitle.value = title
    if (response.requires_2fa) {
      showQrModal.value = false
      qrCodeImage.value = null
      activeTwoFactorChannelType.value = channelType
      twoFactorModalTitle.value = `Авторизация ${title}: пароль 2FA`
      twoFactorDetail.value = response.detail ?? '2FA'
      twoFactorError.value = null
      showTwoFactorModal.value = true
      startQrAuthorizationPolling()
      void pollQrAuthorizationStatus()
      return
    }

    if (!response.qr_code) {
      await store.fetchChannels()
      const refreshedChannel = getPhoneChannelByKey(key)
      if (refreshedChannel?.is_authorized) {
        handleAuthorizationSuccess()
        return
      }
      throw new Error('Сервис не вернул QR-код')
    }
    qrModalTitle.value = `Авторизация ${title} по QR`
    qrCodeImage.value = response.qr_code
    showQrModal.value = true
    startQrAuthorizationPolling()
    void pollQrAuthorizationStatus()
  } catch (err: any) {
    toastError('Ошибка авторизации', getErrorMessage(err, `Не удалось получить QR-код для ${title}`))
  } finally {
    qrLoading.value[key] = false
  }
}

const submitTwoFactorPassword = async (pwdCode: string) => {
  if (!activeTwoFactorChannelType.value) return
  twoFactorLoading.value = true
  twoFactorError.value = null
  try {
    const response = await store.submitChannelAuth2FA(activeTwoFactorChannelType.value, pwdCode)
    twoFactorDetail.value = response.detail ?? 'Пароль принят сервисом'
    await store.fetchChannels()
    if (activeQrChannel.value) {
      const channel = getPhoneChannelByKey(activeQrChannel.value)
      if (channel?.is_authorized) {
        handleAuthorizationSuccess()
        return
      }
    }
    toastSuccess('Пароль 2FA отправлен', 'Ожидаем подтверждение авторизации (online от webhook)')
    startQrAuthorizationPolling()
    void pollQrAuthorizationStatus()
  } catch (err: any) {
    const message = getErrorMessage(err, 'Не удалось отправить пароль 2FA')
    twoFactorError.value = message
    toastError('Ошибка 2FA', message)
    if (isTwoFactorPasswordError(message)) {
      try {
        await requestFreshQrAfterTwoFactorError()
      } catch {
        // Если не удалось обновить QR, остаемся на форме 2FA с исходной ошибкой.
      }
    }
  } finally {
    twoFactorLoading.value = false
  }
}

const handleChannelSaved = async () => {
  await store.fetchChannels()
  showChannelEditSheet.value = false
  toastSuccess('Канал обновлён', 'Настройки Telegram успешно сохранены')
}

const handleChannelDeleted = async () => {
  await store.fetchChannels()
  showChannelEditSheet.value = false
  toastSuccess('Канал удалён', 'Подключение Telegram отключено')
}

onBeforeUnmount(() => {
  stopQrAuthorizationPolling()
})
</script>
