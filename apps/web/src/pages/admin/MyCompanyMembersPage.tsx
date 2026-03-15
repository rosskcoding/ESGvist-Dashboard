import { useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { AppHeader } from '@/components/layout/AppHeader'
import dashboardStyles from '@/pages/DashboardPage.module.css'
import {
  useCompanyMemberships,
  useCreateMembership,
  useCreateAndAddMember,
  useUpdateMembership,
  useDeleteMembership,
  useUsers,
  useRoleAssignments,
  useCreateRoleAssignment,
  useDeleteRoleAssignment,
  useReports,
  useSections,
} from '@/api/hooks'
import { Button, Input, Modal, Select, toast } from '@/components/ui'
import type { RoleType, ScopeType } from '@/types/api'
import styles from './MyCompanyAdmin.module.css'

// Role labels
const ROLE_LABELS: Record<RoleType, string> = {
  corporate_lead: 'Corporate Lead',
  editor: 'Editor in Chief',
  translator: 'Translator',
  content_editor: 'Editor',
  section_editor: 'SME (expert)',
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

export function MyCompanyMembersPage() {
  const user = useAuthStore((s) => s.user)
  const memberships = useMemo(() => user?.memberships ?? [], [user?.memberships])

  const adminMembership = useMemo(() => {
    return memberships.find((m) => m.isActive && m.isCorporateLead)
  }, [memberships])

  const companyId = adminMembership?.companyId || ''
  const companyName = adminMembership?.companyName || ''

  const [searchQuery, setSearchQuery] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [editingUserId, setEditingUserId] = useState<string | null>(null)
  const [editUserFullName, setEditUserFullName] = useState('')
  // Automatically switch to 'new' when no users are available
  const [addMode, setAddMode] = useState<'existing' | 'new'>('new')
  const [selectedUserId, setSelectedUserId] = useState('')
  const [newUserEmail, setNewUserEmail] = useState('')
  const [newUserFullName, setNewUserFullName] = useState('')
  const [newUserPassword, setNewUserPassword] = useState('')

  // Role management states
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false)
  const [selectedUserForRoles, setSelectedUserForRoles] = useState<string | null>(null)
  const [selectedRole, setSelectedRole] = useState<RoleType>('viewer')
  const [selectedScope, setSelectedScope] = useState<ScopeType>('company')
  const [selectedScopeId, setSelectedScopeId] = useState('')
  const [selectedReportId, setSelectedReportId] = useState('')
  const [deleteRoleConfirm, setDeleteRoleConfirm] = useState<string | null>(null)

  const { data: membersData, isLoading, error, refetch } = useCompanyMemberships(companyId)
  const { data: usersData } = useUsers()
  const { data: rolesData } = useRoleAssignments(companyId)
  const { data: reportsData } = useReports()
  const { data: sectionsData } = useSections(selectedReportId)

  const createMembership = useCreateMembership()
  const createAndAddMember = useCreateAndAddMember()
  const updateMembership = useUpdateMembership()
  const deleteMembership = useDeleteMembership()
  const createRoleAssignment = useCreateRoleAssignment()
  const deleteRoleAssignment = useDeleteRoleAssignment()

  const allUsers = useMemo(() => usersData?.items ?? [], [usersData?.items])
  const assignments = useMemo(() => rolesData?.items ?? [], [rolesData?.items])
  const reports = useMemo(() => reportsData?.items ?? [], [reportsData?.items])
  const sections = useMemo(() => sectionsData?.items ?? [], [sectionsData?.items])

  const members = useMemo(() => membersData?.items ?? [], [membersData?.items])

  const corporateLeadCount = useMemo(() => members.filter((m) => m.is_corporate_lead).length, [members])

  // Users not yet members of this company
  const existingUserIds = new Set(members.map((m) => m.user_id))
  const availableUsers = allUsers.filter((u) => !existingUserIds.has(u.user_id))

  // Get roles for a user
  const getUserRoles = (userId: string) => {
    return assignments.filter((a) => a.user_id === userId)
  }

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault()

    if (addMode === 'new') {
      // Create a new user and add to company
      if (!newUserEmail || !newUserFullName || !newUserPassword || !companyId) {
        toast.error('Fill in all required fields')
        return
      }

      try {
        // Create user and add to company in one request
        await createAndAddMember.mutateAsync({
          companyId,
          data: {
            email: newUserEmail,
            full_name: newUserFullName,
            password: newUserPassword,
          },
        })

        toast.success(`${newUserEmail} created and added to company`)
        setNewUserEmail('')
        setNewUserFullName('')
        setNewUserPassword('')
        setIsAddModalOpen(false)
      } catch (err) {
        console.error('Error creating user:', err)
        const error = err as { response?: { data?: { detail?: string } } }
        toast.error(error.response?.data?.detail || 'Failed to create user')
      }
    } else {
      // Add existing user
      if (!selectedUserId || !companyId) {
        toast.error('Error: user or company is not selected')
        return
      }

      const selectedUser = allUsers.find((u) => u.user_id === selectedUserId)

      try {
        await createMembership.mutateAsync({
          companyId,
          data: { user_id: selectedUserId },
        })
        toast.success(`${selectedUser?.email || 'User'} added to company`)
        setSelectedUserId('')
        setIsAddModalOpen(false)
      } catch (err) {
        console.error('Error adding member:', err)
        const error = err as { response?: { data?: { detail?: string } } }
        toast.error(error.response?.data?.detail || 'Failed to add member')
      }
    }
  }

  const filteredMembers = useMemo(() => {
    if (!searchQuery.trim()) return members
    const query = searchQuery.toLowerCase()
    return members.filter(
      (m) =>
        (m.user_email || '').toLowerCase().includes(query) ||
        (m.user_name || '').toLowerCase().includes(query)
    )
  }, [members, searchQuery])

  if (!adminMembership) {
    return <Navigate to="/reports" replace />
  }

  const handleRemoveMember = async (
    userId: string,
    userEmail: string,
    memberIsCorporateLead: boolean
  ) => {
    if (memberIsCorporateLead && corporateLeadCount <= 1) {
      toast.warning('Cannot remove the last Corporate Lead')
      return
    }

    if (deleteConfirm === userId) {
      try {
        await deleteMembership.mutateAsync({ companyId, userId })
        toast.success(`${userEmail} removed from company`)
        setDeleteConfirm(null)
      } catch (err: unknown) {
        const error = err as { response?: { data?: { detail?: string } } }
        toast.error(error.response?.data?.detail || 'Failed to remove member')
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
    if (!selectedUserForRoles || !companyId) return

    const selectedUser = members.find((m) => m.user_id === selectedUserForRoles)
    try {
      const scopeIdToSend = selectedScope === 'company' ? companyId : selectedScopeId

      await createRoleAssignment.mutateAsync({
        companyId,
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
    } catch (err) {
      const error = err as { response?: { data?: { detail?: string } } }
      toast.error(error.response?.data?.detail || 'Failed to assign role')
    }
  }

  const handleDeleteRole = async (assignmentId: string, userEmail: string, role: RoleType) => {
    if (deleteRoleConfirm === assignmentId) {
      try {
        await deleteRoleAssignment.mutateAsync({ companyId, assignmentId })
        toast.success(`Role "${ROLE_LABELS[role]}" removed from ${userEmail}`)
        setDeleteRoleConfirm(null)
      } catch (err) {
        const error = err as { response?: { data?: { detail?: string } } }
        toast.error(error.response?.data?.detail || 'Failed to remove role')
      }
    } else {
      setDeleteRoleConfirm(assignmentId)
      setTimeout(() => setDeleteRoleConfirm(null), 3000)
    }
  }

  const handleOpenEditModal = (userId: string, currentFullName: string) => {
    setEditingUserId(userId)
    setEditUserFullName(currentFullName)
    setIsEditModalOpen(true)
  }

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingUserId || !editUserFullName || !companyId) return

    const member = members.find((m) => m.user_id === editingUserId)
    try {
      await updateMembership.mutateAsync({
        companyId,
        userId: editingUserId,
        data: {
          full_name: editUserFullName,
        },
      })
      toast.success(`User data updated: ${member?.user_email || ''}`)
      setIsEditModalOpen(false)
      setEditingUserId(null)
      setEditUserFullName('')
    } catch (err) {
      const error = err as { response?: { data?: { detail?: string } } }
      toast.error(error.response?.data?.detail || 'Failed to update data')
    }
  }

  return (
    <div className={dashboardStyles.container}>
      <AppHeader />

      <main className={dashboardStyles.main}>
        <div className={styles.hero}>
          <div className={styles.heroTop}>
            <h1 className={styles.companyName}>{companyName}</h1>
            <span className={styles.roleBadge}>Corporate Lead</span>
          </div>
          <p className={styles.heroText}>Manage the team and access to company reports.</p>
        </div>

        <nav className={styles.subnav} aria-label="Company admin navigation">
          <Link to="/company" className={styles.subnavLink}>
            Overview
          </Link>
          <Link to="/company/members" className={styles.subnavLink} aria-current="page">
            Members
          </Link>
          <Link to="/company/roles" className={styles.subnavLink}>
            Roles
          </Link>
        </nav>

        <section className={styles.infoCard}>
          <h2 className={styles.infoTitle}>Member management</h2>
          <p className={styles.infoText}>
            As a <strong>Corporate Lead</strong>, you manage the team and access to company reports.
          </p>
          <ul className={styles.infoList}>
            <li>
              <strong>Add member</strong> to grant an existing platform user access to the company.
            </li>
            <li>
              <strong>Role management</strong> to assign working roles and scopes.
            </li>
            <li>
              <strong>Remove member</strong> to revoke company access (removes all member roles).
            </li>
          </ul>
        </section>

        {corporateLeadCount <= 1 && (
          <div className={styles.warningBanner}>Only one Corporate Lead remains. Assign a backup via Roles.</div>
        )}

        <div className={styles.pageHeader}>
          <div>
            <h2 className={styles.pageTitle}>
              Members
              {membersData ? <span className={styles.countBadge}>{membersData.total}</span> : null}
            </h2>
            <p className={styles.pageHint}>Company membership and role assignments.</p>
          </div>
          <Button
            onClick={() => {
              setAddMode(availableUsers.length > 0 ? 'existing' : 'new')
              setIsAddModalOpen(true)
            }}
          >
            Add member
          </Button>
        </div>

        {!isLoading && !error && members.length > 0 && (
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
                Found: {filteredMembers.length} of {members.length}
              </div>
            ) : null}
          </div>
        )}

        {isLoading ? (
          <section className={styles.stateCard}>
            <h3 className={styles.stateTitle}>Loading members…</h3>
            <p className={styles.stateText}>Please wait.</p>
          </section>
        ) : error ? (
          <section className={styles.stateCard}>
            <h3 className={styles.stateTitle}>Loading error</h3>
            <p className={styles.stateText}>{error instanceof Error ? error.message : 'Failed to load members'}</p>
            <div className={styles.stateActions}>
              <Button onClick={() => refetch()} variant="secondary">
                Retry
              </Button>
            </div>
          </section>
        ) : members.length === 0 ? (
          <section className={styles.stateCard}>
            <h3 className={styles.stateTitle}>No members</h3>
            <p className={styles.stateText}>Add members to your company.</p>
            <div className={styles.stateActions}>
              <Button
                onClick={() => {
                  setAddMode(availableUsers.length > 0 ? 'existing' : 'new')
                  setIsAddModalOpen(true)
                }}
              >
                Add member
              </Button>
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
                {filteredMembers.map((member) => {
                  const userRoles = getUserRoles(member.user_id)
                  const isCurrentUser = member.user_id === user?.userId

                  return (
                    <tr key={member.membership_id}>
                        <td>
                          <div className={styles.userEmail}>
                            {member.user_email || member.user_id}
                            {isCurrentUser ? (
                              <span className={styles.youBadge}>
                                (You)
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
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={isCurrentUser}
                            title={isCurrentUser ? 'You cannot change your own roles' : undefined}
                            onClick={() => handleOpenRoleModal(member.user_id)}
                          >
                            Roles
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => handleOpenEditModal(member.user_id, member.user_name || '')}
                          >
                            {isCurrentUser ? 'My profile' : 'Edit'}
                          </Button>
                          <Button
                            size="sm"
                            variant={deleteConfirm === member.user_id ? 'danger' : 'secondary'}
                            disabled={isCurrentUser}
                            title={isCurrentUser ? 'You cannot remove yourself from the company' : undefined}
                            onClick={() =>
                              handleRemoveMember(member.user_id, member.user_email || '', member.is_corporate_lead || false)
                            }
                          >
                            {deleteConfirm === member.user_id ? 'Confirm remove' : 'Remove'}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )
                })}

                  {filteredMembers.length === 0 && searchQuery ? (
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
      </main>

      {/* Add Member Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => {
          setIsAddModalOpen(false)
          setAddMode(availableUsers.length > 0 ? 'existing' : 'new')
          setSelectedUserId('')
          setNewUserEmail('')
          setNewUserFullName('')
          setNewUserPassword('')
        }}
        title="Add member"
      >
        <form onSubmit={handleAddMember}>
          {availableUsers.length > 0 && (
            <div className={styles.segmented}>
              <Button
                type="button"
                size="sm"
                variant={addMode === 'existing' ? 'primary' : 'secondary'}
                onClick={() => setAddMode('existing')}
              >
                Existing user
              </Button>
              <Button type="button" size="sm" variant={addMode === 'new' ? 'primary' : 'secondary'} onClick={() => setAddMode('new')}>
                Create new
              </Button>
            </div>
          )}

          <div className={styles.modalGrid}>
            {addMode === 'existing' ? (
              <div className={styles.modalFull}>
                <Select
                  label="User"
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(e.target.value)}
                  options={availableUsers.map((u) => ({ value: u.user_id, label: `${u.email} (${u.full_name})` }))}
                  placeholder="Select a user..."
                  required
                />
              </div>
            ) : (
              <>
                <div className={styles.modalFull}>
                  <Input
                    label="Email"
                    type="email"
                    value={newUserEmail}
                    onChange={(e) => setNewUserEmail(e.target.value)}
                    placeholder="user@example.com"
                    required
                  />
                </div>
                <div className={styles.modalFull}>
                  <Input
                    label="Full name"
                    type="text"
                    value={newUserFullName}
                    onChange={(e) => setNewUserFullName(e.target.value)}
                    placeholder="John Smith"
                    required
                  />
                </div>
                <div className={styles.modalFull}>
                  <Input
                    label="Password"
                    type="password"
                    value={newUserPassword}
                    onChange={(e) => setNewUserPassword(e.target.value)}
                    placeholder="Minimum 12 characters"
                    required
                    minLength={12}
                    hint="At least 12 chars: letters, digits, special characters"
                  />
                </div>
              </>
            )}
          </div>

          <div className={styles.noteCard}>
            After adding a member, assign roles via <strong>Roles</strong>.
          </div>

          <div className={styles.modalActions}>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setIsAddModalOpen(false)
                setAddMode(availableUsers.length > 0 ? 'existing' : 'new')
                setSelectedUserId('')
                setNewUserEmail('')
                setNewUserFullName('')
                setNewUserPassword('')
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              loading={createMembership.isPending || createAndAddMember.isPending}
              disabled={
                (addMode === 'existing' && !selectedUserId) ||
                (addMode === 'new' && (!newUserEmail || !newUserFullName || !newUserPassword))
              }
            >
              {addMode === 'new' ? 'Create and add' : 'Add'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit User Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false)
          setEditingUserId(null)
          setEditUserFullName('')
        }}
        title={editingUserId === user?.userId ? 'My profile' : 'Edit member'}
      >
        <form onSubmit={handleUpdateUser}>
          <div className={styles.modalGrid}>
            <div className={styles.modalFull}>
              <Input
                label="Email"
                type="text"
                value={members.find((m) => m.user_id === editingUserId)?.user_email || ''}
                disabled
                hint="Email cannot be changed"
              />
            </div>
            <div className={styles.modalFull}>
              <Input
                label="Full name"
                type="text"
                value={editUserFullName}
                onChange={(e) => setEditUserFullName(e.target.value)}
                placeholder="John Smith"
                required
              />
            </div>
          </div>

          <div className={styles.modalActions}>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setIsEditModalOpen(false)
                setEditingUserId(null)
                setEditUserFullName('')
              }}
            >
              Cancel
            </Button>
            <Button type="submit" loading={updateMembership.isPending} disabled={!editUserFullName}>
              Save
            </Button>
          </div>
        </form>
      </Modal>

      {/* Role Management Modal */}
      <Modal
        isOpen={isRoleModalOpen}
        onClose={() => {
          setIsRoleModalOpen(false)
          setSelectedUserForRoles(null)
        }}
        title={`Role management: ${members.find(m => m.user_id === selectedUserForRoles)?.user_email || ''}`}
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
                              members.find((m) => m.user_id === selectedUserForRoles)?.user_email || '',
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
                  <div className={`${styles.muted} ${styles.roleDesc}`}>
                    {ROLE_DESCRIPTIONS[selectedRole]}
                  </div>
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
    </div>
  )
}
