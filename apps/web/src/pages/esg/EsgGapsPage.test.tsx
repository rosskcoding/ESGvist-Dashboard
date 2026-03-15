import { afterEach, beforeEach, describe, it, vi, expect } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { useAuthStore } from '@/stores/authStore'
import { EsgGapsPage } from './EsgGapsPage'

vi.mock('@/api/hooks', () => ({
  useEsgEntities: vi.fn(),
  useEsgGaps: vi.fn(),
  useEsgLocations: vi.fn(),
  useEsgSegments: vi.fn(),
}))

import { useEsgEntities, useEsgGaps, useEsgLocations, useEsgSegments } from '@/api/hooks'

let originalLocalStorage: unknown = null

function overrideLocalStorage(next: unknown) {
  try {
    Object.defineProperty(window, 'localStorage', {
      value: next,
      configurable: true,
    })
  } catch {
    const w = window as unknown as { localStorage: unknown }
    w.localStorage = next
  }
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/esg/gaps?year=2025']}>
        <EsgGapsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('EsgGapsPage', () => {
  beforeEach(() => {
    if (!originalLocalStorage) {
      originalLocalStorage = window.localStorage
    }

    const store = new Map<string, string>()
    const memStorage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, String(value))
      },
      removeItem: (key: string) => {
        store.delete(key)
      },
      clear: () => {
        store.clear()
      },
    }
    overrideLocalStorage(memStorage)

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

    vi.mocked(useEsgEntities).mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgEntities>)

    vi.mocked(useEsgLocations).mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgLocations>)

    vi.mocked(useEsgSegments).mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgSegments>)

    vi.mocked(useEsgGaps).mockReturnValue({
      data: {
        period_type: 'year',
        period_start: '2025-01-01',
        period_end: '2025-12-31',
        is_ytd: false,
        metrics_total: 2,
        metrics_with_published: 1,
        metrics_missing_published: 1,
        missing_metrics: [
          {
            metric_id: 'm1',
            code: 'M1',
            name: 'Metric 1',
            value_type: 'number',
            unit: 't',
          },
        ],
        attention_facts: [],
        issue_counts: {},
        in_review_overdue: 0,
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgGaps>)
  })

  afterEach(() => {
    if (originalLocalStorage) {
      overrideLocalStorage(originalLocalStorage)
    }
  })

  it('renders gap summary', () => {
    renderPage()

    screen.getByRole('heading', { name: 'Check gaps' })
    screen.getAllByText('Missing published metrics')
    screen.getByText('Metric 1')
    screen.getByText('M1')
  })

  it('applies saved view from localStorage', async () => {
    window.localStorage.setItem(
      'esg.gaps.saved_views.v1',
      JSON.stringify([
        {
          id: 'v1',
          name: 'FY 2024',
          filters: { year: 2024 },
        },
      ])
    )

    vi.mocked(useEsgGaps).mockImplementation(() => {
      return {
        data: {
          period_type: 'year',
          period_start: '2025-01-01',
          period_end: '2025-12-31',
          is_ytd: false,
          metrics_total: 0,
          metrics_with_published: 0,
          metrics_missing_published: 0,
          missing_metrics: [],
          attention_facts: [],
          issue_counts: {},
          in_review_overdue: 0,
        },
        isLoading: false,
        error: null,
      } as unknown as ReturnType<typeof useEsgGaps>
    })

    renderPage()

    const viewSelect = screen.getByLabelText('Saved view') as HTMLSelectElement
    fireEvent.change(viewSelect, { target: { value: 'v1' } })

    await waitFor(() => {
      const lastCall = vi.mocked(useEsgGaps).mock.calls.at(-1)?.[0]
      expect(lastCall?.periodStart).toBe('2024-01-01')
      expect(lastCall?.periodEnd).toBe('2024-12-31')
    })
  })
})
