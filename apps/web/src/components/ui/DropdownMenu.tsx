import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import styles from './DropdownMenu.module.css'

export type DropdownMenuItem =
  | {
      type?: 'item'
      label: string
      onSelect: () => void
      variant?: 'default' | 'danger'
      disabled?: boolean
      hint?: string
    }
  | {
      type: 'label'
      label: string
    }
  | { type: 'divider' }

interface DropdownMenuProps {
  triggerLabel: ReactNode
  triggerAriaLabel?: string
  items: DropdownMenuItem[]
  align?: 'start' | 'end'
  side?: 'top' | 'bottom'
}

export function DropdownMenu({
  triggerLabel,
  triggerAriaLabel,
  items,
  align = 'end',
  side = 'bottom',
}: DropdownMenuProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [coords, setCoords] = useState<{ x: number; y: number } | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false)
    }

    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as Node
      if (triggerRef.current?.contains(target)) return
      if (menuRef.current?.contains(target)) return
      setIsOpen(false)
    }

    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('mousedown', onMouseDown)

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('mousedown', onMouseDown)
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return

    const computePosition = () => {
      if (!triggerRef.current || !menuRef.current) return

      const triggerRect = triggerRef.current.getBoundingClientRect()
      const menuRect = menuRef.current.getBoundingClientRect()

      const padding = 8
      const gap = 8

      let x = align === 'end' ? triggerRect.right - menuRect.width : triggerRect.left
      let y = side === 'top' ? triggerRect.top - menuRect.height - gap : triggerRect.bottom + gap

      // Keep menu within viewport.
      x = Math.max(padding, Math.min(x, window.innerWidth - menuRect.width - padding))
      y = Math.max(padding, Math.min(y, window.innerHeight - menuRect.height - padding))

      setCoords({ x, y })
    }

    setCoords(null)
    computePosition()
    window.addEventListener('resize', computePosition)
    // capture=true catches scrolls on nested containers too.
    window.addEventListener('scroll', computePosition, true)

    // Focus first available item for keyboard users.
    const firstItem = menuRef.current?.querySelector<HTMLButtonElement>('button[data-menu-item="true"]:not(:disabled)')
    firstItem?.focus()

    return () => {
      window.removeEventListener('resize', computePosition)
      window.removeEventListener('scroll', computePosition, true)
    }
  }, [align, isOpen, side])

  const onToggle = () => {
    setIsOpen((v) => !v)
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={styles.trigger}
        aria-label={triggerAriaLabel}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        onClick={onToggle}
      >
        {triggerLabel}
      </button>
      {isOpen && (
        <div
          ref={menuRef}
          className={styles.menu}
          role="menu"
          style={{
            left: coords?.x ?? 0,
            top: coords?.y ?? 0,
            visibility: coords ? 'visible' : 'hidden',
          }}
        >
          {items.map((item, idx) => {
            if (item.type === 'divider') {
              return <div key={`divider-${idx}`} className={styles.divider} role="separator" />
            }

            if (item.type === 'label') {
              return (
                <div key={`label-${item.label}-${idx}`} className={styles.label} role="presentation">
                  {item.label}
                </div>
              )
            }

            return (
              <button
                key={`${item.label}-${idx}`}
                type="button"
                className={`${styles.item} ${item.variant === 'danger' ? styles.danger : ''}`}
                role="menuitem"
                data-menu-item="true"
                disabled={Boolean(item.disabled)}
                onClick={() => {
                  setIsOpen(false)
                  item.onSelect()
                }}
              >
                <span className={styles.itemLabel}>{item.label}</span>
                {item.hint ? <span className={styles.itemHint}>{item.hint}</span> : null}
              </button>
            )
          })}
        </div>
      )}
    </>
  )
}
