export type TenantLLMConfigSet = {
  api_key: string
  provider?: string
}

export type TenantLLMConfigRead = {
  id: string
  tenant_id: string
  provider: string
  last4: string
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export type TenantLLMConfigStatus = {
  has_key: boolean
  provider: string
  last4: string | null
  is_active: boolean
}
