import {
  forwardRef,
  useEffect,
  useId,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type SelectHTMLAttributes,
} from 'react'
import type React from 'react'
import clsx from 'clsx'
import styles from './Select.module.css'

interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label?: string
  error?: string
  options: SelectOption[]
  placeholder?: string
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      label,
      error,
      options,
      placeholder,
      className,
      id,
      value,
      defaultValue,
      disabled,
      onChange,
      onBlur,
      onFocus,
      name,
      required,
      title,
      'aria-label': ariaLabel,
      ...props
    },
    ref
  ) => {
    const generatedId = useId()
    const selectId = id || `${label?.toLowerCase().replace(/\s+/g, '-') || 'select'}-${generatedId}`
    const nativeSelectId = `${selectId}-native`
    const labelId = `${selectId}-label`

    const nativeRef = useRef<HTMLSelectElement | null>(null)
    const wrapperRef = useRef<HTMLDivElement | null>(null)
    const triggerRef = useRef<HTMLButtonElement | null>(null)
    const menuRef = useRef<HTMLDivElement | null>(null)

    useImperativeHandle(ref, () => nativeRef.current as HTMLSelectElement)

    const isControlled = value !== undefined
    const initialValue = useMemo(() => {
      if (defaultValue !== undefined && defaultValue !== null) return String(defaultValue)
      if (placeholder) return ''
      return options[0]?.value ?? ''
    }, [defaultValue, options, placeholder])

    const [internalValue, setInternalValue] = useState<string>(initialValue)
    const [isOpen, setIsOpen] = useState(false)

    useEffect(() => {
      if (isControlled) return
      const hasCurrentValue = options.some((option) => option.value === internalValue)
      if (hasCurrentValue) return
      if (placeholder) {
        setInternalValue('')
        return
      }
      setInternalValue(options[0]?.value ?? '')
    }, [internalValue, isControlled, options, placeholder])

    const selectedValue = isControlled
      ? String(value ?? (placeholder ? '' : options[0]?.value ?? ''))
      : internalValue

    const selectedOption = options.find((option) => option.value === selectedValue)
    const selectedIndex = options.findIndex((option) => option.value === selectedValue)

    const triggerText = selectedOption?.label ?? placeholder ?? options[0]?.label ?? ''

    useEffect(() => {
      if (!isOpen) return

      const closeOnOutsideClick = (event: MouseEvent) => {
        const target = event.target as Node
        if (wrapperRef.current?.contains(target)) return
        setIsOpen(false)
      }

      const closeOnEscape = (event: KeyboardEvent) => {
        if (event.key !== 'Escape') return
        setIsOpen(false)
        triggerRef.current?.focus()
      }

      document.addEventListener('mousedown', closeOnOutsideClick)
      document.addEventListener('keydown', closeOnEscape)
      return () => {
        document.removeEventListener('mousedown', closeOnOutsideClick)
        document.removeEventListener('keydown', closeOnEscape)
      }
    }, [isOpen])

    const focusOptionAt = (index: number) => {
      const menu = menuRef.current
      if (!menu) return
      const enabledOptions = Array.from(
        menu.querySelectorAll<HTMLButtonElement>('button[data-select-option="true"]:not(:disabled)')
      )
      if (enabledOptions.length === 0) return
      const nextIndex = Math.max(0, Math.min(index, enabledOptions.length - 1))
      enabledOptions[nextIndex]?.focus()
    }

    const openMenuAndFocus = (index?: number) => {
      if (disabled || options.length === 0) return
      setIsOpen(true)
      requestAnimationFrame(() => {
        const fallbackIndex = selectedIndex >= 0 ? selectedIndex : 0
        focusOptionAt(index ?? fallbackIndex)
      })
    }

    const emitChange = (nextValue: string) => {
      if (!onChange) return
      const syntheticEvent = {
        target: { value: nextValue, name: name || '', id: selectId },
        currentTarget: { value: nextValue, name: name || '', id: selectId },
      } as unknown as React.ChangeEvent<HTMLSelectElement>
      onChange(syntheticEvent)
    }

    const handleSelect = (nextValue: string) => {
      setIsOpen(false)
      if (nextValue === selectedValue) {
        triggerRef.current?.focus()
        return
      }
      if (!isControlled) setInternalValue(nextValue)
      emitChange(nextValue)
      triggerRef.current?.focus()
    }

    return (
      <div className={styles.field}>
        {label && (
          <label id={labelId} htmlFor={nativeSelectId} className={styles.label}>
            {label}
          </label>
        )}
        <div ref={wrapperRef} className={styles.wrapper}>
          <select
            ref={nativeRef}
            id={nativeSelectId}
            tabIndex={-1}
            aria-hidden="true"
            className={styles.native}
            value={selectedValue}
            onChange={(event) => {
              handleSelect(event.target.value)
            }}
            disabled={disabled}
            name={name}
            required={required}
            {...props}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {options.map((option) => (
              <option key={option.value} value={option.value} disabled={option.disabled}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            ref={triggerRef}
            type="button"
            id={selectId}
            title={title}
            aria-label={ariaLabel}
            aria-haspopup="listbox"
            aria-expanded={isOpen}
            aria-controls={`${selectId}-listbox`}
            role="combobox"
            value={selectedValue}
            disabled={disabled}
            className={clsx(styles.select, error && styles.error, className)}
            onClick={() => {
              if (isOpen) {
                setIsOpen(false)
                return
              }
              openMenuAndFocus()
            }}
            onKeyDown={(event) => {
              if (event.key === 'ArrowDown') {
                event.preventDefault()
                openMenuAndFocus(selectedIndex >= 0 ? selectedIndex : 0)
                return
              }
              if (event.key === 'ArrowUp') {
                event.preventDefault()
                openMenuAndFocus(selectedIndex >= 0 ? selectedIndex : Math.max(options.length - 1, 0))
                return
              }
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                openMenuAndFocus()
              }
            }}
            onBlur={(event) => {
              onBlur?.(event as unknown as React.FocusEvent<HTMLSelectElement>)
            }}
            onFocus={(event) => {
              onFocus?.(event as unknown as React.FocusEvent<HTMLSelectElement>)
            }}
          >
            <span className={styles.value}>{triggerText}</span>
          </button>
          <span className={`${styles.arrow} ${isOpen ? styles.arrowOpen : ''}`} />
          {isOpen && options.length > 0 && (
            <div ref={menuRef} id={`${selectId}-listbox`} className={styles.menu} role="listbox" aria-label={ariaLabel}>
              {options.map((option, index) => {
                const isSelected = option.value === selectedValue
                return (
                  <button
                    key={option.value}
                    type="button"
                    role="option"
                    data-select-option="true"
                    aria-selected={isSelected}
                    disabled={Boolean(option.disabled)}
                    className={`${styles.option} ${isSelected ? styles.optionActive : ''}`}
                    onClick={() => handleSelect(option.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'ArrowDown') {
                        event.preventDefault()
                        focusOptionAt(index + 1)
                        return
                      }
                      if (event.key === 'ArrowUp') {
                        event.preventDefault()
                        focusOptionAt(index - 1)
                        return
                      }
                      if (event.key === 'Home') {
                        event.preventDefault()
                        focusOptionAt(0)
                        return
                      }
                      if (event.key === 'End') {
                        event.preventDefault()
                        focusOptionAt(options.length - 1)
                        return
                      }
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        handleSelect(option.value)
                        return
                      }
                      if (event.key === 'Escape') {
                        event.preventDefault()
                        setIsOpen(false)
                        triggerRef.current?.focus()
                      }
                    }}
                  >
                    <span className={styles.optionCheck} aria-hidden="true">
                      {isSelected ? 'v' : ''}
                    </span>
                    <span className={styles.optionLabel}>{option.label}</span>
                  </button>
                )
              })}
            </div>
          )}
        </div>
        {error && <span className={styles.errorText}>{error}</span>}
      </div>
    )
  }
)

Select.displayName = 'Select'
