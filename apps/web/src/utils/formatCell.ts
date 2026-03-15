/**
 * Safe cell formatter for table previews.
 * Handles null, undefined, objects, and various data types.
 */

export type ColumnType = 'text' | 'number' | 'percent' | 'currency' | 'date'

/**
 * Format a table cell value for display.
 * 
 * @param value - The cell value (any type)
 * @param colType - Column type for formatting hints
 * @param maxLength - Maximum string length before truncation
 * @returns Formatted string safe for display
 */
export function formatCell(
  value: unknown,
  colType: ColumnType = 'text',
  maxLength = 50
): string {
  // Handle null/undefined
  if (value === null || value === undefined) {
    return '—'
  }

  // Handle objects (including arrays)
  if (typeof value === 'object') {
    try {
      const json = JSON.stringify(value)
      return json.length > maxLength ? json.slice(0, maxLength) + '…' : json
    } catch {
      return '[object]'
    }
  }

  // Convert to string
  let str = String(value)

  // Format based on column type
  switch (colType) {
    case 'number': {
      const num = Number(value)
      if (!isNaN(num)) {
        str = num.toLocaleString('ru-RU')
      }
      break
    }
    case 'percent': {
      const num = Number(value)
      if (!isNaN(num)) {
        str = `${num.toLocaleString('ru-RU')}%`
      }
      break
    }
    case 'currency': {
      const num = Number(value)
      if (!isNaN(num)) {
        str = num.toLocaleString('ru-RU', {
          minimumFractionDigits: 0,
          maximumFractionDigits: 2,
        })
      }
      break
    }
    case 'date': {
      // Try to parse as date
      if (typeof value === 'string' || typeof value === 'number') {
        const date = new Date(value)
        if (!isNaN(date.getTime())) {
          str = date.toLocaleDateString('ru-RU')
        }
      }
      break
    }
  }

  // Truncate if too long
  if (str.length > maxLength) {
    return str.slice(0, maxLength) + '…'
  }

  return str
}

/**
 * Format a number with optional unit.
 */
export function formatValue(
  value: unknown,
  unit?: string,
  decimals = 0
): string {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  const num = Number(value)
  if (isNaN(num)) {
    return String(value)
  }

  const formatted = num.toLocaleString('ru-RU', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })

  return unit ? `${formatted} ${unit}` : formatted
}




