import { ref } from 'vue'

export type ToastVariant = 'default' | 'destructive' | 'success' | 'info'

export type Toast = {
  id: string
  title?: string
  description?: string
  variant?: ToastVariant
  duration?: number
}

// Глобальное состояние для toast
const toasts = ref<Toast[]>([])
let toastIdCounter = 0

export const useToast = () => {
  const addToast = (toast: Omit<Toast, 'id'>): string => {
    const id = `toast-${++toastIdCounter}`
    const newToast: Toast = {
      id,
      duration: 5000,
      ...toast,
    }
    
    toasts.value.push(newToast)
    
    if (newToast.duration && newToast.duration > 0) {
      setTimeout(() => {
        removeToast(id)
      }, newToast.duration)
    }
    
    return id
  }

  const removeToast = (id: string) => {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index > -1) {
      toasts.value.splice(index, 1)
    }
  }

  const toast = (options: Omit<Toast, 'id'>) => {
    return addToast(options)
  }

  const success = (title: string, description?: string) => {
    return addToast({ title, description, variant: 'success' })
  }

  const error = (title: string, description?: string) => {
    return addToast({ title, description, variant: 'destructive' })
  }

  const info = (title: string, description?: string) => {
    return addToast({ title, description, variant: 'info' })
  }

  return {
    toasts,
    toast,
    success,
    error,
    info,
    removeToast,
  }
}