import { Component, type ReactNode } from 'react'

type ErrorBoundaryProps = {
  children: ReactNode
}

type ErrorBoundaryState = {
  error: Error | null
  errorId: string | null
}

function makeErrorId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    error: null,
    errorId: null,
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { error, errorId: makeErrorId() }
  }

  componentDidCatch(error: Error, errorInfo: unknown) {
    // Keep a console breadcrumb for debugging when DevTools is available.
    console.error('[ErrorBoundary]', this.state.errorId, error, errorInfo)
  }

  render() {
    if (!this.state.error) return this.props.children

    const message = this.state.error?.message || 'Unknown error'
    const stack = this.state.error?.stack || ''

    return (
      <div
        style={{
          minHeight: '100vh',
          padding: '2rem',
          background: '#ffffff',
          color: '#0f172a',
          fontFamily:
            'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji"',
        }}
      >
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Something went wrong</h1>
        <p style={{ marginTop: '0.75rem', color: '#475569' }}>
          Error ID: <code>{this.state.errorId}</code>
        </p>
        <p style={{ marginTop: '0.75rem' }}>
          <strong>Message:</strong> <code>{message}</code>
        </p>
        {stack && (
          <details style={{ marginTop: '1rem' }} open>
            <summary style={{ cursor: 'pointer', color: '#0f172a' }}>Stack</summary>
            <pre
              style={{
                marginTop: '0.75rem',
                padding: '0.75rem',
                background: '#0b1220',
                color: '#e2e8f0',
                borderRadius: 8,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
              }}
            >
              {stack}
            </pre>
          </details>
        )}

        <div style={{ marginTop: '1.25rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => {
              window.location.href = '/esg'
            }}
            style={{
              padding: '0.6rem 0.9rem',
              borderRadius: 8,
              border: '1px solid rgba(8, 145, 178, 0.25)',
              background: 'rgba(8, 145, 178, 0.08)',
              color: '#0e7490',
              cursor: 'pointer',
            }}
          >
            Back to dashboard
          </button>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              padding: '0.6rem 0.9rem',
              borderRadius: 8,
              border: '1px solid rgba(15, 23, 42, 0.2)',
              background: '#ffffff',
              color: '#0f172a',
              cursor: 'pointer',
            }}
          >
            Reload
          </button>
        </div>
      </div>
    )
  }
}
