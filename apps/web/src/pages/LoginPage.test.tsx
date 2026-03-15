import { describe, it, expect, beforeEach, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { useAuthStore } from '@/stores/authStore'
import { LoginPage } from './LoginPage'
import { apiClient } from '@/api/client'

// Mock the API client
vi.mock('@/api/client', () => ({
  apiClient: {
    post: vi.fn(),
  },
}))

describe('LoginPage', () => {
  beforeEach(() => {
    // Ensure deterministic state across runs
    useAuthStore.getState().logout()
    vi.clearAllMocks()
  })

  it('renders and supports demo login', async () => {
    // Mock successful API response
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        access_token: 'test-token',
        token_type: 'bearer',
        expires_in: 1800,
        user: {
          user_id: 'test-user-id',
          email: 'e2e-test@example.com',
          full_name: 'E2E Test User',
          is_active: true,
          is_superuser: false,
          companies: [],
        },
      },
      status: 200,
      headers: {},
    })

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    // Basic smoke: header is visible
    screen.getByRole('heading', { name: 'Platform' })

    // Demo login calls the API with test credentials
    fireEvent.click(screen.getByRole('button', { name: /Demo Login/i }))

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(true)
    })
    
    expect(useAuthStore.getState().user?.email).toBe('e2e-test@example.com')
    expect(useAuthStore.getState().accessToken).toBe('test-token')
    // Refresh token is set as httpOnly cookie by backend (not in response body)
    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/v1/auth/login',
      {
        email: 'e2e-test@example.com',
        password: 'TestPassword123!',
      },
      { credentials: 'include' }
    )
  })
})
