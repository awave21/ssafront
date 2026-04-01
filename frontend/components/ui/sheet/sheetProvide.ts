import type { ComputedRef, InjectionKey } from 'vue'

export const sheetNonModalKey: InjectionKey<ComputedRef<boolean>> = Symbol('sheet-non-modal')
export const sheetOpenKey: InjectionKey<ComputedRef<boolean>> = Symbol('sheet-open')
export const sheetRequestCloseKey: InjectionKey<() => void> = Symbol('sheet-request-close')
