import { useMemo, useState } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { useCreateUser, useDeleteUser, useUpdateUser, useUsers } from '@/api/hooks'
import {
  Button,
  IconAlertTriangle,
  IconLightbulb,
  IconLock,
  IconPencil,
  IconSearch,
  IconTrash,
  IconUser,
  Input,
  Modal,
  toast,
} from '@/components/ui'
import type { User } from '@/types/api'
import { PlatformAdminLayout } from './PlatformAdminLayout'
import adminStyles from './MyCompanyAdmin.module.css'

export function UsersPage() {
  const currentUser = useAuthStore((s) => s.user)

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Create form state
  const [newEmail, setNewEmail] = useState('')
  const [newFullName, setNewFullName] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newIsSuperuser, setNewIsSuperuser] = useState(false)

  // Edit form state
  const [editEmail, setEditEmail] = useState('')
  const [editFullName, setEditFullName] = useState('')
  const [editPassword, setEditPassword] = useState('')
  const [editIsActive, setEditIsActive] = useState(true)
  const [editIsSuperuser, setEditIsSuperuser] = useState(false)

  const { data: usersData, isLoading, error, refetch } = useUsers()
  const createUser = useCreateUser()
  const updateUser = useUpdateUser()
  const deleteUser = useDeleteUser()

  const users = useMemo(() => usersData?.items ?? [], [usersData?.items])

  const filteredUsers = useMemo(() => {
    if (!searchQuery.trim()) return users
    const query = searchQuery.toLowerCase()
    return users.filter(
      (u) =>
        u.email.toLowerCase().includes(query) ||
        u.full_name.toLowerCase().includes(query) ||
        (u.is_superuser && 'superuser'.includes(query))
    )
  }, [users, searchQuery])

  const resetCreateForm = () => {
    setNewEmail('')
    setNewFullName('')
    setNewPassword('')
    setNewIsSuperuser(false)
  }

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newEmail.trim() || !newFullName.trim() || !newPassword.trim()) return

    // Client-side password validation
    if (newPassword.length < 12) {
      toast.error('Password must be at least 12 characters long')
      return
    }
    if (!/[A-Z]/.test(newPassword)) {
      toast.error('Password must include at least one uppercase letter')
      return
    }
    if (!/[a-z]/.test(newPassword)) {
      toast.error('Password must include at least one lowercase letter')
      return
    }
    if (!/[0-9]/.test(newPassword)) {
      toast.error('Password must include at least one digit')
      return
    }
    if (!/[^A-Za-z0-9]/.test(newPassword)) {
      toast.error('Password must include at least one special character')
      return
    }

    try {
      await createUser.mutateAsync({
        email: newEmail.trim(),
        full_name: newFullName.trim(),
        password: newPassword,
        is_superuser: newIsSuperuser,
      })
      toast.success(`User "${newEmail}" created`)
      resetCreateForm()
      setIsCreateModalOpen(false)
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create user'
      toast.error(errorMessage)
      console.error('Failed to create user:', err)
    }
  }

  const openEditModal = (user: User) => {
    setEditingUser(user)
    setEditEmail(user.email)
    setEditFullName(user.full_name)
    setEditPassword('')
    setEditIsActive(user.is_active)
    setEditIsSuperuser(user.is_superuser)
  }

  const handleEditUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingUser) return

    try {
      const updateData: {
        email?: string
        full_name?: string
        password?: string
        is_active?: boolean
        is_superuser?: boolean
      } = {}

      if (editEmail !== editingUser.email) updateData.email = editEmail
      if (editFullName !== editingUser.full_name) updateData.full_name = editFullName
      if (editPassword) updateData.password = editPassword
      if (editIsActive !== editingUser.is_active) updateData.is_active = editIsActive
      if (editIsSuperuser !== editingUser.is_superuser) updateData.is_superuser = editIsSuperuser

      await updateUser.mutateAsync({
        userId: editingUser.user_id,
        data: updateData,
      })
      toast.success(`User "${editEmail}" updated`)
      setEditingUser(null)
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update user'
      toast.error(errorMessage)
      console.error('Failed to update user:', err)
    }
  }

  const handleDeleteUser = async (userId: string, userEmail: string) => {
    if (deleteConfirm === userId) {
      try {
        await deleteUser.mutateAsync(userId)
        toast.success(`User "${userEmail}" deleted`)
        setDeleteConfirm(null)
      } catch (err: unknown) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to delete user'
        toast.error(errorMessage)
        console.error('Failed to delete user:', err)
      }
    } else {
      setDeleteConfirm(userId)
      setTimeout(() => setDeleteConfirm(null), 5000) // confirmation window
    }
  }

  return (
    <>
      <PlatformAdminLayout
        active="users"
        title="Users"
        hint="Create users, grant superuser, disable access."
      >
        <div className={adminStyles.pageHeader}>
          <div>
            <h2 className={adminStyles.pageTitle}>
              Users
              {usersData ? <span className={adminStyles.countBadge}>{usersData.total}</span> : null}
            </h2>
            <p className={adminStyles.pageHint}>Search by email, name, or superuser.</p>
          </div>
          <Button onClick={() => setIsCreateModalOpen(true)}>Create user</Button>
        </div>

        {!isLoading && !error && users.length > 0 ? (
          <div className={adminStyles.filtersRow}>
            <div className={adminStyles.searchField}>
              <Input
                placeholder="Search by email, name, or superuser..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <div className={adminStyles.searchMeta}>
              {searchQuery ? `Found: ${filteredUsers.length} of ${users.length}` : null}
            </div>
          </div>
        ) : null}

        {isLoading ? (
          <div className={adminStyles.stateCard}>
            <h3 className={adminStyles.stateTitle}>Loading</h3>
            <p className={adminStyles.stateText}>Loading users...</p>
          </div>
        ) : null}

        {error ? (
          <div className={adminStyles.stateCard}>
            <h3 className={adminStyles.stateTitle} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconAlertTriangle size={18} />
              Loading error
            </h3>
            <p className={adminStyles.stateText}>
              {error instanceof Error ? error.message : 'Failed to load users'}
            </p>
            <div className={adminStyles.stateActions}>
              <Button onClick={() => refetch()} variant="secondary">
                Retry
              </Button>
            </div>
          </div>
        ) : null}

        {!isLoading && !error && users.length === 0 ? (
          <div className={adminStyles.stateCard}>
            <h3 className={adminStyles.stateTitle} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconUser size={18} />
              No users
            </h3>
            <p className={adminStyles.stateText}>Create your first user.</p>
            <div className={adminStyles.stateActions}>
              <Button onClick={() => setIsCreateModalOpen(true)}>Create user</Button>
            </div>
          </div>
        ) : null}

        {!isLoading && !error && users.length > 0 ? (
          <div className={adminStyles.tableWrap}>
            <table className={adminStyles.table}>
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Name</th>
                  <th>Status</th>
                  <th className={adminStyles.thRight}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((user) => (
                  <tr key={user.user_id}>
                    <td>
                      <span className={adminStyles.userEmail}>{user.email}</span>
                      {user.is_superuser ? (
                        <span style={{ marginLeft: 8 }} className={adminStyles.countBadge}>
                          superuser
                        </span>
                      ) : null}
                    </td>
                    <td>{user.full_name}</td>
                    <td>{user.is_active ? 'Active' : 'Disabled'}</td>
                    <td className={adminStyles.tdRight}>
                      <div style={{ display: 'inline-flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                        <Button variant="secondary" size="sm" onClick={() => openEditModal(user)}>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                            <IconPencil size={14} />
                            Edit
                          </span>
                        </Button>
                        {user.user_id !== currentUser?.userId ? (
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => handleDeleteUser(user.user_id, user.email)}
                          >
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                              {deleteConfirm === user.user_id ? <IconAlertTriangle size={14} /> : <IconTrash size={14} />}
                              {deleteConfirm === user.user_id ? 'Confirm delete' : 'Delete'}
                            </span>
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredUsers.length === 0 && searchQuery ? (
                  <tr>
                    <td colSpan={4} style={{ padding: '1.5rem' }}>
                      <div style={{ color: '#64748b' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                          <IconSearch size={16} />
                          No results for "{searchQuery}"
                        </span>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        ) : null}
      </PlatformAdminLayout>

      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => {
          setIsCreateModalOpen(false)
          resetCreateForm()
        }}
        title="Create user"
      >
        <form onSubmit={handleCreateUser} className={adminStyles.stateCard}>
          <Input
            label="Email"
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder="user@example.com"
            required
          />
          <Input
            label="Full name"
            value={newFullName}
            onChange={(e) => setNewFullName(e.target.value)}
            placeholder="John Smith"
            required
          />
          <Input
            label="Password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Min. 12 chars, A-Z, a-z, 0-9, special char"
            required
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontWeight: 700, color: '#0f172a' }}>
            <input
              type="checkbox"
              checked={newIsSuperuser}
              onChange={(e) => setNewIsSuperuser(e.target.checked)}
            />
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
              <IconLock size={16} />
              Superuser (full platform access)
            </span>
          </label>

          <div className={adminStyles.infoCard} style={{ margin: 0 }}>
            <p className={adminStyles.infoText} style={{ margin: 0 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <IconLightbulb size={16} />
                <strong>How roles work:</strong>
              </span>
              <br />
              1. Create a user here
              <br />
              2. Add them to a company (Companies → Members)
              <br />
              3. Assign a role in the company (Companies → Roles)
            </p>
          </div>

          <div className={adminStyles.stateActions}>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setIsCreateModalOpen(false)
                resetCreateForm()
              }}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createUser.isPending}>
              {createUser.isPending ? 'Creating...' : 'Create'}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={!!editingUser}
        onClose={() => setEditingUser(null)}
        title="Edit user"
      >
        <form onSubmit={handleEditUser} className={adminStyles.stateCard}>
          <Input
            label="Email"
            type="email"
            value={editEmail}
            onChange={(e) => setEditEmail(e.target.value)}
            placeholder="user@example.com"
            required
          />
          <Input
            label="Full name"
            value={editFullName}
            onChange={(e) => setEditFullName(e.target.value)}
            placeholder="John Smith"
            required
          />
          <Input
            label="New password (leave empty to keep current)"
            type="password"
            value={editPassword}
            onChange={(e) => setEditPassword(e.target.value)}
            placeholder="Min. 12 chars..."
          />

          <div className={adminStyles.infoCard} style={{ margin: 0 }}>
            <p className={adminStyles.infoText} style={{ margin: 0 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <IconLightbulb size={16} />
                <strong>Roles are assigned via company:</strong>
              </span>
              <br />
              Companies → Members → Roles
            </p>
          </div>

          <div>
            <label style={{ display: 'block', fontWeight: 700, marginBottom: '0.35rem', color: '#0f172a' }}>Status</label>
            <select
              value={editIsActive ? 'active' : 'disabled'}
              onChange={(e) => setEditIsActive(e.target.value === 'active')}
              style={{
                width: '100%',
                padding: '0.625rem 0.75rem',
                borderRadius: '10px',
                border: '1px solid rgba(15, 23, 42, 0.12)',
                background: '#ffffff',
              }}
            >
              <option value="active">Active</option>
              <option value="disabled">Disabled</option>
            </select>
          </div>

          <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontWeight: 700, color: '#0f172a' }}>
            <input
              type="checkbox"
              checked={editIsSuperuser}
              onChange={(e) => setEditIsSuperuser(e.target.checked)}
            />
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
              <IconLock size={16} />
              Superuser (full platform access)
            </span>
          </label>

          <div className={adminStyles.stateActions}>
            <Button type="button" variant="secondary" onClick={() => setEditingUser(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateUser.isPending}>
              {updateUser.isPending ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  )
}

