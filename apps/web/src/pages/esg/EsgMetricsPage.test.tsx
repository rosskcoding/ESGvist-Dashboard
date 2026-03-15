import { describe, it, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { useAuthStore } from '@/stores/authStore'
import { apiClient } from '@/api/client'
import { EsgMetricsPage } from './EsgMetricsPage'

vi.mock('@/api/hooks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/hooks')>()
  return {
    ...actual,
    // Ensure non-enumerable ESM namespace exports are present on the mock module shape.
    queryKeys: actual.queryKeys,
    useCreateEsgMetric: vi.fn(),
    useUpdateEsgMetric: vi.fn(),
    useDeleteEsgMetric: vi.fn(),
  }
})

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiClient: {
      get: vi.fn(),
    },
  }
})

import { useCreateEsgMetric, useDeleteEsgMetric, useUpdateEsgMetric } from '@/api/hooks'

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/esg/metrics']}>
        <EsgMetricsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('EsgMetricsPage', () => {
  beforeEach(() => {
    useAuthStore.setState({
      accessToken: 'test-token',
      user: {
        userId: 'test-user-id',
        email: 'test@example.com',
        fullName: 'Test User',
        isSuperuser: false,
        memberships: [],
      },
      isAuthenticated: true,
      _hasHydrated: true,
    })

    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        items: [],
        total: 0,
        page: 1,
        page_size: 100,
        total_pages: 1,
        has_next: false,
        has_prev: false,
      },
      status: 200,
      headers: {},
    })

    vi.mocked(useCreateEsgMetric).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCreateEsgMetric>)

    vi.mocked(useUpdateEsgMetric).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateEsgMetric>)

    vi.mocked(useDeleteEsgMetric).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useDeleteEsgMetric>)
  })

  it('renders empty state', async () => {
    renderPage()

    screen.getByRole('heading', { name: 'Metrics' })
    screen.getByRole('button', { name: '+ New metric' })
    await screen.findByText('No metrics yet.')
  })
})
