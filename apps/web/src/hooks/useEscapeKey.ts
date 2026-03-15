import { useEffect, useCallback } from 'react'

/**
 * Hook to handle ESC key press for closing modals, panels, overlays
 * @param isOpen - Whether the element is currently open/visible
 * @param onClose - Callback to close the element
 */
export function useEscapeKey(isOpen: boolean, onClose: () => void) {
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
    }
    return () => {
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen, handleEscape])
}




