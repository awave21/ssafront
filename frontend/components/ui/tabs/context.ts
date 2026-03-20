import type { Ref } from 'vue'

export interface TabsContext {
  value: Ref<string>
  setValue: (value: string) => void
}

export const tabsContextKey = Symbol('tabs-context')
