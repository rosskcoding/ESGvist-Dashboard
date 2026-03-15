import { useCallback } from 'react';
import styles from './EditorModeSwitch.module.css';

export type EditorMode = 'simple' | 'advanced';

interface EditorModeSwitchProps {
  mode: EditorMode;
  onChange: (mode: EditorMode) => void;
  disabled?: boolean;
  showHint?: boolean;
}

/**
 * Segmented control for switching between Simple and Advanced editor modes.
 * 
 * Simple mode: Covers 80% of use cases with streamlined UI
 * Advanced mode: Full access to all schema fields
 */
export function EditorModeSwitch({
  mode,
  onChange,
  disabled = false,
  showHint = true,
}: EditorModeSwitchProps) {
  const handleModeChange = useCallback((newMode: EditorMode) => {
    if (!disabled && newMode !== mode) {
      onChange(newMode);
    }
  }, [mode, onChange, disabled]);

  return (
    <div className={styles.container}>
      <div className={`${styles.switchWrapper} ${disabled ? styles.disabled : ''}`}>
        <button
          type="button"
          className={`${styles.option} ${mode === 'simple' ? styles.active : ''}`}
          onClick={() => handleModeChange('simple')}
          disabled={disabled}
          aria-pressed={mode === 'simple'}
        >
          <svg
            className={styles.icon}
            viewBox="0 0 20 20"
            fill="currentColor"
            width="16"
            height="16"
          >
            <path
              fillRule="evenodd"
              d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z"
              clipRule="evenodd"
            />
          </svg>
          Simple
        </button>
        
        <button
          type="button"
          className={`${styles.option} ${mode === 'advanced' ? styles.active : ''}`}
          onClick={() => handleModeChange('advanced')}
          disabled={disabled}
          aria-pressed={mode === 'advanced'}
        >
          <svg
            className={styles.icon}
            viewBox="0 0 20 20"
            fill="currentColor"
            width="16"
            height="16"
          >
            <path
              fillRule="evenodd"
              d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z"
              clipRule="evenodd"
            />
          </svg>
          Advanced
        </button>
        
        <div
          className={styles.slider}
          style={{
            transform: mode === 'advanced' ? 'translateX(100%)' : 'translateX(0)',
          }}
        />
      </div>
      
      {showHint && mode === 'advanced' && (
        <div className={styles.hint}>
          <svg
            className={styles.hintIcon}
            viewBox="0 0 20 20"
            fill="currentColor"
            width="14"
            height="14"
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
              clipRule="evenodd"
            />
          </svg>
          Advanced mode shows all parameters. Recommended for complex configurations.
        </div>
      )}
    </div>
  );
}

export default EditorModeSwitch;

