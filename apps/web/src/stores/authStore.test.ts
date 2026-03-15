import { describe, it, expect, beforeEach, vi } from 'vitest'

class MemoryStorage implements Storage {
  private data = new Map<string, string>()

  get length() {
    return this.data.size
  }

  clear(): void {
    this.data.clear()
  }

  getItem(key: string): string | null {
    return this.data.has(key) ? this.data.get(key)! : null
  }

  key(index: number): string | null {
    const keys = Array.from(this.data.keys())
    return keys[index] ?? null
  }

  removeItem(key: string): void {
    this.data.delete(key)
  }

  setItem(key: string, value: string): void {
    this.data.set(key, value)
  }
}

describe('authStore persistence security', () => {
  beforeEach(() => {
    // Ensure a clean module state so authStore re-evaluates canUseWebStorage().
    vi.resetModules()
  })

  it('does not persist accessToken or refreshToken in localStorage', async () => {
    // Node.js v25 ships an experimental `globalThis.localStorage` stub unless started
    // with `--localstorage-file`. Provide a deterministic in-memory Storage for tests.
    const storage = new MemoryStorage()
    Object.defineProperty(window, 'localStorage', {
      value: storage,
      configurable: true,
    })

    const { useAuthStore } = await import('./authStore')

    useAuthStore.getState().login(
      {
        userId: 'u1',
        email: 'user@example.com',
        fullName: 'User',
        isSuperuser: false,
        memberships: [],
      },
      'access-token'
    )

    const raw = storage.getItem('auth-storage')
    expect(raw).toBeTruthy()

    // Persisted payload should NOT contain tokens (XSS hardening).
    expect(raw).not.toContain('accessToken')
    expect(raw).not.toContain('refreshToken')

    // But should contain user info / auth flag for UI.
    expect(raw).toContain('isAuthenticated')
    expect(raw).toContain('user')
  })
})


