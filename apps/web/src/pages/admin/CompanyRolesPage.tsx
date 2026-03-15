import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  useCompany,
  useRoleAssignments,
  useCreateRoleAssignment,
  useDeleteRoleAssignment,
  useCompanyMemberships,
  useReports,
  useSections,
} from '@/api/hooks'
import { Button, IconAlertTriangle, Input, Modal, Select, toast } from '@/components/ui'
import type { RoleType, ScopeType } from '@/types/api'
import styles from './MyCompanyAdmin.module.css'
import { PlatformAdminLayout } from './PlatformAdminLayout'

const ROLE_LABELS: Record<RoleType, string> = {
  corporate_lead: 'Corporate Lead',
  editor: 'Editor in Chief',
  content_editor: 'Editor',
  section_editor: 'SME (section expert)',
  viewer: 'Viewer',
  translator: 'Translator',
  internal_auditor: 'Internal Auditor',
  auditor: 'Auditor',
  audit_lead: 'Audit Lead',
}

const ASSIGNABLE_ROLES: RoleType[] = [
  'corporate_lead',
  'editor',
  'content_editor',
  'section_editor',
  'viewer',
  'translator',
  'internal_auditor',
  'auditor',
  'audit_lead',
]

const SCOPE_LABELS: Record<ScopeType, string> = {
  company: 'Company',
  report: 'Report',
  section: 'Section',
}

export function CompanyRolesPage() {
  const params = useParams<{ companyId?: string; companySlug?: string }>()
  const companySlug = params.companySlug ?? params.companyId

  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false)
  const [selectedUserId, setSelectedUserId] = useState('')
  const [selectedRole, setSelectedRole] = useState<RoleType>('editor')
  const [selectedScopeType, setSelectedScopeType] = useState<ScopeType>('company')
  const [selectedReportId, setSelectedReportId] = useState('')
  const [selectedSectionId, setSelectedSectionId] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [roleFilter, setRoleFilter] = useState<RoleType | 'all'>('all')

  const { data: company, isLoading: companyLoading } = useCompany(companySlug || '')
  const actualCompanyId = company?.company_id || ''

  const { data: rolesData, isLoading, error, refetch } = useRoleAssignments(actualCompanyId)
  const { data: membersData } = useCompanyMemberships(actualCompanyId)
  const { data: reportsData } = useReports()
  const { data: sectionsData } = useSections(selectedReportId)

  const createRoleAssignment = useCreateRoleAssignment()
  const deleteRoleAssignment = useDeleteRoleAssignment()

  const roles = useMemo(() => rolesData?.items ?? [], [rolesData?.items])
  const members = useMemo(() => membersData?.items ?? [], [membersData?.items])
  const activeMembers = useMemo(() => members.filter((m) => m.is_active), [members])
  const reports = useMemo(() => reportsData?.items ?? [], [reportsData?.items])
  const sections = useMemo(() => sectionsData?.items ?? [], [sectionsData?.items])

  const uniqueRoles = useMemo(() => {
    const set = new Set(roles.map((r) => r.role))
    return Array.from(set).sort((a, b) => (ROLE_LABELS[a] || a).localeCompare(ROLE_LABELS[b] || b))
  }, [roles])

  const filteredRoles = useMemo(() => {
    let result = roles

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        (r) =>
          (r.user_email || '').toLowerCase().includes(query) ||
          (r.user_name || '').toLowerCase().includes(query) ||
          ROLE_LABELS[r.role]?.toLowerCase().includes(query)
      )
    }

    if (roleFilter !== 'all') {
      result = result.filter((r) => r.role === roleFilter)
    }

    return result
  }, [roles, roleFilter, searchQuery])

  const handleAssignRole = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedUserId || !actualCompanyId) {
      toast.error('Select a user')
      return
    }

    let scopeId: string

    if (selectedScopeType === 'company') {
      scopeId = actualCompanyId
    } else if (selectedScopeType === 'report') {
      if (!selectedReportId) return
      scopeId = selectedReportId
    } else if (selectedScopeType === 'section') {
      if (!selectedReportId || !selectedSectionId) return
      scopeId = selectedSectionId
    } else {
      return
    }

    try {
      await createRoleAssignment.mutateAsync({
        companyId: actualCompanyId,
        data: {
          user_id: selectedUserId,
          role: selectedRole,
          scope_type: selectedScopeType,
          scope_id: scopeId,
        },
      })

      const selectedMember = activeMembers.find((m) => m.user_id === selectedUserId)
      toast.success(`Role "${ROLE_LABELS[selectedRole]}" assigned to ${selectedMember?.user_email || 'user'}`)

      setSelectedUserId('')
      setSelectedRole('editor')
      setSelectedScopeType('company')
      setSelectedReportId('')
      setSelectedSectionId('')
      setIsAssignModalOpen(false)
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } } }
      toast.error(errorObj.response?.data?.detail || 'Failed to assign role')
    }
  }

  const handleDeleteRole = async (assignmentId: string, userEmail: string, role: RoleType) => {
    if (!actualCompanyId) return
    if (deleteConfirm === assignmentId) {
      try {
        await deleteRoleAssignment.mutateAsync({ companyId: actualCompanyId, assignmentId })
        toast.success(`Role "${ROLE_LABELS[role]}" removed from ${userEmail}`)
        setDeleteConfirm(null)
      } catch (err: unknown) {
        const errorObj = err as { response?: { data?: { detail?: string } } }
        toast.error(errorObj.response?.data?.detail || 'Failed to remove role')
      }
    } else {
      setDeleteConfirm(assignmentId)
      setTimeout(() => setDeleteConfirm(null), 3000)
    }
  }

  if (companyLoading) {
    return (
      <PlatformAdminLayout active="companies" title="Company roles" hint="Assign roles and scopes for a company.">
        <section className={styles.stateCard}>
          <h3 className={styles.stateTitle}>Loading…</h3>
          <p className={styles.stateText}>Please wait.</p>
        </section>
      </PlatformAdminLayout>
    )
  }

  return (
    <PlatformAdminLayout
      active="companies"
      title={company?.name ? `Roles: ${company.name}` : 'Company roles'}
      hint="Assign roles and scope access to users."
    >
      <nav className={styles.subnav} aria-label="Company admin navigation">
        <Link to="/admin/companies" className={styles.subnavLink}>
          All companies
        </Link>
        {company ? (
          <>
            <Link to={`/reports?company=${company.slug}`} className={styles.subnavLink}>
              Reports
            </Link>
            <Link to={`/admin/platform/companies/${company.slug}/members`} className={styles.subnavLink}>
              Members
            </Link>
            <Link to={`/admin/platform/companies/${company.slug}/roles`} className={styles.subnavLink} aria-current="page">
              Roles
            </Link>
          </>
        ) : null}
      </nav>

      <section className={styles.infoCard}>
        <h2 className={styles.infoTitle}>Role management</h2>
        <p className={styles.infoText}>
          Assign roles and scopes to manage access for company <strong>{company?.name || ''}</strong>.
        </p>
        <div className={styles.noteCard}>
          <strong>Scope:</strong> roles can be assigned to company, report, or a specific section.
        </div>
      </section>

      <div className={styles.pageHeader}>
        <div>
          <h2 className={styles.pageTitle}>
            Roles
            {rolesData ? <span className={styles.countBadge}>{rolesData.total}</span> : null}
          </h2>
          <p className={styles.pageHint}>One assignment per user and scope.</p>
        </div>
        <Button onClick={() => setIsAssignModalOpen(true)} disabled={!actualCompanyId}>
          Assign role
        </Button>
      </div>

      {!isLoading && !error && roles.length > 0 ? (
        <div className={styles.filtersRow}>
          <div className={styles.searchField}>
            <Input
              type="search"
              placeholder="Search by email, name, or role..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className={styles.searchMeta}>
            {searchQuery || roleFilter !== 'all'
              ? `Found: ${filteredRoles.length} of ${roles.length}`
              : null}
          </div>
        </div>
      ) : null}

      {!isLoading && !error && roles.length > 0 ? (
        <div className={styles.roleChips} style={{ marginBottom: '1rem' }}>
          <button
            type="button"
            className={`${styles.roleChip} ${roleFilter === 'all' ? styles.roleChipActive : ''}`}
            onClick={() => setRoleFilter('all')}
          >
            All
          </button>
          {uniqueRoles.map((role) => (
            <button
              key={role}
              type="button"
              className={`${styles.roleChip} ${roleFilter === role ? styles.roleChipActive : ''}`}
              onClick={() => setRoleFilter(role)}
              title={ROLE_LABELS[role] || role}
            >
              {ROLE_LABELS[role] || role}
            </button>
          ))}
        </div>
      ) : null}

      {isLoading ? (
        <section className={styles.stateCard}>
          <h3 className={styles.stateTitle}>Loading roles…</h3>
          <p className={styles.stateText}>Please wait.</p>
        </section>
      ) : error ? (
        <section className={styles.stateCard}>
          <h3 className={styles.stateTitle} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <IconAlertTriangle size={18} />
            Loading error
          </h3>
          <p className={styles.stateText}>{error instanceof Error ? error.message : 'Failed to load role assignments.'}</p>
          <div className={styles.stateActions}>
            <Button onClick={() => refetch()} variant="secondary">
              Retry
            </Button>
          </div>
        </section>
      ) : roles.length === 0 ? (
        <section className={styles.stateCard}>
          <h3 className={styles.stateTitle}>No assigned roles</h3>
          <p className={styles.stateText}>Assign roles to manage user access.</p>
          <div className={styles.stateActions}>
            <Button onClick={() => setIsAssignModalOpen(true)}>Assign role</Button>
          </div>
        </section>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Scope</th>
                <th className={styles.thRight}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredRoles.map((assignment) => (
                <tr key={assignment.assignment_id}>
                  <td>
                    <div className={styles.userEmail}>{assignment.user_email}</div>
                    <div className={styles.userName}>{assignment.user_name}</div>
                  </td>
                  <td>
                    <span className={styles.roleChip}>{ROLE_LABELS[assignment.role] || assignment.role}</span>
                  </td>
                  <td>
                    <span className={styles.scopeChip}>{SCOPE_LABELS[assignment.scope_type] || assignment.scope_type}</span>
                  </td>
                  <td className={styles.tdRight}>
                    <div className={styles.rowActions}>
                      <Button
                        size="sm"
                        variant={deleteConfirm === assignment.assignment_id ? 'danger' : 'secondary'}
                        onClick={() => handleDeleteRole(assignment.assignment_id, assignment.user_email || '', assignment.role)}
                      >
                        {deleteConfirm === assignment.assignment_id ? 'Confirm remove' : 'Remove'}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}

              {filteredRoles.length === 0 && (searchQuery || roleFilter !== 'all') ? (
                <tr>
                  <td colSpan={4} className={styles.tableEmptyCell}>
                    <span className={styles.muted}>No results</span>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      )}

      <Modal isOpen={isAssignModalOpen} onClose={() => setIsAssignModalOpen(false)} title="Assign role">
        <form onSubmit={handleAssignRole}>
          <div className={styles.modalGrid}>
            <div className={styles.modalFull}>
              <Select
                label="User (company member)"
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                options={activeMembers.map((m) => ({ value: m.user_id, label: `${m.user_email} (${m.user_name})` }))}
                placeholder="Select a user..."
                required
              />
            </div>

            <div className={styles.modalFull}>
              <Select
                label="Role"
                value={selectedRole}
                onChange={(e) => setSelectedRole(e.target.value as RoleType)}
                options={ASSIGNABLE_ROLES.map((role) => ({ value: role, label: ROLE_LABELS[role] }))}
                required
              />
            </div>

            <div className={styles.modalFull}>
              <Select
                label="Scope"
                value={selectedScopeType}
                onChange={(e) => {
                  setSelectedScopeType(e.target.value as ScopeType)
                  setSelectedReportId('')
                  setSelectedSectionId('')
                }}
                options={Object.entries(SCOPE_LABELS).map(([value, label]) => ({ value, label }))}
                required
              />
            </div>

            {selectedScopeType === 'report' || selectedScopeType === 'section' ? (
              <div className={styles.modalFull}>
                <Select
                  label="Report"
                  value={selectedReportId}
                  onChange={(e) => {
                    setSelectedReportId(e.target.value)
                    setSelectedSectionId('')
                  }}
                  options={reports.map((r) => ({ value: r.report_id, label: `${r.title} (${r.year})` }))}
                  placeholder="Select a report..."
                  required
                />
              </div>
            ) : null}

            {selectedScopeType === 'section' && selectedReportId ? (
              <div className={styles.modalFull}>
                <Select
                  label="Section"
                  value={selectedSectionId}
                  onChange={(e) => setSelectedSectionId(e.target.value)}
                  options={sections.map((s) => ({
                    value: s.section_id,
                    label: s.i18n?.[0]?.title || s.section_id.slice(0, 8),
                  }))}
                  placeholder="Select a section..."
                  required
                />
              </div>
            ) : null}
          </div>

          <div className={styles.modalActions}>
            <Button type="button" variant="secondary" onClick={() => setIsAssignModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={createRoleAssignment.isPending} disabled={!selectedUserId}>
              Assign
            </Button>
          </div>
        </form>
      </Modal>
    </PlatformAdminLayout>
  )
}

