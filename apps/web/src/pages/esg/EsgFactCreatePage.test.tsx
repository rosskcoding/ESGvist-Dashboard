import { describe, it, beforeEach, vi, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { useAuthStore } from '@/stores/authStore'
import { EsgFactCreatePage } from './EsgFactCreatePage'

vi.mock('@/api/hooks', () => ({
  getAssetSignedUrl: vi.fn(),
  useCreateEsgFact: vi.fn(),
  useCreateEsgFactEvidence: vi.fn(),
  useDeleteEsgFactEvidence: vi.fn(),
  useEsgEntities: vi.fn(),
  useEsgFactEvidence: vi.fn(),
  useEsgLocations: vi.fn(),
  useEsgMetrics: vi.fn(),
  useEsgSegments: vi.fn(),
  useUploadAsset: vi.fn(),
}))

import {
  getAssetSignedUrl,
  useCreateEsgFact,
  useCreateEsgFactEvidence,
  useDeleteEsgFactEvidence,
  useEsgEntities,
  useEsgFactEvidence,
  useEsgLocations,
  useEsgMetrics,
  useEsgSegments,
  useUploadAsset,
} from '@/api/hooks'

function renderPage(path = '/esg/facts/new') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <EsgFactCreatePage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('EsgFactCreatePage', () => {
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

    vi.mocked(useEsgMetrics).mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgMetrics>)

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

    vi.mocked(useCreateEsgFact).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCreateEsgFact>)

    vi.mocked(useEsgFactEvidence).mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgFactEvidence>)

    vi.mocked(useCreateEsgFactEvidence).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCreateEsgFactEvidence>)

    vi.mocked(useDeleteEsgFactEvidence).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useDeleteEsgFactEvidence>)

    vi.mocked(useUploadAsset).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useUploadAsset>)

    vi.mocked(getAssetSignedUrl).mockResolvedValue('https://example.com/signed-url')
  })

  it('renders form shell', () => {
    renderPage()

    screen.getByRole('heading', { name: 'New fact' })
    screen.getByRole('button', { name: 'Create draft fact' })
    screen.getByRole('button', { name: 'Back to facts' })
  })

  it('prefills metric, period, and context from query params', () => {
    vi.mocked(useEsgMetrics).mockReturnValue({
      data: {
        items: [
          {
            metric_id: 'm1',
            company_id: 'c1',
            code: 'M1',
            name: 'Metric 1',
            description: null,
            value_type: 'number',
            unit: 't',
            value_schema_json: {},
            is_active: true,
            created_by: null,
            updated_by: null,
            created_at_utc: '2026-01-01T00:00:00Z',
            updated_at_utc: '2026-01-01T00:00:00Z',
          },
        ],
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgMetrics>)

    vi.mocked(useEsgEntities).mockReturnValue({
      data: {
        items: [
          {
            entity_id: 'e1',
            company_id: 'c1',
            code: null,
            name: 'Entity 1',
            description: null,
            is_active: true,
            created_by: null,
            created_at_utc: '2026-01-01T00:00:00Z',
            updated_at_utc: '2026-01-01T00:00:00Z',
          },
        ],
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgEntities>)

    vi.mocked(useEsgLocations).mockReturnValue({
      data: {
        items: [
          {
            location_id: 'l1',
            company_id: 'c1',
            code: null,
            name: 'Location 1',
            description: null,
            is_active: true,
            created_by: null,
            created_at_utc: '2026-01-01T00:00:00Z',
            updated_at_utc: '2026-01-01T00:00:00Z',
          },
        ],
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgLocations>)

    vi.mocked(useEsgSegments).mockReturnValue({
      data: {
        items: [
          {
            segment_id: 's1',
            company_id: 'c1',
            code: null,
            name: 'Segment 1',
            description: null,
            is_active: true,
            created_by: null,
            created_at_utc: '2026-01-01T00:00:00Z',
            updated_at_utc: '2026-01-01T00:00:00Z',
          },
        ],
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgSegments>)

    renderPage('/esg/facts/new?metric_id=m1&year=2025&entity_id=e1&location_id=l1&segment_id=s1')

    const metricSelect = screen.getByLabelText('Metric') as HTMLSelectElement
    const entitySelect = screen.getByLabelText('Entity') as HTMLSelectElement
    const locationSelect = screen.getByLabelText('Location') as HTMLSelectElement
    const segmentSelect = screen.getByLabelText('Segment') as HTMLSelectElement
    const start = screen.getByLabelText('Start date') as HTMLInputElement
    const end = screen.getByLabelText('End date') as HTMLInputElement

    expect(metricSelect.value).toBe('m1')
    expect(entitySelect.value).toBe('e1')
    expect(locationSelect.value).toBe('l1')
    expect(segmentSelect.value).toBe('s1')
    expect(start.value).toBe('2025-01-01')
    expect(end.value).toBe('2025-12-31')
  })

  it('renders schema-driven required sources inputs from value_schema_json', () => {
    vi.mocked(useEsgMetrics).mockReturnValue({
      data: {
        items: [
          {
            metric_id: 'm1',
            company_id: 'c1',
            code: 'M1',
            name: 'Metric 1',
            description: null,
            value_type: 'number',
            unit: 't',
            value_schema_json: {
              requirements: {
                sources: { required_fields: ['source', 'method'] },
                evidence: { min_items: 2 },
              },
              checks: { range: { min: 0, max: 100 } },
            },
            is_active: true,
            created_by: null,
            updated_by: null,
            created_at_utc: '2026-01-01T00:00:00Z',
            updated_at_utc: '2026-01-01T00:00:00Z',
          },
        ],
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useEsgMetrics>)

    renderPage('/esg/facts/new?metric_id=m1&year=2025')

    screen.getByLabelText('source')
    screen.getByLabelText('method')
    screen.getByText(/Expected evidence:/)
    screen.getByText(/Expected range:/)
  })
})
