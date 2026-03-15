import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  useCompany,
  useCompanyMemberships,
  useCreateMembership,
  useDeleteMembership,
  useUsers,
  useRoleAssignments,
  useCreateRoleAssignment,
  useDeleteRoleAssignment,
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
  translator: 'Translator',
  content_editor: 'Content Editor',
  section_editor: 'SME',
  viewer: 'Viewer',
  internal_auditor: 'Internal Auditor',
  auditor: 'Auditor',
  audit_lead: 'Audit Lead',
}

const ROLE_DESCRIPTIONS: Record<RoleType, string> = {
  corporate_lead: 'Company management, releases, audit override',
  editor: 'Full CRUD + freeze + approve',
  translator: 'Content localization and translations',
  content_editor: 'Content editing',
  section_editor: 'Subject matter expert',
  viewer: 'Read-only access',
  internal_auditor: 'Internal audit - read only',
  auditor: 'External auditor',
  audit_lead: 'Audit lead',
}

const ASSIGNABLE_ROLES: RoleType[] = [
  'corporate_lead',
  'editor',
  'content_editor',
  'section_editor',
  'viewer',
  'internal_auditor',
  'auditor',
  'audit_lead',
]

const SCOPE_LABELS: Record<ScopeType, string> = {
  company: 'Company',
  report: 'Report',
  section: 'Section',
}

export function CompanyMembersPage() {
  const params = useParams<{ companyId?: string; companySlug?: string }>()
  // Back-compat: routes use `:companySlug`, but older code referenced `:companyId`.
  const companySlug = params.companySlug ?? params.companyId

  const [searchQuery, setSearchQuery] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [selectedUserId, setSelectedUserId] = useState('')

  // Role management states
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false)
  const [selectedUserForRoles, setSelectedUserForRoles] = useState<string | null>(null)
  const [selectedRole, setSelectedRole] = useState<RoleType>('viewer')
  const [selectedScope, setSelectedScope] = useState<ScopeType>('company')
  const [selectedScopeId, setSelectedScopeId] = useState('')
  const [selectedReportId, setSelectedReportId] = useState('')
  const [deleteRoleConfirm, setDeleteRoleConfirm] = useState<string | null>(null)

  const { data: company, isLoading: companyLoading } = useCompany(companySlug || '')
  const actualCompanyId = company?.company_id || ''

  const { data: membershipsData, isLoading, error, refetch } = useCompanyMemberships(actualCompanyId)
  const { data: usersData } = useUsers()
  const { data: assignmentsData } = useRoleAssignments(actualCompanyId)
  const { data: reportsData } = useReports()
  const { data: sectionsData } = useSections(selectedReportId)

  const createMembership = useCreateMembership()
  const deleteMembership = useDeleteMembership()
  const createRoleAssignment = useCreateRoleAssignment()
  const deleteRoleAssignment = useDeleteRoleAssignment()

  const memberships = useMemo(() => membershipsData?.items ?? [], [membershipsData?.items])
  const users = useMemo(() => usersData?.items ?? [], [usersData?.items])
  const assignments = useMemo(() => assignmentsData?.items ?? [], [assignmentsData?.items])
  const reports = useMemo(() => reportsData?.items ?? [], [reportsData?.items])
  const sections = useMemo(() => sectionsData?.items ?? [], [sectionsData?.items])

  const corporateLeadCount = useMemo(() => memberships.filter((m) => m.is_corporate_lead).length, [memberships])

  const existingUserIds = useMemo(() => new Set(memberships.map((m) => m.user_id)), [memberships])
  const availableUsers = useMemo(() => users.filter((u) => !existingUserIds.has(u.user_id)), [users, existingUserIds])

  const getUserRoles = (userId: string) => {
    return assignments.filter((a) => a.user_id === userId)
  }

  const filteredMemberships = useMemo(() => {
    if (!searchQuery.trim()) return memberships
    const query = searchQuery.toLowerCase()
    return memberships.filter(
      (m) => (m.user_email || '').toLowerCase().includes(query) || (m.user_name || '').toLowerCase().includes(query)
    )
  }, [memberships, searchQuery])

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedUserId || !actualCompanyId) return

    const selectedUser = users.find((u) => u.user_id === selectedUserId)
    try {
      await createMembership.mutateAsync({
        companyId: actualCompanyId,
        data: {
          user_id: selectedUserId,
        },
      })
      toast.success(`${selectedUser?.email || 'User'} added to company`)
      setSelectedUserId('')
      setIsAddModalOpen(false)
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } } }
      toast.error(errorObj.response?.data?.detail || 'Failed to add member')
    }
  }

  const handleRemoveMember = async (userId: string, userEmail: string, memberIsCorporateLead: boolean) => {
    if (!actualCompanyId) return

    if (memberIsCorporateLead && corporateLeadCount <= 1) {
      toast.warning('Cannot remove the last Corporate Lead of the company')
      return
    }

    if (deleteConfirm === userId) {
      try {
        await deleteMembership.mutateAsync({ companyId: actualCompanyId, userId })
        toast.success(`${userEmail} removed from company`)
        setDeleteConfirm(null)
      } catch (err: unknown) {
        const errorObj = err as { response?: { data?: { detail?: string } } }
        toast.error(errorObj.response?.data?.detail || 'Failed to remove member')
      }
    } else {
      setDeleteConfirm(userId)
      setTimeout(() => setDeleteConfirm(null), 3000)
    }
  }

  const handleOpenRoleModal = (userId: string) => {
    setSelectedUserForRoles(userId)
    setIsRoleModalOpen(true)
    setSelectedRole('viewer')
    setSelectedScope('company')
    setSelectedScopeId('')
    setSelectedReportId('')
  }

  const handleAssignRole = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedUserForRoles || !actualCompanyId) return

    const selectedUser = memberships.find((m) => m.user_id === selectedUserForRoles)
    try {
      const scopeIdToSend = selectedScope === 'company' ? actualCompanyId : selectedScopeId

      await createRoleAssignment.mutateAsync({
        companyId: actualCompanyId,
        data: {
          user_id: selectedUserForRoles,
          role: selectedRole,
          scope_type: selectedScope,
          scope_id: scopeIdToSend,
        },
      })
      toast.success(`Role "${ROLE_LABELS[selectedRole]}" assigned to ${selectedUser?.user_email || 'user'}`)
      setSelectedRole('viewer')
      setSelectedScope('company')
      setSelectedScopeId('')
      setSelectedReportId('')
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } } }
      toast.error(errorObj.response?.data?.detail || 'Failed to assign role')
    }
  }

  const handleDeleteRole = async (assignmentId: string, userEmail: string, role: RoleType) => {
    if (!actualCompanyId) return
    if (deleteRoleConfirm === assignmentId) {
      try {
        await deleteRoleAssignment.mutateAsync({ companyId: actualCompanyId, assignmentId })
        toast.success(`Role "${ROLE_LABELS[role]}" removed from ${userEmail}`)
        setDeleteRoleConfirm(null)
      } catch (err: unknown) {
        const errorObj = err as { response?: { data?: { detail?: string } } }
        toast.error(errorObj.response?.data?.detail || 'Failed to remove role')
      }
    } else {
      setDeleteRoleConfirm(assignmentId)
      setTimeout(() => setDeleteRoleConfirm(null), 3000)
    }
  }

  if (companyLoading) {
    return (
      <PlatformAdminLayout active="companies" title="Company members" hint="Manage access and roles for a company.">
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
      title={company?.name ? `Members: ${company.name}` : 'Company members'}
      hint="Manage members and their role assignments."
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
            <Link to={`/admin/platform/companies/${company.slug}/members`} className={styles.subnavLink} aria-current="page">
              Members
            </Link>
            <Link to={`/admin/platform/companies/${company.slug}/roles`} className={styles.subnavLink}>
              Roles
            </Link>
          </>
        ) : null}
      </nav>

      <section className={styles.infoCard}>
        <h2 className={styles.infoTitle}>Member management</h2>
        <p className={styles.infoText}>
          Add or remove members and manage their roles and scopes for company <strong>{company?.name || ''}</strong>.
        </p>
        <ul className={styles.infoList}>
          <li>
            <strong>Add member</strong> to grant an existing platform user access to the company.
          </li>
          <li>
            <strong>Role management</strong> to assign working roles and scopes.
          </li>
          <li>
            <strong>Remove member</strong> revokes access (and removes all member roles).
          </li>
        </ul>
      </section>

      {corporateLeadCount <= 1 ? (
        <div className={styles.warningBanner}>Only one Corporate Lead remains. Assign a backup via Roles.</div>
      ) : null}

      <div className={styles.pageHeader}>
        <div>
          <h2 className={styles.pageTitle}>
            Members
            {membershipsData ? <span className={styles.countBadge}>{membershipsData.total}</span> : null}
          </h2>
          <p className={styles.pageHint}>Company membership and role assignments.</p>
        </div>
        <Button onClick={() => setIsAddModalOpen(true)} disabled={!actualCompanyId}>
          Add member
        </Button>
      </div>

      {!isLoading && !error && memberships.length > 0 ? (
        <div className={styles.filtersRow}>
          <div className={styles.searchField}>
            <Input
              type="search"
              placeholder="Search by email or name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          {searchQuery ? (
            <div className={styles.searchMeta}>
              Found: {filteredMemberships.length} of {memberships.length}
            </div>
          ) : null}
        </div>
      ) : null}

      {isLoading ? (
        <section className={styles.stateCard}>
          <h3 className={styles.stateTitle}>Loading members…</h3>
          <p className={styles.stateText}>Please wait.</p>
        </section>
      ) : error ? (
        <section className={styles.stateCard}>
          <h3 className={styles.stateTitle} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <IconAlertTriangle size={18} />
            Loading error
          </h3>
          <p className={styles.stateText}>{error instanceof Error ? error.message : 'Failed to load members'}</p>
          <div className={styles.stateActions}>
            <Button onClick={() => refetch()} variant="secondary">
              Retry
            </Button>
          </div>
        </section>
      ) : memberships.length === 0 ? (
        <section className={styles.stateCard}>
          <h3 className={styles.stateTitle}>No members</h3>
          <p className={styles.stateText}>Add members to this company.</p>
          <div className={styles.stateActions}>
            <Button onClick={() => setIsAddModalOpen(true)}>Add member</Button>
          </div>
        </section>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>User</th>
                <th>Roles</th>
                <th>Added</th>
                <th className={styles.thRight}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredMemberships.map((member) => {
                const userRoles = getUserRoles(member.user_id)
                return (
                  <tr key={member.membership_id}>
                    <td>
                      <div className={styles.userEmail}>
                        {member.user_email || member.user_id}
                        {member.is_corporate_lead ? (
                          <span className={`${styles.roleChip} ${styles.roleChipActive}`} style={{ marginLeft: 8 }}>
                            Corporate Lead
                          </span>
                        ) : null}
                      </div>
                      <div className={styles.userName}>{member.user_name}</div>
                    </td>
                    <td>
                      {userRoles.length === 0 ? (
                        <span className={styles.muted}>No roles</span>
                      ) : (
                        <div className={styles.roleChips}>
                          {userRoles.map((assignment) => (
                            <span
                              key={assignment.assignment_id}
                              className={styles.roleChip}
                              title={assignment.scope_type !== 'company' ? SCOPE_LABELS[assignment.scope_type] : undefined}
                            >
                              {ROLE_LABELS[assignment.role]}
                              {assignment.scope_type !== 'company' ? ` (${SCOPE_LABELS[assignment.scope_type]})` : ''}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td>{new Date(member.created_at_utc).toLocaleDateString('en-GB')}</td>
                    <td className={styles.tdRight}>
                      <div className={styles.rowActions}>
                        <Button size="sm" variant="secondary" onClick={() => handleOpenRoleModal(member.user_id)}>
                          Roles
                        </Button>
                        <Button
                          size="sm"
                          variant={deleteConfirm === member.user_id ? 'danger' : 'secondary'}
                          onClick={() =>
                            handleRemoveMember(member.user_id, member.user_email || '', Boolean(member.is_corporate_lead))
                          }
                        >
                          {deleteConfirm === member.user_id ? 'Confirm remove' : 'Remove'}
                        </Button>
                      </div>
                    </td>
                  </tr>
                )
              })}

              {filteredMemberships.length === 0 && searchQuery ? (
                <tr>
                  <td colSpan={4} className={styles.tableEmptyCell}>
                    <span className={styles.muted}>No results for "{searchQuery}"</span>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        isOpen={isAddModalOpen}
        onClose={() => {
          setIsAddModalOpen(false)
          setSelectedUserId('')
        }}
        title="Add member"
      >
        <form onSubmit={handleAddMember}>
          <div className={styles.modalGrid}>
            <div className={styles.modalFull}>
              <Select
                label="User"
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                options={availableUsers.map((u) => ({ value: u.user_id, label: `${u.email} (${u.full_name})` }))}
                placeholder="Select a user..."
                required
              />
              {availableUsers.length === 0 ? <p className={styles.muted}>All users are already members.</p> : null}
            </div>
          </div>

          <div className={styles.modalActions}>
            <Button type="button" variant="secondary" onClick={() => setIsAddModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={createMembership.isPending} disabled={!selectedUserId}>
              Add
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isRoleModalOpen}
        onClose={() => {
          setIsRoleModalOpen(false)
          setSelectedUserForRoles(null)
        }}
        title={`Role management: ${memberships.find((m) => m.user_id === selectedUserForRoles)?.user_email || ''}`}
      >
        <div>
          <div>
            <h3 className={styles.infoTitle}>Current roles</h3>
            {selectedUserForRoles && getUserRoles(selectedUserForRoles).length === 0 ? (
              <p className={styles.muted}>No assigned roles.</p>
            ) : (
              <div className={styles.roleList}>
                {selectedUserForRoles
                  ? getUserRoles(selectedUserForRoles).map((assignment) => (
                      <div key={assignment.assignment_id} className={styles.roleRow}>
                        <div className={styles.roleRowMeta}>
                          <span className={styles.roleChip}>{ROLE_LABELS[assignment.role]}</span>
                          <span className={styles.scopeChip}>{SCOPE_LABELS[assignment.scope_type]}</span>
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          variant={deleteRoleConfirm === assignment.assignment_id ? 'danger' : 'secondary'}
                          onClick={() =>
                            handleDeleteRole(
                              assignment.assignment_id,
                              memberships.find((m) => m.user_id === selectedUserForRoles)?.user_email || '',
                              assignment.role
                            )
                          }
                        >
                          {deleteRoleConfirm === assignment.assignment_id ? 'Confirm' : 'Remove'}
                        </Button>
                      </div>
                    ))
                  : null}
              </div>
            )}
          </div>

          <hr className={styles.divider} />

          <form onSubmit={handleAssignRole}>
            <h3 className={styles.infoTitle}>Assign a new role</h3>

            {selectedUserForRoles && getUserRoles(selectedUserForRoles).length > 0 ? (
              <div className={styles.warningBanner}>
                Note: assigning a new role may replace existing roles depending on server rules.
              </div>
            ) : null}

            <div className={styles.modalGrid}>
              <div className={styles.modalFull}>
                <Select
                  label="Role"
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value as RoleType)}
                  options={ASSIGNABLE_ROLES.map((role) => ({ value: role, label: ROLE_LABELS[role] }))}
                  required
                />
                <div className={`${styles.muted} ${styles.roleDesc}`}>{ROLE_DESCRIPTIONS[selectedRole]}</div>
              </div>

              <div className={styles.modalFull}>
                <Select
                  label="Scope"
                  value={selectedScope}
                  onChange={(e) => {
                    setSelectedScope(e.target.value as ScopeType)
                    setSelectedScopeId('')
                    setSelectedReportId('')
                  }}
                  options={Object.entries(SCOPE_LABELS).map(([value, label]) => ({ value, label }))}
                  required
                />
              </div>

              {selectedScope === 'report' ? (
                <div className={styles.modalFull}>
                  <Select
                    label="Report"
                    value={selectedScopeId}
                    onChange={(e) => setSelectedScopeId(e.target.value)}
                    options={reports.map((r) => ({ value: r.report_id, label: `${r.title} (${r.year})` }))}
                    placeholder="Select a report..."
                    required
                  />
                </div>
              ) : null}

              {selectedScope === 'section' ? (
                <>
                  <div className={styles.modalFull}>
                    <Select
                      label="Report"
                      value={selectedReportId}
                      onChange={(e) => {
                        setSelectedReportId(e.target.value)
                        setSelectedScopeId('')
                      }}
                      options={reports.map((r) => ({ value: r.report_id, label: `${r.title} (${r.year})` }))}
                      placeholder="Select a report..."
                      required
                    />
                  </div>
                  {selectedReportId ? (
                    <div className={styles.modalFull}>
                      <Select
                        label="Section"
                        value={selectedScopeId}
                        onChange={(e) => setSelectedScopeId(e.target.value)}
                        options={sections.map((s) => {
                          const title = s.i18n?.[0]?.title || `Section ${s.order_index + 1}`
                          const label = `${s.label_prefix ? `${s.label_prefix} ` : ''}${title}`
                          return { value: s.section_id, label }
                        })}
                        placeholder="Select a section..."
                        required
                      />
                    </div>
                  ) : null}
                </>
              ) : null}
            </div>

            <div className={styles.modalActions}>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setIsRoleModalOpen(false)
                  setSelectedUserForRoles(null)
                }}
              >
                Close
              </Button>
              <Button
                type="submit"
                loading={createRoleAssignment.isPending}
                disabled={selectedScope !== 'company' && !selectedScopeId}
              >
                Assign role
              </Button>
            </div>
          </form>
        </div>
      </Modal>
    </PlatformAdminLayout>
  )
}

