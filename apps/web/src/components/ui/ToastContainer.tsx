import { useEffect, useState } from 'react'
import styles from './Toast.module.css'
import { IconAlertTriangle, IconCheck, IconInfo, IconX } from './Icons'

import {
  subscribeToToasts,
  toast,
  type ToastItem as ToastItemType,
  type ToastType,
} from './toast'

interface ToastProps {
  message: string
  type: ToastType
  onClose: () => void
  duration?: number
}

function ToastItem({ message, type, onClose, duration = 4000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, duration)
    return () => clearTimeout(timer)
  }, [onClose, duration])

  const icons: Record<ToastType, React.ReactNode> = {
    success: <IconCheck size={18} />,
    error: <IconX size={18} />,
    info: <IconInfo size={18} />,
    warning: <IconAlertTriangle size={18} />,
  }

  return (
    <div className={`${styles.toast} ${styles[type]}`}>
      <span className={styles.icon}>{icons[type]}</span>
      <span className={styles.message}>{message}</span>
      <button onClick={onClose} className={styles.close}>
        <IconX size={16} />
      </button>
    </div>
  )
}

export function ToastContainer() {
  const [items, setItems] = useState<ToastItemType[]>([])

  useEffect(() => {
    return subscribeToToasts((newToasts) => setItems(newToasts))
  }, [])

  if (items.length === 0) return null

  return (
    <div className={styles.container}>
      {items.map((item) => (
        <ToastItem
          key={item.id}
          message={item.message}
          type={item.type}
          onClose={() => toast.remove(item.id)}
        />
      ))}
    </div>
  )
}
