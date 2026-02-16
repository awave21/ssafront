export const AUTH_TYPES = {
  api_key: 'API Key',
  bearer_token: 'Bearer Token',
  basic_auth: 'Basic Auth',
  custom_header: 'Custom Header',
  query_param: 'Query Parameter',
  none: 'Без авторизации',
} as const

export type CredentialAuthType = keyof typeof AUTH_TYPES

export type CredentialConfig =
  | { header: string; value: string }         // api_key, custom_header
  | { token: string }                          // bearer_token
  | { username: string; password: string }     // basic_auth
  | { param: string; value: string }           // query_param
  | Record<string, never>                      // none

export type Credential = {
  id: string
  name: string
  auth_type: CredentialAuthType
  config: CredentialConfig
  created_at?: string
  updated_at?: string
}

export type CredentialCreate = {
  name: string
  auth_type: CredentialAuthType
  config: CredentialConfig
}

export type CredentialUpdate = Partial<CredentialCreate>

export type CredentialTestResult = {
  success: boolean
  status_code?: number
  message?: string
}

/**
 * Returns the config fields needed for each auth_type
 */
export const getConfigFieldsForAuthType = (authType: CredentialAuthType): string[] => {
  switch (authType) {
    case 'api_key':
      return ['header', 'value']
    case 'bearer_token':
      return ['token']
    case 'basic_auth':
      return ['username', 'password']
    case 'custom_header':
      return ['header', 'value']
    case 'query_param':
      return ['param', 'value']
    case 'none':
      return []
  }
}

/**
 * Returns labels for config fields by auth_type
 */
export const getConfigFieldLabels = (authType: CredentialAuthType): Record<string, string> => {
  switch (authType) {
    case 'api_key':
      return { header: 'Имя заголовка (напр. apikey, X-API-Key)', value: 'Значение ключа' }
    case 'bearer_token':
      return { token: 'Bearer токен' }
    case 'basic_auth':
      return { username: 'Имя пользователя', password: 'Пароль' }
    case 'custom_header':
      return { header: 'Имя заголовка', value: 'Значение' }
    case 'query_param':
      return { param: 'Имя параметра', value: 'Значение' }
    case 'none':
      return {}
  }
}

/**
 * Returns placeholder values for config fields
 */
export const getConfigFieldPlaceholders = (authType: CredentialAuthType): Record<string, string> => {
  switch (authType) {
    case 'api_key':
      return { header: 'apikey', value: 'eyJhbGciOiJIUzI1NiIs...' }
    case 'bearer_token':
      return { token: 'eyJhbGciOiJIUzI1NiIs...' }
    case 'basic_auth':
      return { username: 'admin', password: '••••••••' }
    case 'custom_header':
      return { header: 'X-Custom-Auth', value: 'secret-value' }
    case 'query_param':
      return { param: 'api_key', value: 'your-api-key' }
    case 'none':
      return {}
  }
}

/**
 * Returns which config fields should use password input type
 */
export const getSecretFields = (authType: CredentialAuthType): Set<string> => {
  switch (authType) {
    case 'api_key':
      return new Set(['value'])
    case 'bearer_token':
      return new Set(['token'])
    case 'basic_auth':
      return new Set(['password'])
    case 'custom_header':
      return new Set(['value'])
    case 'query_param':
      return new Set(['value'])
    case 'none':
      return new Set()
  }
}

/**
 * Creates an empty config for the given auth_type
 */
export const createEmptyConfig = (authType: CredentialAuthType): CredentialConfig => {
  switch (authType) {
    case 'api_key':
      return { header: '', value: '' }
    case 'bearer_token':
      return { token: '' }
    case 'basic_auth':
      return { username: '', password: '' }
    case 'custom_header':
      return { header: '', value: '' }
    case 'query_param':
      return { param: '', value: '' }
    case 'none':
      return {} as Record<string, never>
  }
}
