import { beforeEach, describe, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { useAuthStore } from '@/stores/authStore'
import { EsgSnapshotPage } from './EsgSnapshotPage'

vi.mock('@/api/hooks', () => ({
  useEsgEntities: vi.fn(),
  useEsgLocations: vi.fn(),
  useEsgSegments: vi.fn(),
  useEsgSnapshot: vi.fn(),
}))

import { useEsgEntities, useEsgLocations, useEsgSegments, useEsgSnapshot } from '@/api/hooks'

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/esg/snapshot?year=2025']}>
        <EsgSnapshotPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('EsgSnapshotPage', () => {
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

    vi.mocked(useEsgSnapshot).mockReturnValue({
      data: {
        period_type: 'year',
        period_start: '2025-01-01',
        period_end: '2025-12-31',
        is_ytd: false,
        standard: 'GRI',
        generated_at_utc: '2026-02-14T00:00:00.000Z',
        snapshot_hash: 'a'.repeat(64),
        metrics_total: 1,
        facts_published: 1,
        missing_metrics: [],
        facts: [
          {
            metric: { metric_id: 'm1', code: 'M1', name: 'Metric 1', value_type: 'number', unit: 't' },
            fact: {
              fact_id: 'f1',
              company_id: 'c1',
              metric_id: 'm1',
              status: 'published',
              version_number: 1,
              supersedes_fact_id: null,
              logical_key_hash: 'b'.repeat(64),
              period_type: 'year',
              period_start: '2025-01-01',
              period_end: '2025-12-31',
              is_ytd: false,
              entity_id: null,
              location_id: null,
              segment_id: null,
              consolidation_approach: null,
              ghg_scope: null,
              scope2_method: null,
              scope3_category: null,
              tags: null,
              value_json: 123.45,
              dataset_id: null,
              dataset_revision_id: null,
              quality_json: {},
              sources_json: {},
              published_at_utc: '2026-02-14T00:00:00.000Z',
              published_by: null,
              created_by: null,
              updated_by: null,
              created_at_utc: '2026-02-14T00:00:00.000Z',
              updated_at_utc: '2026-02-14T00:00:00.000Z',
            },
          },
        ],
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgSnapshot>)
  })

  it('renders snapshot summary', () => {
    renderPage()

    screen.getByRole('heading', { name: 'Snapshot' })
    screen.getAllByText('Published facts')
    screen.getByText('Metric 1')
    screen.getByText('123.45')
  })
})
