export type ApiKey = {
  id: string
  name: string
  tenant_id: string
  user_id: string
  agent_id: string | null
  last4: string
  scopes: string[]
  expires_at: string | null
  total_calls: number
  daily_limit: number | null
  created_at: string
  revoked_at: string | null
  last_used_at: string | null
}

export type ApiKeyCreated = ApiKey & {
  api_key: string
}

export type ApiKeyStatus = 'active' | 'expired' | 'revoked'

export const getApiKeyStatus = (key: ApiKey): ApiKeyStatus => {
  if (key.revoked_at) return 'revoked'
  if (key.expires_at && new Date(key.expires_at) <= new Date()) return 'expired'
  return 'active'
}

export type CreateApiKeyPayload = {
  name: string
  agent_id: string
  expires_in_days?: number | null
  daily_limit?: number | null
}

export type UpdateApiKeyPayload = {
  name?: string
  daily_limit?: number | null
  expires_in_days?: number | null
}
