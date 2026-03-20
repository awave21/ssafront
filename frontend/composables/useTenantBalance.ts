import { computed, ref } from 'vue'
import { useApiFetch } from '~/composables/useApiFetch'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { TenantBalanceRead, TenantBalanceUpdateRequest } from '~/types/tenant-balance'

const BALANCE_ENDPOINT = '/tenant-settings/balance'
export const USD_TO_RUB_RATE = 101

const createDefaultBalance = (): TenantBalanceRead => ({
  initial_balance_usd: '0.0000000000',
  spent_usd: '0.0000000000',
  remaining_usd: '0.0000000000',
  currency: 'USD',
  updated_at: null,
})

const toNumberSafe = (value: string | number | null | undefined): number => {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0
  if (typeof value !== 'string') return 0
  const normalized = value.trim().replace(',', '.')
  const parsed = Number.parseFloat(normalized)
  return Number.isFinite(parsed) ? parsed : 0
}

const normalizeMoneyString = (value: string): string => {
  const parsed = toNumberSafe(value)
  return parsed.toFixed(10)
}

const convertUsdToRub = (usdAmount: number): number => usdAmount * USD_TO_RUB_RATE
const convertRubToUsd = (rubAmount: number): number => rubAmount / USD_TO_RUB_RATE

const normalizeBalanceResponse = (value: Partial<TenantBalanceRead> | null | undefined): TenantBalanceRead => {
  if (!value) return createDefaultBalance()
  return {
    initial_balance_usd: normalizeMoneyString(String(value.initial_balance_usd ?? '0')),
    spent_usd: normalizeMoneyString(String(value.spent_usd ?? '0')),
    remaining_usd: normalizeMoneyString(String(value.remaining_usd ?? '0')),
    currency: String(value.currency || 'USD'),
    updated_at: value.updated_at ?? null,
  }
}

export const formatUsdAmount = (
  value: string | number | null | undefined,
  minimumFractionDigits = 2,
  maximumFractionDigits = 4,
): string => {
  const amount = toNumberSafe(value)
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(amount)
}

export const formatRubAmountFromUsd = (
  usdValue: string | number | null | undefined,
  minimumFractionDigits = 2,
  maximumFractionDigits = 2,
): string => {
  const usdAmount = toNumberSafe(usdValue)
  const rubAmount = convertUsdToRub(usdAmount)
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(rubAmount)
}

export const rubInputToUsdFixed = (rubValue: string | number): string | null => {
  if (typeof rubValue === 'string' && rubValue.trim().length === 0) return null
  const rubAmount = toNumberSafe(rubValue)
  if (!Number.isFinite(rubAmount) || rubAmount < 0) return null
  const usdAmount = convertRubToUsd(rubAmount)
  return usdAmount.toFixed(10)
}

export const usdToRubDisplayValue = (usdValue: string | number): string => {
  const rubAmount = convertUsdToRub(toNumberSafe(usdValue))
  return rubAmount.toFixed(2)
}

export const useTenantBalance = () => {
  const apiFetch = useApiFetch()

  const balance = ref<TenantBalanceRead>(createDefaultBalance())
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<string | null>(null)

  const fetchBalance = async () => {
    isLoading.value = true
    error.value = null
    try {
      const response = await apiFetch<Partial<TenantBalanceRead>>(BALANCE_ENDPOINT, {
        method: 'GET',
      })
      balance.value = normalizeBalanceResponse(response)
      return balance.value
    } catch (err: unknown) {
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить баланс организации')
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const updateInitialBalance = async (rawAmount: string) => {
    if (isSaving.value) return balance.value

    isSaving.value = true
    error.value = null
    try {
      const payload: TenantBalanceUpdateRequest = {
        initial_balance_usd: normalizeMoneyString(rawAmount),
      }
      const response = await apiFetch<Partial<TenantBalanceRead>>(BALANCE_ENDPOINT, {
        method: 'PATCH',
        body: payload,
      })
      balance.value = normalizeBalanceResponse(response)
      return balance.value
    } catch (err: unknown) {
      error.value = getReadableErrorMessage(err, 'Не удалось сохранить стартовый баланс')
      throw err
    } finally {
      isSaving.value = false
    }
  }

  const remainingUsdValue = computed(() => toNumberSafe(balance.value.remaining_usd))
  const spentUsdValue = computed(() => toNumberSafe(balance.value.spent_usd))
  const initialUsdValue = computed(() => toNumberSafe(balance.value.initial_balance_usd))

  return {
    balance,
    error,
    isLoading,
    isSaving,
    fetchBalance,
    updateInitialBalance,
    remainingUsdValue,
    spentUsdValue,
    initialUsdValue,
  }
}
