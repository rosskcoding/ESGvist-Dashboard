import { useEffect, useCallback, useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import styles from './Modal.module.css'
import { IconX } from './Icons'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl'
}

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  size = 'md',
}: ModalProps) {
  const { t } = useTranslation('ui')
  // Track where mousedown started to avoid closing on text selection drag.
  const mouseDownTarget = useRef<EventTarget | null>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    },
    [onClose]
  )

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      document.body.style.overflow = 'hidden'
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = ''
    }
  }, [isOpen, handleEscape])

  const handleMouseDown = (e: React.MouseEvent) => {
    mouseDownTarget.current = e.target
  }

  const handleOverlayClick = (e: React.MouseEvent) => {
    // Close only when both mousedown and click happened on the overlay.
    if (
      e.target === overlayRef.current &&
      mouseDownTarget.current === overlayRef.current
    ) {
      onClose()
    }
    mouseDownTarget.current = null
  }

  if (!isOpen) return null

  return (
    <div
      ref={overlayRef}
      className={styles.overlay}
      onMouseDown={handleMouseDown}
      onClick={handleOverlayClick}
    >
      <div
        className={`${styles.modal} ${styles[size]}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <h2 className={styles.title}>{title}</h2>
          <button
            className={styles.closeBtn}
            onClick={onClose}
            aria-label={t('modal.closeAria')}
          >
            <IconX size={18} />
          </button>
        </div>
        <div className={styles.content}>{children}</div>
      </div>
    </div>
  )
}

