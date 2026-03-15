import { Button } from './Button'
import { useTranslation } from 'react-i18next'
import styles from './ConfirmDialog.module.css'

interface ConfirmDialogProps {
  isOpen: boolean
  title?: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  confirmLoading?: boolean
  onConfirm: () => void
  onCancel: () => void
  variant?: 'danger' | 'warning' | 'info'
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = 'OK',
  cancelLabel,
  confirmLoading = false,
  onConfirm,
  onCancel,
  variant = 'danger',
}: ConfirmDialogProps) {
  const { t } = useTranslation('ui')
  if (!isOpen) return null

  const resolvedTitle = title ?? t('confirmDialog.title')
  const resolvedCancelLabel = cancelLabel ?? t('confirmDialog.cancel')

  const handleCancel = () => {
    if (confirmLoading) return
    onCancel()
  }

  return (
    <div className={styles.overlay} onClick={handleCancel}>
      <div
        className={styles.dialog}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <h3 className={styles.title}>{resolvedTitle}</h3>
        </div>
        <div className={styles.body}>
          <p className={styles.message}>{message}</p>
        </div>
        <div className={styles.footer}>
          <Button
            variant="secondary"
            onClick={handleCancel}
            type="button"
            disabled={confirmLoading}
          >
            {resolvedCancelLabel}
          </Button>
          <Button
            variant={variant === 'danger' ? 'danger' : 'primary'}
            onClick={onConfirm}
            type="button"
            loading={confirmLoading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
