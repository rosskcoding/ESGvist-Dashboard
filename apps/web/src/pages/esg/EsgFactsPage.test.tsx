import { describe, it, beforeEach, vi, expect } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { useAuthStore } from '@/stores/authStore'
import { EsgFactsPage } from './EsgFactsPage'

vi.mock('@/api/hooks', () => ({
  getAssetSignedUrl: vi.fn(),
  useCompanyMemberships: vi.fn(),
  useCreateEsgFactComment: vi.fn(),
  useCreateEsgFactEvidence: vi.fn(),
  useDeleteEsgFactEvidence: vi.fn(),
  useEsgEntities: vi.fn(),
  useEsgFactComments: vi.fn(),
  useEsgFactEvidence: vi.fn(),
  useEsgFactTimeline: vi.fn(),
  useEsgFacts: vi.fn(),
  useEsgMetrics: vi.fn(),
  usePublishEsgFact: vi.fn(),
  useRequestEsgFactChanges: vi.fn(),
  useRestateEsgFact: vi.fn(),
  useSubmitEsgFactReview: vi.fn(),
  useUploadAsset: vi.fn(),
  useUpdateEsgFact: vi.fn(),
}))

import {
  useCompanyMemberships,
  useCreateEsgFactComment,
  useEsgEntities,
  useEsgFactComments,
  useEsgFactEvidence,
  useEsgFactTimeline,
  useEsgFacts,
  useEsgMetrics,
  usePublishEsgFact,
  useRequestEsgFactChanges,
  useRestateEsgFact,
  useSubmitEsgFactReview,
  useUpdateEsgFact,
} from '@/api/hooks'

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/esg/facts']}>
        <EsgFactsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('EsgFactsPage', () => {
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

    vi.mocked(useEsgFacts).mockImplementation((params) => {
      if (params?.enabled === false) {
        return {
          data: { items: [] },
          isLoading: false,
          error: null,
        } as unknown as ReturnType<typeof useEsgFacts>
      }

      return {
        data: { items: [] },
        isLoading: false,
        error: null,
      } as unknown as ReturnType<typeof useEsgFacts>
    })

      vi.mocked(useEsgFactEvidence).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as unknown as ReturnType<typeof useEsgFactEvidence>)

      vi.mocked(useCompanyMemberships).mockReturnValue({
        data: { items: [] },
        isLoading: false,
        error: null,
      } as unknown as ReturnType<typeof useCompanyMemberships>)

      vi.mocked(useEsgFactComments).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as unknown as ReturnType<typeof useEsgFactComments>)

      vi.mocked(useCreateEsgFactComment).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: false,
      } as unknown as ReturnType<typeof useCreateEsgFactComment>)

      vi.mocked(useEsgFactTimeline).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as unknown as ReturnType<typeof useEsgFactTimeline>)

      vi.mocked(usePublishEsgFact).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: false,
      } as unknown as ReturnType<typeof usePublishEsgFact>)

    vi.mocked(useSubmitEsgFactReview).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useSubmitEsgFactReview>)

    vi.mocked(useRequestEsgFactChanges).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useRequestEsgFactChanges>)

    vi.mocked(useRestateEsgFact).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useRestateEsgFact>)

    vi.mocked(useUpdateEsgFact).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateEsgFact>)
  })

  it('renders empty state', () => {
    renderPage()

    screen.getByRole('heading', { name: 'Facts' })
    screen.getByText('No facts yet.')
    screen.getByRole('button', { name: '+ New fact' })
  })

  it('submits sources_json and quality_json from the edit modal', async () => {
    const updateSpy = vi.fn().mockResolvedValue({
      fact_id: 'f1',
    })

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

    const fact = {
      fact_id: 'f1',
      company_id: 'c1',
      metric_id: 'm1',
      logical_key_hash: 'a'.repeat(64),
      status: 'draft',
      version_number: 1,
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
      value_json: 5,
      dataset_id: null,
      dataset_revision_id: null,
      quality_json: { q: 1 },
      sources_json: { source: 'x' },
      created_by: null,
      updated_by: null,
      created_at_utc: '2026-01-01T00:00:00Z',
      updated_at_utc: '2026-01-02T00:00:00Z',
    }

    vi.mocked(useEsgFacts).mockImplementation((params) => {
      if (params?.enabled === false) {
        return {
          data: { items: [] },
          isLoading: false,
          error: null,
        } as unknown as ReturnType<typeof useEsgFacts>
      }

      return {
        data: {
          items: [fact],
          total: 1,
          page: 1,
          page_size: 50,
          total_pages: 1,
          has_next: false,
          has_prev: false,
        },
        isLoading: false,
        error: null,
      } as unknown as ReturnType<typeof useEsgFacts>
    })

    vi.mocked(useUpdateEsgFact).mockReturnValue({
      mutateAsync: updateSpy,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateEsgFact>)

    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))

    fireEvent.click(screen.getByLabelText('Advanced JSON (sources_json, quality_json)'))

    const sources = screen.getByLabelText('sources_json') as HTMLTextAreaElement
    const quality = screen.getByLabelText('quality_json') as HTMLTextAreaElement

    fireEvent.change(sources, { target: { value: '{"source":"new"}' } })
    fireEvent.change(quality, { target: { value: '{"q":2}' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalled()
    })

    expect(updateSpy).toHaveBeenCalledWith({
      factId: 'f1',
      data: {
        value_json: 5,
        quality_json: { q: 2 },
        sources_json: { source: 'new' },
      },
    })
  })

  it('creates a review comment and shows mention suggestions', async () => {
    const createCommentSpy = vi.fn().mockResolvedValue({
      comment: { comment_id: 'c1' },
      factId: 'f1',
    })

    vi.mocked(useCreateEsgFactComment).mockReturnValue({
      mutateAsync: createCommentSpy,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateEsgFactComment>)

    vi.mocked(useCompanyMemberships).mockReturnValue({
      data: {
        items: [
          {
            membership_id: 'm1',
            company_id: 'c1',
            user_id: 'u1',
            is_active: true,
            created_by: null,
            created_at_utc: '2026-01-01T00:00:00Z',
            updated_at_utc: '2026-01-01T00:00:00Z',
            user_email: 'alex@example.com',
            user_name: 'Alex',
            is_corporate_lead: false,
          },
        ],
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useCompanyMemberships>)

    const fact = {
      fact_id: 'f1',
      company_id: 'c1',
      metric_id: 'm1',
      logical_key_hash: 'a'.repeat(64),
      status: 'in_review',
      version_number: 1,
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
      value_json: 5,
      dataset_id: null,
      dataset_revision_id: null,
      quality_json: {},
      sources_json: {},
      created_by: null,
      updated_by: null,
      created_at_utc: '2026-01-01T00:00:00Z',
      updated_at_utc: '2026-01-02T00:00:00Z',
    }

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

    vi.mocked(useEsgFacts).mockImplementation((params) => {
      if (params?.enabled === false) {
        return {
          data: { items: [] },
          isLoading: false,
          error: null,
        } as unknown as ReturnType<typeof useEsgFacts>
      }

      return {
        data: {
          items: [fact],
          total: 1,
          page: 1,
          page_size: 50,
          total_pages: 1,
          has_next: false,
          has_prev: false,
        },
        isLoading: false,
        error: null,
      } as unknown as ReturnType<typeof useEsgFacts>
    })

    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Review' }))

    const textarea = screen.getByLabelText('Add comment') as HTMLTextAreaElement
    fireEvent.change(textarea, { target: { value: 'Ping @al' } })

    screen.getByText('Alex')
    screen.getByText('alex@example.com')

    fireEvent.click(screen.getByRole('button', { name: 'Add' }))

    await waitFor(() => {
      expect(createCommentSpy).toHaveBeenCalled()
    })

    expect(createCommentSpy).toHaveBeenCalledWith({
      factId: 'f1',
      data: { body_md: 'Ping @al' },
    })
  })
})
