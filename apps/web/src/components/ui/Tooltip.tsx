import { useState, useRef, useEffect, ReactNode } from 'react'
import styles from './Tooltip.module.css'

type TooltipPosition = 'top' | 'bottom' | 'left' | 'right'

interface TooltipProps {
  children: ReactNode
  content: string
  position?: TooltipPosition
  delay?: number
  maxWidth?: number
}

export function Tooltip({
  children,
  content,
  position = 'top',
  delay = 300,
  maxWidth = 250,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [coords, setCoords] = useState({ x: 0, y: 0 })
  const triggerRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const timeoutRef = useRef<number | null>(null)

  const showTooltip = () => {
    timeoutRef.current = window.setTimeout(() => {
      setIsVisible(true)
    }, delay)
  }

  const hideTooltip = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    setIsVisible(false)
  }

  useEffect(() => {
    if (isVisible && triggerRef.current && tooltipRef.current) {
      const triggerRect = triggerRef.current.getBoundingClientRect()
      const tooltipRect = tooltipRef.current.getBoundingClientRect()
      
      let x = 0
      let y = 0

      switch (position) {
        case 'top':
          x = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2
          y = triggerRect.top - tooltipRect.height - 8
          break
        case 'bottom':
          x = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2
          y = triggerRect.bottom + 8
          break
        case 'left':
          x = triggerRect.left - tooltipRect.width - 8
          y = triggerRect.top + (triggerRect.height - tooltipRect.height) / 2
          break
        case 'right':
          x = triggerRect.right + 8
          y = triggerRect.top + (triggerRect.height - tooltipRect.height) / 2
          break
      }

      // Keep tooltip within viewport
      const padding = 8
      x = Math.max(padding, Math.min(x, window.innerWidth - tooltipRect.width - padding))
      y = Math.max(padding, Math.min(y, window.innerHeight - tooltipRect.height - padding))

      setCoords({ x, y })
    }
  }, [isVisible, position])

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  if (!content) {
    return <>{children}</>
  }

  return (
    <>
      <div
        ref={triggerRef}
        className={styles.trigger}
        onMouseEnter={showTooltip}
        onMouseLeave={hideTooltip}
        onFocus={showTooltip}
        onBlur={hideTooltip}
      >
        {children}
      </div>
      {isVisible && (
        <div
          ref={tooltipRef}
          className={`${styles.tooltip} ${styles[position]}`}
          style={{
            left: coords.x,
            top: coords.y,
            maxWidth,
          }}
          role="tooltip"
        >
          {content}
          <span className={styles.arrow} />
        </div>
      )}
    </>
  )
}




