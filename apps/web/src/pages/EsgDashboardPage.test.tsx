import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { useAuthStore } from '@/stores/authStore'
import { EsgDashboardPage } from './EsgDashboardPage'

vi.mock('@/api/hooks', () => ({
  useEsgFacts: vi.fn(),
  useEsgGaps: vi.fn(),
  useEsgMetrics: vi.fn(),
}))

import { useEsgFacts, useEsgGaps, useEsgMetrics } from '@/api/hooks'

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/esg?year=2025&standard=GRI']}>
        <EsgDashboardPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('EsgDashboardPage', () => {
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

    vi.mocked(useEsgMetrics).mockImplementation((params) => {
      if (params?.includeInactive) {
        return {
          data: { items: [], total: 128 },
          isLoading: false,
          error: null,
        } as unknown as ReturnType<typeof useEsgMetrics>
      }
      return {
        data: { items: [], total: 120 },
        isLoading: false,
        error: null,
      } as unknown as ReturnType<typeof useEsgMetrics>
    })

    vi.mocked(useEsgFacts).mockImplementation((params) => {
      if (params?.status === 'published') {
        return {
          data: { items: [], total: 3100 },
          isLoading: false,
          error: null,
        } as unknown as ReturnType<typeof useEsgFacts>
      }
      if (params?.status === 'in_review') {
        return {
          data: { items: [], total: 30 },
          isLoading: false,
          error: null,
        } as unknown as ReturnType<typeof useEsgFacts>
      }
      if (params?.status === 'draft') {
        return {
          data: { items: [], total: 1220 },
          isLoading: false,
          error: null,
        } as unknown as ReturnType<typeof useEsgFacts>
      }
      return {
        data: { items: [], total: 4320 },
        isLoading: false,
        error: null,
      } as unknown as ReturnType<typeof useEsgFacts>
    })

    vi.mocked(useEsgGaps).mockReturnValue({
      data: {
        period_type: 'year',
        period_start: '2025-01-01',
        period_end: '2025-12-31',
        is_ytd: false,
        standard: 'GRI',
        metrics_total: 20,
        metrics_with_published: 15,
        metrics_missing_published: 5,
        missing_metrics: [],
        attention_facts: [
          {
            fact_id: 'fact-1',
            metric: { metric_id: 'm1', code: 'E-1', name: 'Test metric 1', value_type: 'number', unit: 't' },
            logical_key_hash: 'lk-1',
            status: 'draft',
            updated_at_utc: '2025-02-01T00:00:00Z',
            issues: [{ code: 'missing_evidence', message: 'Missing evidence' }],
          },
          {
            fact_id: 'fact-2',
            metric: { metric_id: 'm2', code: 'E-2', name: 'Test metric 2', value_type: 'number', unit: 't' },
            logical_key_hash: 'lk-2',
            status: 'in_review',
            updated_at_utc: '2025-02-02T00:00:00Z',
            issues: [{ code: 'missing_source:source', message: 'Missing source' }],
          },
        ],
        issue_counts: {
          'missing_evidence': 8,
          'missing_source:source': 3,
          'range_above_max': 2,
          'review_overdue': 2,
        },
        in_review_overdue: 2,
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgGaps>)
  })

  it('renders quick overview with counters', () => {
    renderPage()

    screen.getByRole('heading', { name: 'Workspace' })
    screen.getByText('Data coverage')
    screen.getByText('Publish readiness')
    screen.getByText('Evidence coverage')
    screen.getByText('Risks & blockers')
    screen.getByRole('link', { name: 'Overdue reviews' })
    screen.getByText('Report snapshot')

    screen.getByText('75%')
    screen.getByText('15 / 20 metrics published (5 missing)')
    screen.getByText('Published 3,100 · In review 30 · Draft 1,220 · Missing 5')
    screen.getByText('Missing evidence 8 · Missing sources 3')
    within(screen.getByRole('link', { name: 'Risks & blockers' })).getByText('13')

    const gapsCall = vi.mocked(useEsgGaps).mock.calls[0]?.[0]
    expect(gapsCall?.standard).toBe('GRI')
    expect(gapsCall?.periodStart).toBe('2025-01-01')
    expect(gapsCall?.periodEnd).toBe('2025-12-31')
    expect(gapsCall?.reviewOverdueDays).toBe(7)

    screen.getByText("Today's work")
    screen.getByText('Missing published value (5)')
    screen.getByText('Overdue reviews (2)')
    screen.getByText('Missing evidence (8)')
    screen.getByText('Out of range (2)')
    screen.getByText('Missing sources (3)')
  })
})
