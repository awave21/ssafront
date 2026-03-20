export type TenantBalanceRead = {
  initial_balance_usd: string
  spent_usd: string
  remaining_usd: string
  currency: 'USD' | string
  updated_at: string | null
}

export type TenantBalanceUpdateRequest = {
  initial_balance_usd: string
}
