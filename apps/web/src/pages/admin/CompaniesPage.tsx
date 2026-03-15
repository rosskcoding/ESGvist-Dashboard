import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useCompanies, useCreateCompany, useUpdateCompany, useDeleteCompany } from '@/api/hooks'
import {
  Button,
  IconAlertTriangle,
  IconBuilding,
  IconPencil,
  IconSearch,
  IconSettings,
  IconTrash,
  IconUsers,
  Input,
  Modal,
  toast,
} from '@/components/ui'
import type { Company } from '@/types/api'
import { PlatformAdminLayout } from './PlatformAdminLayout'
import adminStyles from './MyCompanyAdmin.module.css'

export function CompaniesPage() {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [newCompanyName, setNewCompanyName] = useState('')
  const [editingCompany, setEditingCompany] = useState<Company | null>(null)
  const [editName, setEditName] = useState('')
  const [editStatus, setEditStatus] = useState<'active' | 'disabled'>('active')
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  const { data: companiesData, isLoading, error, refetch } = useCompanies()
  const createCompany = useCreateCompany()
  const updateCompany = useUpdateCompany()
  const deleteCompany = useDeleteCompany()

  const companies = useMemo(() => companiesData?.items ?? [], [companiesData?.items])

  // Filtered companies based on search
  const filteredCompanies = useMemo(() => {
    if (!searchQuery.trim()) return companies
    const query = searchQuery.toLowerCase()
    return companies.filter(
      (c) =>
        c.name.toLowerCase().includes(query) ||
        c.status.toLowerCase().includes(query)
    )
  }, [companies, searchQuery])

  const handleCreateCompany = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newCompanyName.trim()) return

    try {
      await createCompany.mutateAsync({ name: newCompanyName.trim() })
      toast.success(`Company "${newCompanyName.trim()}" created successfully`)
      setNewCompanyName('')
      setIsCreateModalOpen(false)
    } catch (err) {
      toast.error('Failed to create company')
      console.error('Failed to create company:', err)
    }
  }

  const openEditModal = (company: Company) => {
    setEditingCompany(company)
    setEditName(company.name)
    setEditStatus(company.status as 'active' | 'disabled')
  }

  const handleEditCompany = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingCompany || !editName.trim()) return

    try {
      await updateCompany.mutateAsync({
        companyId: editingCompany.company_id,
        data: {
          name: editName.trim(),
          status: editStatus,
        },
      })
      toast.success(`Company "${editName.trim()}" updated`)
      setEditingCompany(null)
    } catch (err) {
      toast.error('Failed to update company')
      console.error('Failed to update company:', err)
    }
  }

  const handleDeleteCompany = async (companyId: string, companyName: string) => {
    if (deleteConfirm === companyId) {
      try {
        await deleteCompany.mutateAsync(companyId)
        toast.success(`Company "${companyName}" deleted`)
        setDeleteConfirm(null)
      } catch (err: unknown) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to delete company'
        toast.error(errorMessage)
        console.error('Failed to delete company:', err)
      }
    } else {
      setDeleteConfirm(companyId)
      setTimeout(() => setDeleteConfirm(null), 5000) // 5-second confirmation window
    }
  }

  return (
    <>
      <PlatformAdminLayout
        active="companies"
        title="Companies"
        hint="Platform-level tenant management."
      >
        <div className={adminStyles.infoCard}>
          <p className={adminStyles.infoText}>
            Create companies, manage members, and configure roles. Deleting companies is destructive.
          </p>
        </div>

        <div className={adminStyles.pageHeader}>
          <div>
            <h2 className={adminStyles.pageTitle}>
              Companies
              {companiesData ? <span className={adminStyles.countBadge}>{companiesData.total}</span> : null}
            </h2>
            <p className={adminStyles.pageHint}>Search by name or status. Use Members/Roles to manage access.</p>
          </div>
          <Button onClick={() => setIsCreateModalOpen(true)}>Create company</Button>
        </div>

        {!isLoading && !error && companies.length > 0 ? (
          <div className={adminStyles.filtersRow}>
            <div className={adminStyles.searchField}>
              <Input
                placeholder="Search by name or status..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <div className={adminStyles.searchMeta}>
              {searchQuery ? `Found: ${filteredCompanies.length} of ${companies.length}` : null}
            </div>
          </div>
        ) : null}

        {isLoading ? (
          <div className={adminStyles.stateCard}>
            <h3 className={adminStyles.stateTitle}>Loading</h3>
            <p className={adminStyles.stateText}>Loading companies...</p>
          </div>
        ) : null}

        {error ? (
          <div className={adminStyles.stateCard}>
            <h3 className={adminStyles.stateTitle} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconAlertTriangle size={18} />
              Loading error
            </h3>
            <p className={adminStyles.stateText}>
              {error instanceof Error ? error.message : 'Failed to load companies'}
            </p>
            <div className={adminStyles.stateActions}>
              <Button onClick={() => refetch()} variant="secondary">
                Retry
              </Button>
            </div>
          </div>
        ) : null}

        {!isLoading && !error && companies.length === 0 ? (
          <div className={adminStyles.stateCard}>
            <h3 className={adminStyles.stateTitle} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconBuilding size={18} />
              No companies
            </h3>
            <p className={adminStyles.stateText}>Create your first company to get started.</p>
            <div className={adminStyles.stateActions}>
              <Button onClick={() => setIsCreateModalOpen(true)}>Create company</Button>
            </div>
          </div>
        ) : null}

        {!isLoading && !error && companies.length > 0 ? (
          <div className={adminStyles.tableWrap}>
            <table className={adminStyles.table}>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th className={adminStyles.thRight}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredCompanies.map((company) => (
                  <tr key={company.company_id}>
                    <td>
                      <Link to={`/admin/companies/${company.slug}/members`} style={{ fontWeight: 700, color: '#0f172a' }}>
                        {company.name}
                      </Link>
                    </td>
                    <td>{company.status === 'active' ? 'Active' : 'Disabled'}</td>
                    <td>{new Date(company.created_at_utc).toLocaleDateString('en-GB')}</td>
                    <td className={adminStyles.tdRight}>
                      <div style={{ display: 'inline-flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                        <Button variant="secondary" size="sm" onClick={() => openEditModal(company)}>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                            <IconPencil size={14} />
                            Edit
                          </span>
                        </Button>
                        <Link to={`/admin/companies/${company.slug}/members`}>
                          <Button variant="secondary" size="sm">
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                              <IconUsers size={14} />
                              Members
                            </span>
                          </Button>
                        </Link>
                        <Link to={`/admin/companies/${company.slug}/roles`}>
                          <Button variant="secondary" size="sm">
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                              <IconSettings size={14} />
                              Roles
                            </span>
                          </Button>
                        </Link>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => handleDeleteCompany(company.company_id, company.name)}
                        >
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                            {deleteConfirm === company.company_id ? <IconAlertTriangle size={14} /> : <IconTrash size={14} />}
                            {deleteConfirm === company.company_id ? 'Confirm delete' : 'Delete'}
                          </span>
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredCompanies.length === 0 && searchQuery ? (
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

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create company"
      >
        <form onSubmit={handleCreateCompany} className={adminStyles.stateCard}>
          <Input
            label="Company name"
            value={newCompanyName}
            onChange={(e) => setNewCompanyName(e.target.value)}
            placeholder="Company LLC"
            required
          />
          <div className={adminStyles.stateActions}>
            <Button type="button" variant="secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createCompany.isPending}>
              {createCompany.isPending ? 'Creating...' : 'Create'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Modal */}
      <Modal
        isOpen={!!editingCompany}
        onClose={() => setEditingCompany(null)}
        title="Edit company"
      >
        <form onSubmit={handleEditCompany} className={adminStyles.stateCard}>
          <Input
            label="Company name"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            placeholder="Company LLC"
            required
          />
          <div>
            <label style={{ display: 'block', fontWeight: 700, marginBottom: '0.35rem', color: '#0f172a' }}>Status</label>
            <select
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value as 'active' | 'disabled')}
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
          <div className={adminStyles.stateActions}>
            <Button type="button" variant="secondary" onClick={() => setEditingCompany(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateCompany.isPending}>
              {updateCompany.isPending ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  )
}
