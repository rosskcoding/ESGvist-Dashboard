/**
 * React Query hooks for ESGvist Platform API
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import { useAuthStore } from '@/stores/authStore'
import type {
  Asset,
  AssetKind,
  AssetUploadResponse,
  AuditCheckCreate,
  AuditCheckDTO,
  AuditCheckListParams,
  AuditCheckSummary,
  AuditCheckUpdate,
  AuditPackJob,
  AuditPackRequest,
  Block,
  BlockCreate,
  BlockI18nUpdate,
  BlockUpdate,
  Comment,
  CommentCreate,
  CommentThread,
  CommentThreadCreate,
  CommentThreadWithComments,
  ContentVersionList,
  ContentLock,
  ContentLockCreate,
  ContentLockRelease,
  EsgEntity,
  EsgFact,
  EsgFactCompareItem,
  EsgFactCompareRequest,
  EsgFactCreate,
  EsgFactEvidenceCreate,
  EsgFactEvidenceItem,
  EsgFactEvidenceUpdate,
  EsgFactRequestChanges,
  EsgFactReviewComment,
  EsgFactReviewCommentCreate,
  EsgFactTimelineEvent,
  EsgFactUpdate,
  EsgGaps,
  EsgSnapshot,
  EsgLocation,
  EsgMetric,
  EsgMetricCreate,
  EsgMetricOwner,
  EsgMetricOwnerUpsert,
  EsgMetricUpdate,
  EsgSegment,
  EvidenceItem,
  EvidenceType,
  EvidenceVisibility,
  LockScopeType,
  PaginatedResponse,
  Report,
  ReportCreate,
  ReportUpdate,
  Section,
  SectionCreate,
  SectionI18nUpdate,
  SectionUpdate,
  SignedUrlResponse,
  Theme,
  ThemeCreate,
  ThemeListItem,
  ThemeUpdate,
} from '@/types/api'

// === Query Keys ===

export const queryKeys = {
  reports: {
    all: ['reports'] as const,
    list: (params?: { page?: number; year?: number }) =>
      [...queryKeys.reports.all, 'list', params] as const,
    detail: (id: string) => [...queryKeys.reports.all, 'detail', id] as const,
    bySlug: (slug: string) => [...queryKeys.reports.all, 'by-slug', slug] as const,
  },
  sections: {
    all: ['sections'] as const,
    list: (reportId: string, parentId?: string | null) =>
      [...queryKeys.sections.all, 'list', reportId, parentId] as const,
    detail: (id: string) => [...queryKeys.sections.all, 'detail', id] as const,
    bySlug: (reportSlug: string, sectionSlug: string) =>
      [...queryKeys.sections.all, 'by-slug', reportSlug, sectionSlug] as const,
  },
  blocks: {
    all: ['blocks'] as const,
    list: (sectionId: string) =>
      [...queryKeys.blocks.all, 'list', sectionId] as const,
    detail: (id: string) => [...queryKeys.blocks.all, 'detail', id] as const,
  },
  themes: {
    all: ['themes'] as const,
    list: () => [...queryKeys.themes.all, 'list'] as const,
    detail: (id: string) => [...queryKeys.themes.all, 'detail', id] as const,
    bySlug: (slug: string) => [...queryKeys.themes.all, 'slug', slug] as const,
  },
  assets: {
    all: ['assets'] as const,
    list: (params?: { kind?: AssetKind; page?: number }) =>
      [...queryKeys.assets.all, 'list', params] as const,
    detail: (id: string) => [...queryKeys.assets.all, 'detail', id] as const,
  },
  comments: {
    all: ['comments'] as const,
    threads: (reportId: string, params?: {
      anchor_type?: string
      anchor_id?: string
      thread_status?: string
    }) => [...queryKeys.comments.all, 'threads', reportId, params] as const,
    thread: (reportId: string, threadId: string) =>
      [...queryKeys.comments.all, 'thread', reportId, threadId] as const,
  },
  locks: {
    all: ['locks'] as const,
    check: (companyId: string, scopeType: LockScopeType, scopeId: string) =>
      [...queryKeys.locks.all, 'check', companyId, scopeType, scopeId] as const,
  },
  evidence: {
    all: ['evidence'] as const,
    list: (
      companyId: string,
      params?: {
        report_id?: string
        scope_type?: string
        scope_id?: string
        evidence_type?: EvidenceType
        visibility?: EvidenceVisibility
        status?: string
        owner_user_id?: string
        include_deleted?: boolean
        page?: number
        page_size?: number
      }
    ) => [...queryKeys.evidence.all, 'list', companyId, params] as const,
  },
  auditChecks: {
    all: ['audit-checks'] as const,
    list: (companyId: string, params?: AuditCheckListParams) =>
      [...queryKeys.auditChecks.all, 'list', companyId, params] as const,
    detail: (companyId: string, checkId: string) =>
      [...queryKeys.auditChecks.all, 'detail', companyId, checkId] as const,
    summary: (companyId: string, reportId: string) =>
      [...queryKeys.auditChecks.all, 'summary', companyId, reportId] as const,
  },
  auditPack: {
    all: ['audit-pack'] as const,
    job: (reportId: string, jobId: string) => [...queryKeys.auditPack.all, 'job', reportId, jobId] as const,
  },
  contentVersions: {
    all: ['content-versions'] as const,
    list: (blockId: string, locale: string, limit?: number) =>
      [...queryKeys.contentVersions.all, 'list', blockId, locale, limit] as const,
  },
  esg: {
    all: ['esg'] as const,
    gaps: (params?: Record<string, unknown>) => [...queryKeys.esg.all, 'gaps', params] as const,
    snapshot: (params?: Record<string, unknown>) => [...queryKeys.esg.all, 'snapshot', params] as const,
    metrics: {
      list: (params?: { search?: string; include_inactive?: boolean; company_id?: string; page?: number; page_size?: number }) =>
        [...queryKeys.esg.all, 'metrics', 'list', params] as const,
      detail: (metricId: string) => [...queryKeys.esg.all, 'metrics', 'detail', metricId] as const,
    },
    metricOwners: {
      list: (params?: { metric_ids?: string[]; company_id?: string }) =>
        [...queryKeys.esg.all, 'metricOwners', 'list', params] as const,
    },
    dimensions: {
      entities: (params?: { search?: string; include_inactive?: boolean; company_id?: string; page?: number; page_size?: number }) =>
        [...queryKeys.esg.all, 'entities', 'list', params] as const,
      locations: (params?: { search?: string; include_inactive?: boolean; company_id?: string; page?: number; page_size?: number }) =>
        [...queryKeys.esg.all, 'locations', 'list', params] as const,
      segments: (params?: { search?: string; include_inactive?: boolean; company_id?: string; page?: number; page_size?: number }) =>
        [...queryKeys.esg.all, 'segments', 'list', params] as const,
    },
    facts: {
      list: (params?: Record<string, unknown>) => [...queryKeys.esg.all, 'facts', 'list', params] as const,
      detail: (factId: string) => [...queryKeys.esg.all, 'facts', 'detail', factId] as const,
      evidence: (factId: string) => [...queryKeys.esg.all, 'facts', factId, 'evidence'] as const,
      comments: (factId: string) => [...queryKeys.esg.all, 'facts', factId, 'comments'] as const,
      timeline: (factId: string) => [...queryKeys.esg.all, 'facts', factId, 'timeline'] as const,
    },
  },
}

// === Content Lock Hooks ===

export function useCheckLocks(companyId: string, scopeType: LockScopeType, scopeId: string) {
  return useQuery({
    queryKey: queryKeys.locks.check(companyId, scopeType, scopeId),
    queryFn: async () => {
      const { data } = await apiClient.get<ContentLock[]>(
        `/api/v1/companies/${companyId}/locks/check/${scopeType}/${scopeId}`
      )
      return data
    },
    enabled: !!companyId && !!scopeType && !!scopeId,
  })
}

export function useApplyLock(companyId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: ContentLockCreate) => {
      const { data: lock } = await apiClient.post<ContentLock>(
        `/api/v1/companies/${companyId}/locks`,
        data
      )
      return lock
    },
    onSuccess: (lock) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.locks.all })
      queryClient.invalidateQueries({
        queryKey: queryKeys.locks.check(lock.company_id, lock.scope_type, lock.scope_id),
      })
    },
  })
}

export function useReleaseLock(companyId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (variables: { lockId: string; data?: ContentLockRelease }) => {
      const { data } = await apiClient.post<ContentLock>(
        `/api/v1/companies/${companyId}/locks/${variables.lockId}/release`,
        variables.data ?? {}
      )
      return data
    },
    onSuccess: (lock) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.locks.all })
      queryClient.invalidateQueries({
        queryKey: queryKeys.locks.check(lock.company_id, lock.scope_type, lock.scope_id),
      })
    },
  })
}

// === Evidence Hooks ===

export function useEvidenceItems(
  companyId: string,
  params?: {
    report_id?: string
    scope_type?: string
    scope_id?: string
    evidence_type?: EvidenceType
    visibility?: EvidenceVisibility
    status?: string
    owner_user_id?: string
    include_deleted?: boolean
    page?: number
    page_size?: number
  }
) {
  return useQuery({
    queryKey: queryKeys.evidence.list(companyId, params),
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<EvidenceItem>>(
        `/api/v1/companies/${companyId}/evidence`,
        { params }
      )
      return data
    },
    enabled: !!companyId,
  })
}

// === Audit Checks Hooks ===

/**
 * List audit checks for a company with optional filters.
 */
export function useAuditChecks(companyId: string, params?: AuditCheckListParams) {
  return useQuery({
    queryKey: queryKeys.auditChecks.list(companyId, params),
    queryFn: async () => {
      const queryParams: Record<string, string> = {}
      if (params?.report_id) queryParams.report_id = params.report_id
      if (params?.target_type) queryParams.target_type = params.target_type
      if (params?.target_id) queryParams.target_id = params.target_id
      if (params?.check_status) queryParams.check_status = params.check_status
      if (params?.auditor_id) queryParams.auditor_id = params.auditor_id

      const { data } = await apiClient.get<AuditCheckDTO[]>(
        `/api/v1/companies/${companyId}/audit-checks`,
        { params: Object.keys(queryParams).length ? queryParams : undefined }
      )
      return data
    },
    enabled: !!companyId,
  })
}

/**
 * Get audit summary (aggregated stats) for a report.
 */
export function useAuditCheckSummary(companyId: string, reportId: string) {
  return useQuery({
    queryKey: queryKeys.auditChecks.summary(companyId, reportId),
    queryFn: async () => {
      const { data } = await apiClient.get<AuditCheckSummary>(
        `/api/v1/companies/${companyId}/audit-checks/summary/${reportId}`
      )
      return data
    },
    enabled: !!companyId && !!reportId,
  })
}

/**
 * Create a new audit check.
 */
export function useCreateAuditCheck(companyId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: AuditCheckCreate) => {
      const { data: check } = await apiClient.post<AuditCheckDTO>(
        `/api/v1/companies/${companyId}/audit-checks`,
        data
      )
      return check
    },
    onSuccess: (check) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auditChecks.all })
      queryClient.invalidateQueries({
        queryKey: queryKeys.auditChecks.summary(companyId, check.report_id),
      })
    },
  })
}

/**
 * Update an existing audit check.
 */
export function useUpdateAuditCheck(companyId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (variables: { checkId: string; data: AuditCheckUpdate }) => {
      const { data: check } = await apiClient.patch<AuditCheckDTO>(
        `/api/v1/companies/${companyId}/audit-checks/${variables.checkId}`,
        variables.data
      )
      return check
    },
    onSuccess: (check) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auditChecks.all })
      queryClient.invalidateQueries({
        queryKey: queryKeys.auditChecks.summary(companyId, check.report_id),
      })
    },
  })
}

/**
 * Delete an audit check.
 */
export function useDeleteAuditCheck(companyId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (checkId: string) => {
      await apiClient.delete(`/api/v1/companies/${companyId}/audit-checks/${checkId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auditChecks.all })
    },
  })
}

// === Audit Pack Hooks ===

export function useCreateAuditPack(reportId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: AuditPackRequest) => {
      const { data: job } = await apiClient.post<AuditPackJob>(
        `/api/v1/reports/${reportId}/audit-pack`,
        data
      )
      return job
    },
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auditPack.all })
      queryClient.setQueryData(queryKeys.auditPack.job(job.report_id, job.job_id), job)
    },
  })
}

export function useAuditPackJob(reportId: string, jobId: string) {
  return useQuery({
    queryKey: queryKeys.auditPack.job(reportId, jobId),
    queryFn: async () => {
      const { data } = await apiClient.get<AuditPackJob>(
        `/api/v1/reports/${reportId}/audit-pack/${jobId}`
      )
      return data
    },
    enabled: !!reportId && !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'queued' || status === 'running' ? 3000 : false
    },
  })
}

/**
 * Alias for useAuditPackJob (matches TODO naming).
 */
export const useAuditPackStatus = useAuditPackJob

export function useDownloadAuditPackArtifact() {
  return useMutation({
    mutationFn: async (variables: {
      reportId: string
      jobId: string
      artifactId: string
      filename: string
    }) => {
      const response = await fetch(
        `/api/v1/reports/${variables.reportId}/audit-pack/${variables.jobId}/artifacts/${variables.artifactId}/download`,
        {
          headers: {
            Authorization: `Bearer ${useAuthStore.getState().accessToken}`,
          },
        }
      )

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Download failed')
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = variables.filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    },
  })
}

// === Content Versions Hooks ===

export function useBlockVersions(blockId: string, locale: string, limit = 10) {
  return useQuery({
    queryKey: queryKeys.contentVersions.list(blockId, locale, limit),
    queryFn: async () => {
      const { data } = await apiClient.get<ContentVersionList>(
        `/api/v1/blocks/${blockId}/versions`,
        { params: { locale, limit: String(limit) } }
      )
      return data
    },
    enabled: !!blockId && !!locale,
  })
}

// === Video Hooks ===

interface VideoUploadResponse {
  asset_id: string
  filename: string
  size_bytes: number
  duration_sec: number | null
  width: number | null
  height: number | null
  message: string
}

export function useUploadVideo() {
  return useMutation({
    mutationFn: async (variables: { file: File; companyId?: string }) => {
      const formData = new FormData()
      formData.append('file', variables.file)

      const params: Record<string, string> = {}
      if (variables.companyId) params.company_id = variables.companyId

      const { data } = await apiClient.post<VideoUploadResponse>(
        '/api/v1/video/upload',
        formData,
        { params }
      )
      return data
    },
  })
}

export function useSetVideoPosterTimestamp() {
  return useMutation({
    mutationFn: async (variables: { blockId: string; time_ms: number }) => {
      const { data } = await apiClient.post<{
        block_id: string
        poster_job_id: string
        poster_status: string
        message: string
      }>(`/api/v1/video/blocks/${variables.blockId}/poster/set`, { time_ms: variables.time_ms })
      return data
    },
  })
}

// === Report Hooks ===

export function useReports(params?: { page?: number; year?: number }) {
  return useQuery({
    queryKey: queryKeys.reports.list(params),
    queryFn: async () => {
      const queryParams: Record<string, string> = {}
      if (params?.page) queryParams.page = String(params.page)
      if (params?.year) queryParams.year = String(params.year)
      
      const { data } = await apiClient.get<PaginatedResponse<Report>>(
        '/api/v1/reports',
        { params: queryParams }
      )
      return data
    },
  })
}

export function useReport(reportId: string) {
  return useQuery({
    queryKey: queryKeys.reports.detail(reportId),
    queryFn: async () => {
      const { data } = await apiClient.get<Report>(
        `/api/v1/reports/${reportId}`
      )
      return data
    },
    enabled: !!reportId,
  })
}

export function useReportBySlug(slug: string) {
  return useQuery({
    queryKey: ['reports', 'by-slug', slug],
    queryFn: async () => {
      const { data } = await apiClient.get<Report>(
        `/api/v1/reports/by-slug/${slug}`
      )
      return data
    },
    enabled: !!slug,
  })
}

export function useCreateReport() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: ReportCreate) => {
      const { data: report } = await apiClient.post<Report>(
        '/api/v1/reports',
        data
      )
      return report
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.reports.all })
    },
  })
}

export function useUpdateReport() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      reportId,
      data,
    }: {
      reportId: string
      data: ReportUpdate
    }) => {
      const { data: report } = await apiClient.patch<Report>(
        `/api/v1/reports/${reportId}`,
        data
      )
      return report
    },
    onSuccess: (_, { reportId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.reports.detail(reportId),
      })
      queryClient.invalidateQueries({ queryKey: queryKeys.reports.all })
    },
  })
}

export function useDeleteReport() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (reportId: string) => {
      await apiClient.delete(`/api/v1/reports/${reportId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.reports.all })
    },
  })
}

// === Section Hooks ===

export function useSections(reportId: string, parentId?: string | null) {
  return useQuery({
    queryKey: queryKeys.sections.list(reportId, parentId),
    queryFn: async () => {
      const params: Record<string, string> = { report_id: reportId }
      if (parentId !== undefined) {
        params.parent_section_id = parentId || ''
      }
      
      const { data } = await apiClient.get<PaginatedResponse<Section>>(
        '/api/v1/sections',
        { params }
      )
      return data
    },
    enabled: !!reportId,
  })
}

export function useSection(sectionId: string) {
  return useQuery({
    queryKey: queryKeys.sections.detail(sectionId),
    queryFn: async () => {
      const { data } = await apiClient.get<Section>(
        `/api/v1/sections/${sectionId}`
      )
      return data
    },
    enabled: !!sectionId,
  })
}

export function useSectionBySlug(reportSlug: string, sectionSlug: string) {
  return useQuery({
    queryKey: queryKeys.sections.bySlug(reportSlug, sectionSlug),
    queryFn: async () => {
      const { data } = await apiClient.get<Section>(
        `/api/v1/sections/by-slug/${reportSlug}/${sectionSlug}`
      )
      return data
    },
    enabled: !!reportSlug && !!sectionSlug,
  })
}

export function useCreateSection() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: SectionCreate) => {
      const { data: section } = await apiClient.post<Section>(
        '/api/v1/sections',
        data
      )
      return section
    },
    onSuccess: (section) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sections.list(section.report_id),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.reports.detail(section.report_id),
      })
    },
  })
}

export function useUpdateSection() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      sectionId,
      data,
    }: {
      sectionId: string
      data: SectionUpdate
    }) => {
      const { data: section } = await apiClient.patch<Section>(
        `/api/v1/sections/${sectionId}`,
        data
      )
      return section
    },
    onSuccess: (section) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sections.detail(section.section_id),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.sections.list(section.report_id),
      })
    },
  })
}

export function useUpdateSectionI18n() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (variables: {
      sectionId: string
      reportId: string
      locale: string
      data: SectionI18nUpdate
    }) => {
      const { data: result } = await apiClient.patch(
        `/api/v1/sections/${variables.sectionId}/i18n/${variables.locale}`,
        variables.data
      )
      return result
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sections.detail(variables.sectionId),
      })
      // Also invalidate list cache so UI stays in sync
      queryClient.invalidateQueries({
        queryKey: queryKeys.sections.list(variables.reportId),
      })
    },
  })
}

export function useDeleteSection() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      sectionId,
      reportId,
    }: {
      sectionId: string
      reportId: string
    }) => {
      await apiClient.delete(`/api/v1/sections/${sectionId}`)
      return { reportId }
    },
    onSuccess: (_, { reportId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sections.list(reportId),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.reports.detail(reportId),
      })
    },
  })
}

export function useReorderSection() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      sectionId,
      newOrder,
      newParentId,
    }: {
      sectionId: string
      newOrder: number
      newParentId?: string | null
    }) => {
      const params: Record<string, string> = { new_order: String(newOrder) }
      if (newParentId !== undefined && newParentId !== null) {
        params.new_parent_id = newParentId
      }
      
      const { data } = await apiClient.post<Section>(
        `/api/v1/sections/${sectionId}/reorder`,
        null,
        { params }
      )
      return data
    },
    onSuccess: (section) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.sections.list(section.report_id),
      })
    },
  })
}

export function useBulkReorderSections() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: {
      report_id: string
      items: Array<{
        section_id: string
        order_index: number
        parent_section_id: string | null
        depth: number
      }>
    }) => {
      const { data: sections } = await apiClient.post<Section[]>(
        '/api/v1/sections/bulk-reorder',
        data
      )
      return sections
    },
    onSuccess: (sections) => {
      if (sections.length > 0) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.sections.list(sections[0].report_id),
        })
      }
    },
  })
}

// === Block Hooks ===

export function useBlocks(sectionId: string) {
  return useQuery({
    queryKey: queryKeys.blocks.list(sectionId),
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Block>>(
        '/api/v1/blocks',
        { params: { section_id: sectionId } }
      )
      return data
    },
    enabled: !!sectionId,
  })
}

export function useBlock(blockId: string) {
  return useQuery({
    queryKey: queryKeys.blocks.detail(blockId),
    queryFn: async () => {
      const { data } = await apiClient.get<Block>(
        `/api/v1/blocks/${blockId}`
      )
      return data
    },
    enabled: !!blockId,
  })
}

export function useCreateBlock() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: BlockCreate) => {
      const { data: block } = await apiClient.post<Block>(
        '/api/v1/blocks',
        data
      )
      return block
    },
    onSuccess: (block) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.blocks.list(block.section_id),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.sections.detail(block.section_id),
      })
    },
  })
}

export function useUpdateBlock() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      blockId,
      data,
    }: {
      blockId: string
      data: BlockUpdate
    }) => {
      const { data: block } = await apiClient.patch<Block>(
        `/api/v1/blocks/${blockId}`,
        data
      )
      return block
    },
    onSuccess: (block) => {
      // Use refetchQueries for immediate update (not just invalidate)
      queryClient.refetchQueries({
        queryKey: queryKeys.blocks.detail(block.block_id),
      })
      queryClient.refetchQueries({
        queryKey: queryKeys.blocks.list(block.section_id),
      })
    },
  })
}

export function useUpdateBlockI18n() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (variables: {
      blockId: string
      sectionId: string
      locale: string
      data: BlockI18nUpdate
    }) => {
      const { data: result } = await apiClient.patch(
        `/api/v1/blocks/${variables.blockId}/i18n/${variables.locale}`,
        variables.data
      )
      return result
    },
    onSuccess: (_, variables) => {
      // Use refetchQueries for immediate update (not just invalidate)
      queryClient.refetchQueries({
        queryKey: queryKeys.blocks.detail(variables.blockId),
      })
      // Also refetch list cache so UI stays in sync
      queryClient.refetchQueries({
        queryKey: queryKeys.blocks.list(variables.sectionId),
      })
    },
  })
}

export function useDeleteBlock() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      blockId,
      sectionId,
    }: {
      blockId: string
      sectionId: string
    }) => {
      await apiClient.delete(`/api/v1/blocks/${blockId}`)
      return { sectionId }
    },
    onSuccess: (_, { sectionId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.blocks.list(sectionId),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.sections.detail(sectionId),
      })
    },
  })
}

export function useReorderBlock() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      blockId,
      newOrder,
      newSectionId,
    }: {
      blockId: string
      newOrder: number
      newSectionId?: string
    }) => {
      const params: Record<string, string> = { new_order: String(newOrder) }
      if (newSectionId) {
        params.new_section_id = newSectionId
      }
      
      const { data } = await apiClient.post<Block>(
        `/api/v1/blocks/${blockId}/reorder`,
        null,
        { params }
      )
      return data
    },
    onSuccess: (block) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.blocks.list(block.section_id),
      })
    },
  })
}

// === Theme Hooks ===

export function useThemes() {
  return useQuery({
    queryKey: queryKeys.themes.list(),
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<ThemeListItem>>(
        '/api/v1/themes'
      )
      return data
    },
  })
}

export function useTheme(themeId: string) {
  return useQuery({
    queryKey: queryKeys.themes.detail(themeId),
    queryFn: async () => {
      const { data } = await apiClient.get<Theme>(
        `/api/v1/themes/${themeId}`
      )
      return data
    },
    enabled: !!themeId,
  })
}

export function useThemeBySlug(slug: string) {
  return useQuery({
    queryKey: queryKeys.themes.bySlug(slug),
    queryFn: async () => {
      const { data } = await apiClient.get<Theme>(
        `/api/v1/themes/by-slug/${slug}`
      )
      return data
    },
    enabled: !!slug,
  })
}

export function useCreateTheme() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: ThemeCreate) => {
      const { data: theme } = await apiClient.post<Theme>(
        '/api/v1/themes',
        data
      )
      return theme
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.themes.all })
    },
  })
}

export function useUpdateTheme() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      themeId,
      data,
    }: {
      themeId: string
      data: ThemeUpdate
    }) => {
      const { data: theme } = await apiClient.patch<Theme>(
        `/api/v1/themes/${themeId}`,
        data
      )
      return theme
    },
    onSuccess: (theme) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.themes.detail(theme.theme_id),
      })
      queryClient.invalidateQueries({ queryKey: queryKeys.themes.all })
    },
  })
}

export function useDeleteTheme() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (themeId: string) => {
      await apiClient.delete(`/api/v1/themes/${themeId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.themes.all })
    },
  })
}

// === Translation Hooks ===

interface TranslationJobCreate {
  report_id: string
  scope_type: 'report' | 'section' | 'blocks'
  scope_ids: string[]
  target_locales: string[]
  mode: 'reporting' | 'marketing'
}

interface TranslationJob {
  job_id: string
  report_id: string
  scope_type: string
  source_locale: string
  target_locales: string[]
  mode: string
  status: string
  progress: { total: number; completed: number; failed: number }
  created_at_utc: string
}

interface TranslationProgress {
  report_id: string
  total_chunks: number
  translated_chunks: number
  pending_chunks: number
  qa_required_chunks: number
  by_locale: Record<string, { total: number; translated: number; pending: number; qa_required: number }>
}

export function useTranslationProgress(reportId: string, enabled = true) {
  return useQuery({
    queryKey: ['translations', 'progress', reportId],
    queryFn: async () => {
      const { data } = await apiClient.get<TranslationProgress>(
        `/api/v1/translations/progress/${reportId}`
      )
      return data
    },
    enabled: !!reportId && enabled,
    // Translation progress can be triggered from another tab (e.g., platform dashboard),
    // so we poll lightly to keep the editor UI in sync.
    refetchInterval: !!reportId && enabled ? 10_000 : false,
  })
}

export function useTranslationJobs(reportId: string, enabled = true) {
  return useQuery({
    queryKey: ['translations', 'jobs', reportId],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<TranslationJob>>(
        '/api/v1/translations/jobs',
        { params: { report_id: reportId } }
      )
      return data
    },
    enabled: !!reportId && enabled,
    refetchInterval: !!reportId && enabled ? 10_000 : false,
  })
}

export function useCreateTranslationJob() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: TranslationJobCreate) => {
      const { data: job } = await apiClient.post<TranslationJob>(
        '/api/v1/translations/jobs',
        data
      )
      return job
    },
    onSuccess: (job) => {
      queryClient.invalidateQueries({ 
        queryKey: ['translations', 'jobs', job.report_id] 
      })
      queryClient.invalidateQueries({ 
        queryKey: ['translations', 'progress', job.report_id] 
      })
      queryClient.invalidateQueries({ 
        queryKey: ['translations', 'blocks', job.report_id] 
      })
    },
  })
}

// === Glossary Hooks ===

export interface GlossaryTerm {
  term_id: string
  ru: string
  en: string
  kk: string
  strictness: 'do_not_translate' | 'strict' | 'preferred'
  notes: string | null
  created_at_utc: string
  updated_at_utc: string
}

export interface GlossaryTermCreate {
  ru: string
  en: string
  kk: string
  strictness: 'do_not_translate' | 'strict' | 'preferred'
  notes?: string
}

export const glossaryQueryKeys = {
  all: ['glossary'] as const,
  list: (params?: { search?: string; page?: number }) =>
    [...glossaryQueryKeys.all, 'list', params] as const,
}

export function useGlossaryTerms(params?: { search?: string; page?: number; pageSize?: number }) {
  return useQuery({
    queryKey: glossaryQueryKeys.list(params),
    queryFn: async () => {
      const queryParams: Record<string, string> = {}
      if (params?.search) queryParams.search = params.search
      if (params?.page) queryParams.page = String(params.page)
      if (params?.pageSize) queryParams.page_size = String(params.pageSize)

      const { data } = await apiClient.get<PaginatedResponse<GlossaryTerm>>(
        '/api/v1/translations/glossary',
        { params: queryParams }
      )
      return data
    },
  })
}

export function useCreateGlossaryTerm() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: GlossaryTermCreate) => {
      const { data: term } = await apiClient.post<GlossaryTerm>(
        '/api/v1/translations/glossary',
        data
      )
      return term
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: glossaryQueryKeys.all })
    },
  })
}

export function useDeleteGlossaryTerm() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (termId: string) => {
      await apiClient.delete(`/api/v1/translations/glossary/${termId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: glossaryQueryKeys.all })
    },
  })
}

// Block translation status
interface BlockTranslationStatus {
  block_id: string
  locales: Record<string, 'translated' | 'pending' | 'qa_required' | 'none'>
}

interface BlocksTranslationStatusResponse {
  report_id: string
  source_locale: string
  enabled_locales: string[]
  blocks: BlockTranslationStatus[]
}

export function useBlocksTranslationStatus(reportId: string, enabled = true) {
  return useQuery({
    queryKey: ['translations', 'blocks', reportId],
    queryFn: async () => {
      const { data } = await apiClient.get<BlocksTranslationStatusResponse>(
        `/api/v1/translations/blocks/${reportId}/status`
      )
      return data
    },
    enabled: !!reportId && enabled,
    staleTime: 30_000, // Cache for 30s - translation status doesn't change often
    refetchInterval: !!reportId && enabled ? 10_000 : false,
  })
}

// === Release Hooks ===

interface ReleaseBuildCreate {
  report_id: string
  build_type: 'draft' | 'release'
  locales: string[]
  theme_slug: string
  base_path: string
}

interface ReleaseBuild {
  build_id: string
  report_id: string
  build_type: string
  status: string
  locales: string[]
  zip_path: string | null
  error_message: string | null
  created_at_utc: string
  finished_at_utc: string | null
}

export function useReleaseBuilds(reportId: string) {
  return useQuery({
    queryKey: ['releases', 'builds', reportId],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<ReleaseBuild>>(
        '/api/v1/releases',
        { params: { report_id: reportId } }
      )
      return data
    },
    enabled: !!reportId,
    refetchInterval: (query) => {
      // Auto-refresh if any builds are running
      const hasRunning = query.state.data?.items.some(
        (b) => b.status === 'queued' || b.status === 'running'
      )
      return hasRunning ? 3000 : false
    },
  })
}

export function useCreateReleaseBuild() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: ReleaseBuildCreate) => {
      const { data: build } = await apiClient.post<ReleaseBuild>(
        '/api/v1/releases',
        data
      )
      return build
    },
    onSuccess: (build) => {
      queryClient.invalidateQueries({
        queryKey: ['releases', 'builds', build.report_id],
      })
    },
  })
}

export function useDeleteReleaseBuild() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ buildId, reportId }: { buildId: string; reportId: string }) => {
      await apiClient.delete(`/api/v1/releases/${buildId}`)
      return { reportId }
    },
    onSuccess: (_, { reportId }) => {
      queryClient.invalidateQueries({
        queryKey: ['releases', 'builds', reportId],
      })
    },
  })
}

export function useDownloadRelease() {
  return useMutation({
    mutationFn: async (buildId: string) => {
      const response = await fetch(`/api/v1/releases/${buildId}/download`, {
        headers: {
          Authorization: `Bearer ${useAuthStore.getState().accessToken}`,
        },
      })
      
      if (!response.ok) {
        throw new Error('Download failed')
      }
      
      // Trigger download
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `report-${buildId}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    },
  })
}

export function useRestoreReleaseBuild() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ buildId }: { buildId: string }) => {
      const { data } = await apiClient.post<{
        status: string
        restored_to: string
        safety_checkpoint_id: string
      }>(`/api/v1/releases/${buildId}/restore`, {})
      return data
    },
    onSuccess: () => {
      // Broad invalidation: restore can affect whole report structure/content.
      queryClient.invalidateQueries({ queryKey: queryKeys.reports.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.sections.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.blocks.all })
      queryClient.invalidateQueries({ queryKey: ['releases', 'builds'] })
      queryClient.invalidateQueries({ queryKey: ['checkpoints'] })
    },
  })
}

// === Artifact Hooks (PDF/DOCX) ===

export type ArtifactFormat = 'pdf' | 'docx'
export type ArtifactStatus = 'queued' | 'processing' | 'done' | 'failed' | 'cancelled'

export interface Artifact {
  artifact_id: string
  build_id: string
  format: ArtifactFormat
  locale: string | null
  profile: string | null
  status: ArtifactStatus
  path: string | null
  sha256: string | null
  size_bytes: number | null
  error_message: string | null
  created_at_utc: string
  updated_at_utc: string
}

export interface ArtifactCreate {
  format: ArtifactFormat
  locale: string
  profile?: string
}

export interface ArtifactListResponse {
  artifacts: Artifact[]
  build_id: string
  build_status: string
}

export const artifactQueryKeys = {
  all: ['artifacts'] as const,
  list: (buildId: string) => [...artifactQueryKeys.all, 'list', buildId] as const,
  detail: (buildId: string, artifactId: string) => [...artifactQueryKeys.all, 'detail', buildId, artifactId] as const,
}

export function useArtifacts(buildId: string) {
  return useQuery({
    queryKey: artifactQueryKeys.list(buildId),
    queryFn: async () => {
      const { data } = await apiClient.get<ArtifactListResponse>(
        `/api/v1/releases/${buildId}/artifacts`
      )
      return data
    },
    enabled: !!buildId,
    refetchInterval: (query) => {
      // Poll while any artifact is processing
      const artifacts = query.state.data?.artifacts || []
      const hasProcessing = artifacts.some(a => a.status === 'queued' || a.status === 'processing')
      return hasProcessing ? 3000 : false
    },
  })
}

export function useCreateArtifact() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ buildId, data }: { buildId: string; data: ArtifactCreate }) => {
      const { data: artifact } = await apiClient.post<Artifact>(
        `/api/v1/releases/${buildId}/artifacts`,
        data
      )
      return { artifact, buildId }
    },
    onSuccess: (_, { buildId }) => {
      queryClient.invalidateQueries({ queryKey: artifactQueryKeys.list(buildId) })
    },
  })
}

export function useDownloadArtifact() {
  return useMutation({
    mutationFn: async ({ buildId, artifactId, filename }: { buildId: string; artifactId: string; filename: string }) => {
      const response = await fetch(`/api/v1/releases/${buildId}/artifacts/${artifactId}/download`, {
        headers: {
          Authorization: `Bearer ${useAuthStore.getState().accessToken}`,
        },
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Download failed')
      }
      
      // Trigger download
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    },
  })
}

// === Asset Hooks ===

export function useAssets(params?: { kind?: AssetKind; page?: number; pageSize?: number }) {
  return useQuery({
    queryKey: queryKeys.assets.list(params),
    queryFn: async () => {
      const queryParams: Record<string, string> = {}
      if (params?.kind) queryParams.kind = params.kind
      if (params?.page) queryParams.page = String(params.page)
      if (params?.pageSize) queryParams.page_size = String(params.pageSize)
      
      const { data } = await apiClient.get<PaginatedResponse<Asset>>(
        '/api/v1/assets',
        { params: queryParams }
      )
      return data
    },
  })
}

export function useAsset(assetId: string) {
  return useQuery({
    queryKey: queryKeys.assets.detail(assetId),
    queryFn: async () => {
      const { data } = await apiClient.get<Asset>(
        `/api/v1/assets/${assetId}`
      )
      return data
    },
    enabled: !!assetId,
  })
}

export function useUploadAsset() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ file, kind }: { file: File; kind?: AssetKind }) => {
      const formData = new FormData()
      formData.append('file', file)
      
      const params: Record<string, string> = {}
      if (kind) params.kind = kind
      
      // Note: Do NOT set Content-Type header manually for FormData!
      // Axios will automatically set the correct multipart boundary
      const { data } = await apiClient.post<AssetUploadResponse>(
        '/api/v1/assets/upload',
        formData,
        { params }
      )
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.assets.all })
    },
  })
}

export function useDeleteAsset() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ assetId, force = false }: { assetId: string; force?: boolean }) => {
      await apiClient.delete(`/api/v1/assets/${assetId}`, {
        params: { force: String(force) },
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.assets.all })
    },
  })
}

export function useLinkAssetToBlock() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      assetId,
      blockId,
      purpose = 'content',
    }: {
      assetId: string
      blockId: string
      purpose?: string
    }) => {
      const { data } = await apiClient.post(
        `/api/v1/assets/${assetId}/link`,
        { block_id: blockId, purpose }
      )
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.blocks.all })
    },
  })
}

/**
 * Get a signed URL for an asset.
 * 
 * Signed URLs allow downloading assets without Authorization headers,
 * which is required for <img src>, <a href>, etc.
 * 
 * The URL expires after ttl_seconds (default: 300).
 */
export function useAssetSignedUrl(assetId: string, ttlSeconds = 300) {
  return useQuery({
    queryKey: [...queryKeys.assets.detail(assetId), 'signed-url', ttlSeconds] as const,
    queryFn: async () => {
      const { data } = await apiClient.post<SignedUrlResponse>(
        `/api/v1/assets/${assetId}/signed-url`,
        { ttl_seconds: ttlSeconds }
      )
      return data
    },
    enabled: !!assetId,
    // Refetch before expiry (with 30 second buffer)
    staleTime: (ttlSeconds - 30) * 1000,
    gcTime: ttlSeconds * 1000,
  })
}

/**
 * Generate a signed URL for an asset (imperative, for one-time use).
 * Returns the signed URL directly.
 */
export async function getAssetSignedUrl(
  assetId: string, 
  ttlSeconds = 300
): Promise<string> {
  const { data } = await apiClient.post<SignedUrlResponse>(
    `/api/v1/assets/${assetId}/signed-url`,
    { ttl_seconds: ttlSeconds }
  )
  return data.url
}

// === Admin: Company Hooks ===

import type {
  Company,
  CompanyCreate,
  CompanyUpdate,
  CompanyMembership,
  CompanyMembershipCreate,
  CompanyMembershipUpdate,
  RoleAssignment,
  RoleAssignmentCreate,
  RoleAssignmentUpdate,
  User,
  UserCreate,
  UserUpdate,
} from '@/types/api'

export const adminQueryKeys = {
  companies: {
    all: ['admin', 'companies'] as const,
    list: () => [...adminQueryKeys.companies.all, 'list'] as const,
    detail: (id: string) => [...adminQueryKeys.companies.all, 'detail', id] as const,
  },
  memberships: {
    all: ['admin', 'memberships'] as const,
    list: (companyId: string) => [...adminQueryKeys.memberships.all, 'list', companyId] as const,
  },
  roleAssignments: {
    all: ['admin', 'roleAssignments'] as const,
    list: (companyId: string) => [...adminQueryKeys.roleAssignments.all, 'list', companyId] as const,
  },
  users: {
    all: ['admin', 'users'] as const,
    list: () => [...adminQueryKeys.users.all, 'list'] as const,
  },
}

// Companies
export function useCompanies() {
  return useQuery({
    queryKey: adminQueryKeys.companies.list(),
    queryFn: async () => {
      const { data } = await apiClient.get<Company[]>(
        '/api/v1/companies'
      )
      // Wrap in paginated format for consistency
      return { items: data, total: data.length }
    },
  })
}

export function useCompany(companyId: string) {
  return useQuery({
    queryKey: adminQueryKeys.companies.detail(companyId),
    queryFn: async () => {
      const { data } = await apiClient.get<Company>(
        `/api/v1/companies/${companyId}`
      )
      return data
    },
    enabled: !!companyId,
  })
}

export function useCreateCompany() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: CompanyCreate) => {
      const { data: company } = await apiClient.post<Company>(
        '/api/v1/companies',
        data
      )
      return company
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.companies.all })
    },
  })
}

export function useUpdateCompany() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ companyId, data }: { companyId: string; data: CompanyUpdate }) => {
      const { data: company } = await apiClient.patch<Company>(
        `/api/v1/companies/${companyId}`,
        data
      )
      return company
    },
    onSuccess: (company) => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.companies.detail(company.company_id) })
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.companies.all })
    },
  })
}

export function useDeleteCompany() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (companyId: string) => {
      await apiClient.delete(`/api/v1/companies/${companyId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.companies.all })
    },
  })
}

// Company Memberships
export function useCompanyMemberships(companyId: string) {
  return useQuery({
    queryKey: adminQueryKeys.memberships.list(companyId),
    queryFn: async () => {
      const { data } = await apiClient.get<CompanyMembership[]>(
        `/api/v1/companies/${companyId}/members`
      )
      return { items: data, total: data.length }
    },
    enabled: !!companyId,
  })
}

export function useCreateMembership() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ companyId, data }: { companyId: string; data: CompanyMembershipCreate }) => {
      const { data: membership } = await apiClient.post<CompanyMembership>(
        `/api/v1/companies/${companyId}/members`,
        data
      )
      return { membership, companyId }
    },
    onSuccess: (_, { companyId }) => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.memberships.list(companyId) })
    },
  })
}

export function useCreateAndAddMember() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ companyId, data }: { companyId: string; data: UserCreate }) => {
      const { data: membership } = await apiClient.post<CompanyMembership>(
        `/api/v1/companies/${companyId}/members/create-and-add`,
        data
      )
      return { membership, companyId }
    },
    onSuccess: (_, { companyId }) => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.memberships.list(companyId) })
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.users.all })
    },
  })
}

export function useUpdateMembership() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      companyId,
      userId,
      data,
    }: {
      companyId: string
      userId: string
      data: CompanyMembershipUpdate
    }) => {
      const { data: membership } = await apiClient.patch<CompanyMembership>(
        `/api/v1/companies/${companyId}/members/${userId}`,
        data
      )
      return { membership, companyId }
    },
    onSuccess: (_, { companyId }) => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.memberships.list(companyId) })
    },
  })
}

export function useDeleteMembership() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ companyId, userId }: { companyId: string; userId: string }) => {
      await apiClient.delete(`/api/v1/companies/${companyId}/members/${userId}`)
      return { companyId }
    },
    onSuccess: (_, { companyId }) => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.memberships.list(companyId) })
    },
  })
}

// Role Assignments
export function useRoleAssignments(companyId: string) {
  return useQuery({
    queryKey: adminQueryKeys.roleAssignments.list(companyId),
    queryFn: async () => {
      const { data } = await apiClient.get<RoleAssignment[]>(
        `/api/v1/companies/${companyId}/roles`
      )
      return { items: data, total: data.length }
    },
    enabled: !!companyId,
  })
}

export function useCreateRoleAssignment() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ companyId, data }: { companyId: string; data: RoleAssignmentCreate }) => {
      const { data: assignment } = await apiClient.post<RoleAssignment>(
        `/api/v1/companies/${companyId}/roles`,
        data
      )
      return { assignment, companyId }
    },
    onSuccess: (_, { companyId }) => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.roleAssignments.list(companyId) })
    },
  })
}

export function useUpdateRoleAssignment() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      companyId,
      assignmentId,
      data,
    }: {
      companyId: string
      assignmentId: string
      data: RoleAssignmentUpdate
    }) => {
      const { data: assignment } = await apiClient.patch<RoleAssignment>(
        `/api/v1/companies/${companyId}/roles/${assignmentId}`,
        data
      )
      return { assignment, companyId }
    },
    onSuccess: (_, { companyId }) => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.roleAssignments.list(companyId) })
    },
  })
}

export function useDeleteRoleAssignment() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ companyId, assignmentId }: { companyId: string; assignmentId: string }) => {
      await apiClient.delete(`/api/v1/companies/${companyId}/roles/${assignmentId}`)
      return { companyId }
    },
    onSuccess: (_, { companyId }) => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.roleAssignments.list(companyId) })
    },
  })
}

// Users list for assignment
export function useUsers() {
  return useQuery({
    queryKey: adminQueryKeys.users.list(),
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<User>>(
        '/api/v1/auth/users'
      )
      return data
    },
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: UserCreate) => {
      const { data: user } = await apiClient.post<User>(
        '/api/v1/auth/users',
        data
      )
      return user
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.users.all })
    },
  })
}

export function useUpdateUser() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ userId, data }: { userId: string; data: UserUpdate }) => {
      const { data: user } = await apiClient.patch<User>(
        `/api/v1/auth/users/${userId}`,
        data
      )
      return user
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.users.all })
    },
  })
}

export function useDeleteUser() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (userId: string) => {
      await apiClient.delete(`/api/v1/auth/users/${userId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminQueryKeys.users.all })
    },
  })
}

// === Comment Hooks ===

export function useCommentThreads(
  reportId: string,
  params?: {
    anchor_type?: string
    anchor_id?: string
    thread_status?: string
    page?: number
    page_size?: number
  }
) {
  return useQuery({
    queryKey: queryKeys.comments.threads(reportId, params),
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<CommentThread>>(
        `/api/v1/reports/${reportId}/comment-threads`,
        { params }
      )
      return data
    },
    enabled: !!reportId,
  })
}

export function useCommentThread(reportId: string, threadId: string) {
  return useQuery({
    queryKey: queryKeys.comments.thread(reportId, threadId),
    queryFn: async () => {
      const { data } = await apiClient.get<CommentThreadWithComments>(
        `/api/v1/reports/${reportId}/comment-threads/${threadId}`
      )
      return data
    },
    enabled: !!reportId && !!threadId,
  })
}

export function useCreateCommentThread() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      reportId,
      data,
    }: {
      reportId: string
      data: CommentThreadCreate
    }) => {
      const { data: thread } = await apiClient.post<CommentThreadWithComments>(
        `/api/v1/reports/${reportId}/comment-threads`,
        data
      )
      return thread
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        // Invalidate ALL thread lists for this report (including filtered by anchor/status params)
        queryKey: [...queryKeys.comments.all, 'threads', variables.reportId],
      })
    },
  })
}

export function useAddComment() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      reportId,
      threadId,
      data,
    }: {
      reportId: string
      threadId: string
      data: CommentCreate
    }) => {
      const { data: comment } = await apiClient.post<Comment>(
        `/api/v1/reports/${reportId}/comment-threads/${threadId}/comments`,
        data
      )
      return comment
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.comments.thread(variables.reportId, variables.threadId),
      })
      queryClient.invalidateQueries({
        // Invalidate ALL thread lists for this report (including filtered by anchor/status params)
        queryKey: [...queryKeys.comments.all, 'threads', variables.reportId],
      })
    },
  })
}

export function useResolveThread() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      reportId,
      threadId,
    }: {
      reportId: string
      threadId: string
    }) => {
      const { data } = await apiClient.post<CommentThread>(
        `/api/v1/reports/${reportId}/comment-threads/${threadId}/resolve`
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.comments.thread(variables.reportId, variables.threadId),
      })
      queryClient.invalidateQueries({
        // Invalidate ALL thread lists for this report (including filtered by anchor/status params)
        queryKey: [...queryKeys.comments.all, 'threads', variables.reportId],
      })
    },
  })
}

export function useReopenThread() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      reportId,
      threadId,
    }: {
      reportId: string
      threadId: string
    }) => {
      const { data } = await apiClient.post<CommentThread>(
        `/api/v1/reports/${reportId}/comment-threads/${threadId}/reopen`
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.comments.thread(variables.reportId, variables.threadId),
      })
      queryClient.invalidateQueries({
        // Invalidate ALL thread lists for this report (including filtered by anchor/status params)
        queryKey: [...queryKeys.comments.all, 'threads', variables.reportId],
      })
    },
  })
}

export function useDeleteComment() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({
      reportId,
      threadId,
      commentId,
    }: {
      reportId: string
      threadId: string
      commentId: string
    }) => {
      await apiClient.delete(
        `/api/v1/reports/${reportId}/comment-threads/${threadId}/comments/${commentId}`
      )
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.comments.thread(variables.reportId, variables.threadId),
      })
      queryClient.invalidateQueries({
        // Invalidate ALL thread lists for this report (including filtered by anchor/status params)
        queryKey: [...queryKeys.comments.all, 'threads', variables.reportId],
      })
    },
  })
}

// === ESG Hooks ===

export function useEsgGaps(params: {
  periodType: string
  periodStart: string
  periodEnd: string
  isYtd?: boolean
  standard?: string
  entityId?: string
  locationId?: string
  segmentId?: string
  includeInactiveMetrics?: boolean
  reviewOverdueDays?: number
  maxAttentionFacts?: number
  companyId?: string
  enabled?: boolean
}) {
  return useQuery({
    queryKey: queryKeys.esg.gaps({
      period_type: params.periodType,
      period_start: params.periodStart,
      period_end: params.periodEnd,
      is_ytd: params.isYtd ?? false,
      standard: params.standard,
      entity_id: params.entityId,
      location_id: params.locationId,
      segment_id: params.segmentId,
      include_inactive_metrics: params.includeInactiveMetrics,
      review_overdue_days: params.reviewOverdueDays,
      max_attention_facts: params.maxAttentionFacts,
      company_id: params.companyId,
    }),
    queryFn: async () => {
      const queryParams: Record<string, string> = {
        period_type: params.periodType,
        period_start: params.periodStart,
        period_end: params.periodEnd,
        is_ytd: String(params.isYtd ?? false),
      }
      if (params.standard) queryParams.standard = params.standard
      if (params.entityId) queryParams.entity_id = params.entityId
      if (params.locationId) queryParams.location_id = params.locationId
      if (params.segmentId) queryParams.segment_id = params.segmentId
      if (params.includeInactiveMetrics !== undefined) {
        queryParams.include_inactive_metrics = String(params.includeInactiveMetrics)
      }
      if (params.reviewOverdueDays !== undefined) queryParams.review_overdue_days = String(params.reviewOverdueDays)
      if (params.maxAttentionFacts !== undefined) queryParams.max_attention_facts = String(params.maxAttentionFacts)
      if (params.companyId) queryParams.company_id = params.companyId

      const { data } = await apiClient.get<EsgGaps>('/api/v1/esg/gaps', { params: queryParams })
      return data
    },
    enabled: params.enabled ?? Boolean(params.periodStart && params.periodEnd),
  })
}

export function useEsgSnapshot(params: {
  periodType: string
  periodStart: string
  periodEnd: string
  isYtd?: boolean
  standard?: string
  entityId?: string
  locationId?: string
  segmentId?: string
  includeInactiveMetrics?: boolean
  companyId?: string
  enabled?: boolean
}) {
  return useQuery({
    queryKey: queryKeys.esg.snapshot({
      period_type: params.periodType,
      period_start: params.periodStart,
      period_end: params.periodEnd,
      is_ytd: params.isYtd ?? false,
      standard: params.standard,
      entity_id: params.entityId,
      location_id: params.locationId,
      segment_id: params.segmentId,
      include_inactive_metrics: params.includeInactiveMetrics,
      company_id: params.companyId,
    }),
    queryFn: async () => {
      const queryParams: Record<string, string> = {
        period_type: params.periodType,
        period_start: params.periodStart,
        period_end: params.periodEnd,
        is_ytd: String(params.isYtd ?? false),
      }
      if (params.standard) queryParams.standard = params.standard
      if (params.entityId) queryParams.entity_id = params.entityId
      if (params.locationId) queryParams.location_id = params.locationId
      if (params.segmentId) queryParams.segment_id = params.segmentId
      if (params.includeInactiveMetrics !== undefined) {
        queryParams.include_inactive_metrics = String(params.includeInactiveMetrics)
      }
      if (params.companyId) queryParams.company_id = params.companyId

      const { data } = await apiClient.get<EsgSnapshot>('/api/v1/esg/snapshot', { params: queryParams })
      return data
    },
    enabled: params.enabled ?? Boolean(params.periodStart && params.periodEnd),
  })
}

export function useEsgMetrics(params?: {
  search?: string
  includeInactive?: boolean
  companyId?: string
  enabled?: boolean
  page?: number
  pageSize?: number
}) {
  return useQuery({
    queryKey: queryKeys.esg.metrics.list({
      search: params?.search,
      include_inactive: params?.includeInactive,
      company_id: params?.companyId,
      page: params?.page,
      page_size: params?.pageSize,
    }),
    queryFn: async () => {
      const queryParams: Record<string, string> = {}
      if (params?.search) queryParams.search = params.search
      if (params?.includeInactive !== undefined) queryParams.include_inactive = String(params.includeInactive)
      if (params?.companyId) queryParams.company_id = params.companyId
      if (params?.page) queryParams.page = String(params.page)
      if (params?.pageSize) queryParams.page_size = String(params.pageSize)

      const { data } = await apiClient.get<PaginatedResponse<EsgMetric>>(
        '/api/v1/esg/metrics',
        { params: queryParams }
      )
      return data
    },
    enabled: params?.enabled ?? true,
  })
}

export function useEsgMetricOwners(params?: {
  metricIds?: string[]
  companyId?: string
  enabled?: boolean
}) {
  const { enabled = true, ...keyParams } = params || {}
  return useQuery({
    queryKey: queryKeys.esg.metricOwners.list({
      metric_ids: keyParams.metricIds,
      company_id: keyParams.companyId,
    }),
    queryFn: async () => {
      const queryParams: Record<string, string | string[]> = {}
      if (params?.metricIds && params.metricIds.length > 0) queryParams.metric_ids = params.metricIds
      if (params?.companyId) queryParams.company_id = params.companyId

      const { data } = await apiClient.get<EsgMetricOwner[]>('/api/v1/esg/metric-owners', {
        params: queryParams,
      })
      return data
    },
    enabled,
  })
}

export function useUpsertEsgMetricOwner() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (variables: { metricId: string; data: EsgMetricOwnerUpsert }) => {
      const { data } = await apiClient.put<EsgMetricOwner>(
        `/api/v1/esg/metrics/${variables.metricId}/owner`,
        variables.data
      )
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'metricOwners'] })
    },
  })
}

export function useCreateEsgMetric() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: EsgMetricCreate) => {
      const { data: metric } = await apiClient.post<EsgMetric>('/api/v1/esg/metrics', data)
      return metric
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'metrics'] })
    },
  })
}

export function useUpdateEsgMetric() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (variables: { metricId: string; data: EsgMetricUpdate }) => {
      const { data: metric } = await apiClient.patch<EsgMetric>(
        `/api/v1/esg/metrics/${variables.metricId}`,
        variables.data
      )
      return metric
    },
    onSuccess: (metric) => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'metrics'] })
      queryClient.invalidateQueries({ queryKey: queryKeys.esg.metrics.detail(metric.metric_id) })
    },
  })
}

export function useDeleteEsgMetric() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (metricId: string) => {
      await apiClient.delete(`/api/v1/esg/metrics/${metricId}`)
      return metricId
    },
    onSuccess: (metricId) => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'metrics'] })
      queryClient.removeQueries({ queryKey: queryKeys.esg.metrics.detail(metricId) })
    },
  })
}

export function useEsgEntities(params?: {
  search?: string
  includeInactive?: boolean
  companyId?: string
  enabled?: boolean
  page?: number
  pageSize?: number
}) {
  return useQuery({
    queryKey: queryKeys.esg.dimensions.entities({
      search: params?.search,
      include_inactive: params?.includeInactive,
      company_id: params?.companyId,
      page: params?.page,
      page_size: params?.pageSize,
    }),
    queryFn: async () => {
      const queryParams: Record<string, string> = {}
      if (params?.search) queryParams.search = params.search
      if (params?.includeInactive !== undefined) queryParams.include_inactive = String(params.includeInactive)
      if (params?.companyId) queryParams.company_id = params.companyId
      if (params?.page) queryParams.page = String(params.page)
      if (params?.pageSize) queryParams.page_size = String(params.pageSize)

      const { data } = await apiClient.get<PaginatedResponse<EsgEntity>>('/api/v1/esg/entities', {
        params: queryParams,
      })
      return data
    },
    enabled: params?.enabled ?? true,
  })
}

export function useCreateEsgEntity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: { code?: string | null; name: string; description?: string | null; is_active?: boolean }) => {
      const { data: item } = await apiClient.post<EsgEntity>('/api/v1/esg/entities', data)
      return item
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'entities'] })
    },
  })
}

export function useEsgLocations(params?: {
  search?: string
  includeInactive?: boolean
  companyId?: string
  enabled?: boolean
  page?: number
  pageSize?: number
}) {
  return useQuery({
    queryKey: queryKeys.esg.dimensions.locations({
      search: params?.search,
      include_inactive: params?.includeInactive,
      company_id: params?.companyId,
      page: params?.page,
      page_size: params?.pageSize,
    }),
    queryFn: async () => {
      const queryParams: Record<string, string> = {}
      if (params?.search) queryParams.search = params.search
      if (params?.includeInactive !== undefined) queryParams.include_inactive = String(params.includeInactive)
      if (params?.companyId) queryParams.company_id = params.companyId
      if (params?.page) queryParams.page = String(params.page)
      if (params?.pageSize) queryParams.page_size = String(params.pageSize)

      const { data } = await apiClient.get<PaginatedResponse<EsgLocation>>('/api/v1/esg/locations', {
        params: queryParams,
      })
      return data
    },
    enabled: params?.enabled ?? true,
  })
}

export function useCreateEsgLocation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: { code?: string | null; name: string; description?: string | null; is_active?: boolean }) => {
      const { data: item } = await apiClient.post<EsgLocation>('/api/v1/esg/locations', data)
      return item
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'locations'] })
    },
  })
}

export function useEsgSegments(params?: {
  search?: string
  includeInactive?: boolean
  companyId?: string
  enabled?: boolean
  page?: number
  pageSize?: number
}) {
  return useQuery({
    queryKey: queryKeys.esg.dimensions.segments({
      search: params?.search,
      include_inactive: params?.includeInactive,
      company_id: params?.companyId,
      page: params?.page,
      page_size: params?.pageSize,
    }),
    queryFn: async () => {
      const queryParams: Record<string, string> = {}
      if (params?.search) queryParams.search = params.search
      if (params?.includeInactive !== undefined) queryParams.include_inactive = String(params.includeInactive)
      if (params?.companyId) queryParams.company_id = params.companyId
      if (params?.page) queryParams.page = String(params.page)
      if (params?.pageSize) queryParams.page_size = String(params.pageSize)

      const { data } = await apiClient.get<PaginatedResponse<EsgSegment>>('/api/v1/esg/segments', {
        params: queryParams,
      })
      return data
    },
    enabled: params?.enabled ?? true,
  })
}

export function useCreateEsgSegment() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: { code?: string | null; name: string; description?: string | null; is_active?: boolean }) => {
      const { data: item } = await apiClient.post<EsgSegment>('/api/v1/esg/segments', data)
      return item
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'segments'] })
    },
  })
}

export function useEsgFacts(params?: {
  metric_id?: string
  logical_key_hash?: string
  entity_id?: string
  location_id?: string
  segment_id?: string
  period_from?: string
  period_to?: string
  status?: string
  latest_only?: boolean
  has_evidence?: boolean
  companyId?: string
  page?: number
  pageSize?: number
  enabled?: boolean
}) {
  const { enabled = true, ...keyParams } = params || {}
  return useQuery({
    queryKey: queryKeys.esg.facts.list(keyParams),
    queryFn: async () => {
      const queryParams: Record<string, string> = {}
      if (params?.metric_id) queryParams.metric_id = params.metric_id
      if (params?.logical_key_hash) queryParams.logical_key_hash = params.logical_key_hash
      if (params?.entity_id) queryParams.entity_id = params.entity_id
      if (params?.location_id) queryParams.location_id = params.location_id
      if (params?.segment_id) queryParams.segment_id = params.segment_id
      if (params?.period_from) queryParams.period_from = params.period_from
      if (params?.period_to) queryParams.period_to = params.period_to
      if (params?.status) queryParams.status = params.status
      if (params?.latest_only !== undefined) queryParams.latest_only = String(params.latest_only)
      if (params?.has_evidence !== undefined) queryParams.has_evidence = String(params.has_evidence)
      if (params?.companyId) queryParams.company_id = params.companyId
      if (params?.page) queryParams.page = String(params.page)
      if (params?.pageSize) queryParams.page_size = String(params.pageSize)

      const { data } = await apiClient.get<PaginatedResponse<EsgFact>>('/api/v1/esg/facts', {
        params: queryParams,
      })
      return data
    },
    enabled,
  })
}

export function useEsgFact(factId: string) {
  return useQuery({
    queryKey: queryKeys.esg.facts.detail(factId),
    queryFn: async () => {
      const { data } = await apiClient.get<EsgFact>(`/api/v1/esg/facts/${factId}`)
      return data
    },
    enabled: !!factId,
  })
}

export function useCreateEsgFact() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: EsgFactCreate) => {
      const { data: fact } = await apiClient.post<EsgFact>('/api/v1/esg/facts', data)
      return fact
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'facts'] })
    },
  })
}

export function useUpdateEsgFact() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (variables: { factId: string; data: EsgFactUpdate }) => {
      const { data: fact } = await apiClient.patch<EsgFact>(
        `/api/v1/esg/facts/${variables.factId}`,
        variables.data
      )
      return fact
    },
    onSuccess: (fact) => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'facts'] })
      queryClient.invalidateQueries({ queryKey: queryKeys.esg.facts.detail(fact.fact_id) })
    },
  })
}

export function usePublishEsgFact() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (factId: string) => {
      const { data: fact } = await apiClient.post<EsgFact>(`/api/v1/esg/facts/${factId}/publish`)
      return fact
    },
    onSuccess: (fact) => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'facts'] })
      queryClient.invalidateQueries({ queryKey: queryKeys.esg.facts.detail(fact.fact_id) })
    },
  })
}

export function useSubmitEsgFactReview() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (factId: string) => {
      const { data: fact } = await apiClient.post<EsgFact>(`/api/v1/esg/facts/${factId}/submit-review`)
      return fact
    },
    onSuccess: (fact) => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'facts'] })
      queryClient.invalidateQueries({ queryKey: queryKeys.esg.facts.detail(fact.fact_id) })
    },
  })
}

export function useRequestEsgFactChanges() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (variables: { factId: string; data: EsgFactRequestChanges }) => {
      const { data: fact } = await apiClient.post<EsgFact>(
        `/api/v1/esg/facts/${variables.factId}/request-changes`,
        variables.data
      )
      return fact
    },
    onSuccess: (fact) => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'facts'] })
      queryClient.invalidateQueries({ queryKey: queryKeys.esg.facts.detail(fact.fact_id) })
    },
  })
}

export function useRestateEsgFact() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (factId: string) => {
      const { data: fact } = await apiClient.post<EsgFact>(`/api/v1/esg/facts/${factId}/restatement`)
      return fact
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'facts'] })
    },
  })
}

export function useEsgFactEvidence(factId: string) {
  return useQuery({
    queryKey: queryKeys.esg.facts.evidence(factId),
    queryFn: async () => {
      const { data } = await apiClient.get<EsgFactEvidenceItem[]>(
        `/api/v1/esg/facts/${factId}/evidence`
      )
      return data
    },
    enabled: !!factId,
  })
}

export function useCreateEsgFactEvidence() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (variables: { factId: string; data: EsgFactEvidenceCreate }) => {
      const { data } = await apiClient.post<EsgFactEvidenceItem>(
        `/api/v1/esg/facts/${variables.factId}/evidence`,
        variables.data
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.esg.facts.evidence(variables.factId) })
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'facts'] })
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'gaps'] })
    },
  })
}

export function useUpdateEsgFactEvidence() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (variables: { factId: string; evidenceId: string; data: EsgFactEvidenceUpdate }) => {
      const { data } = await apiClient.patch<EsgFactEvidenceItem>(
        `/api/v1/esg/facts/${variables.factId}/evidence/${variables.evidenceId}`,
        variables.data
      )
      return { item: data, factId: variables.factId }
    },
    onSuccess: ({ factId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.esg.facts.evidence(factId) })
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'facts'] })
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'gaps'] })
    },
  })
}

export function useDeleteEsgFactEvidence() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (variables: { factId: string; evidenceId: string }) => {
      await apiClient.delete(
        `/api/v1/esg/facts/${variables.factId}/evidence/${variables.evidenceId}`
      )
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.esg.facts.evidence(variables.factId) })
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'facts'] })
      queryClient.invalidateQueries({ queryKey: [...queryKeys.esg.all, 'gaps'] })
    },
  })
}

export function useEsgFactComments(factId: string) {
  return useQuery({
    queryKey: queryKeys.esg.facts.comments(factId),
    queryFn: async () => {
      const { data } = await apiClient.get<EsgFactReviewComment[]>(`/api/v1/esg/facts/${factId}/comments`)
      return data
    },
    enabled: !!factId,
  })
}

export function useCreateEsgFactComment() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (variables: { factId: string; data: EsgFactReviewCommentCreate }) => {
      const { data } = await apiClient.post<EsgFactReviewComment>(`/api/v1/esg/facts/${variables.factId}/comments`, variables.data)
      return { comment: data, factId: variables.factId }
    },
    onSuccess: ({ factId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.esg.facts.comments(factId) })
    },
  })
}

export function useEsgFactTimeline(factId: string) {
  return useQuery({
    queryKey: queryKeys.esg.facts.timeline(factId),
    queryFn: async () => {
      const { data } = await apiClient.get<EsgFactTimelineEvent[]>(`/api/v1/esg/facts/${factId}/timeline`)
      return data
    },
    enabled: !!factId,
  })
}

export function useCompareEsgFacts() {
  return useMutation({
    mutationFn: async (variables: { data: EsgFactCompareRequest; companyId?: string }) => {
      const { data: items } = await apiClient.post<EsgFactCompareItem[]>(
        '/api/v1/esg/facts/compare',
        variables.data,
        variables.companyId ? { params: { company_id: variables.companyId } } : undefined
      )
      return items
    },
  })
}
