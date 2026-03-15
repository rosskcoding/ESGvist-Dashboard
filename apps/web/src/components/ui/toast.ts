export type ToastType = 'success' | 'error' | 'info' | 'warning'

export interface ToastItem {
  id: string
  message: string
  type: ToastType
}

type ToastListener = (toasts: ToastItem[]) => void

let toastListeners: ToastListener[] = []
let toasts: ToastItem[] = []

function notifyListeners() {
  toastListeners.forEach((listener) => listener([...toasts]))
}

export function subscribeToToasts(listener: ToastListener) {
  toastListeners.push(listener)
  // Immediately emit current state
  listener([...toasts])

  return () => {
    toastListeners = toastListeners.filter((l) => l !== listener)
  }
}

function addToast(message: string, type: ToastType) {
  const id = Math.random().toString(36).slice(2)
  toasts = [...toasts, { id, message, type }]
  notifyListeners()
}

export const toast = {
  success: (message: string) => addToast(message, 'success'),
  error: (message: string) => addToast(message, 'error'),
  info: (message: string) => addToast(message, 'info'),
  warning: (message: string) => addToast(message, 'warning'),
  remove: (id: string) => {
    toasts = toasts.filter((t) => t.id !== id)
    notifyListeners()
  },
}


