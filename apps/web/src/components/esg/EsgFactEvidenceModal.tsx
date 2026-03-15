import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, ConfirmDialog, Input, Modal, Select } from '@/components/ui'
import { toast } from '@/components/ui/toast'
import {
  getAssetSignedUrl,
  useCompanyMemberships,
  useCreateEsgFactEvidence,
  useDeleteEsgFactEvidence,
  useEsgFactEvidence,
  useUpdateEsgFactEvidence,
  useUploadAsset,
} from '@/api/hooks'
import type { EsgFactEvidenceItem, EsgFactEvidenceType } from '@/types/api'
import styles from './EsgFactEvidenceModal.module.css'

export function EsgFactEvidenceModal(props: {
  isOpen: boolean
  companyId?: string
  factId: string
  canWrite: boolean
  meta?: string
  onClose: () => void
}) {
  const { t } = useTranslation(['esg', 'common'])

  const evidenceList = useEsgFactEvidence(props.factId)
  const createEvidence = useCreateEsgFactEvidence()
  const updateEvidence = useUpdateEsgFactEvidence()
  const deleteEvidence = useDeleteEsgFactEvidence()
  const uploadAsset = useUploadAsset()

  const companyId = props.companyId || evidenceList.data?.[0]?.company_id || ''
  const membershipsQuery = useCompanyMemberships(companyId)

  const [newEvidenceType, setNewEvidenceType] = useState<EsgFactEvidenceType>('file')
  const [newEvidenceTitle, setNewEvidenceTitle] = useState<string>('')
  const [newEvidenceDescription, setNewEvidenceDescription] = useState<string>('')
  const [newEvidenceSource, setNewEvidenceSource] = useState<string>('')
  const [newEvidenceSourceDate, setNewEvidenceSourceDate] = useState<string>('')
  const [newEvidenceOwnerUserId, setNewEvidenceOwnerUserId] = useState<string>('')
  const [newEvidenceUrl, setNewEvidenceUrl] = useState<string>('')
  const [newEvidenceNote, setNewEvidenceNote] = useState<string>('')
  const [newEvidenceFile, setNewEvidenceFile] = useState<File | null>(null)
  const [deleteEvidenceId, setDeleteEvidenceId] = useState<string | null>(null)
  const [notePreview, setNotePreview] = useState<EsgFactEvidenceItem | null>(null)
  const [editEvidence, setEditEvidence] = useState<EsgFactEvidenceItem | null>(null)

  const [editTitle, setEditTitle] = useState<string>('')
  const [editDescription, setEditDescription] = useState<string>('')
  const [editSource, setEditSource] = useState<string>('')
  const [editSourceDate, setEditSourceDate] = useState<string>('')
  const [editOwnerUserId, setEditOwnerUserId] = useState<string>('')

  const evidenceTypeOptions = useMemo(
    () => [
      { value: 'file', label: t('esg:factCreatePage.evidence.types.file') },
      { value: 'link', label: t('esg:factCreatePage.evidence.types.link') },
      { value: 'note', label: t('esg:factCreatePage.evidence.types.note') },
    ],
    [t]
  )

  const resetEvidenceForm = () => {
    setNewEvidenceTitle('')
    setNewEvidenceDescription('')
    setNewEvidenceSource('')
    setNewEvidenceSourceDate('')
    setNewEvidenceOwnerUserId('')
    setNewEvidenceUrl('')
    setNewEvidenceNote('')
    setNewEvidenceFile(null)
  }

  useEffect(() => {
    if (!props.isOpen) {
      resetEvidenceForm()
      setDeleteEvidenceId(null)
      setNotePreview(null)
      setEditEvidence(null)
    }
  }, [props.isOpen])

  useEffect(() => {
    if (!editEvidence) return
    setEditTitle(editEvidence.title ?? '')
    setEditDescription(editEvidence.description ?? '')
    setEditSource(editEvidence.source ?? '')
    setEditSourceDate(editEvidence.source_date ?? '')
    setEditOwnerUserId(editEvidence.owner_user_id ?? '')
  }, [editEvidence])

  const membersByUserId = useMemo(() => {
    const items = membershipsQuery.data?.items ?? []
    return new Map(items.map((m) => [m.user_id, m]))
  }, [membershipsQuery.data?.items])

  const ownerOptions = useMemo(() => {
    const items = membershipsQuery.data?.items ?? []
    const opts: Array<{ value: string; label: string }> = [{ value: '', label: t('esg:factCreatePage.select.none') }]
    for (const m of items) {
      const label = m.user_name || m.user_email || m.user_id
      opts.push({ value: m.user_id, label })
    }
    return opts
  }, [membershipsQuery.data?.items, t])

  const formatOwner = (userId: string | null) => {
    if (!userId) return t('esg:factCreatePage.select.none')
    const m = membersByUserId.get(userId)
    return m?.user_name || m?.user_email || userId
  }

  const evidenceMetaPayload = () => ({
    source: newEvidenceSource.trim() ? newEvidenceSource.trim() : null,
    source_date: newEvidenceSourceDate || null,
    owner_user_id: newEvidenceOwnerUserId || null,
  })

  const handleDownloadEvidence = async (assetId: string) => {
    // Open a tab synchronously to avoid popup blockers, then redirect once we have the signed URL.
    const w = window.open('about:blank', '_blank', 'noopener,noreferrer')
    try {
      const url = await getAssetSignedUrl(assetId, 300)
      if (w) {
        w.location.href = url
      } else {
        window.location.href = url
      }
    } catch (e) {
      if (w) w.close()
      toast.error((e as Error).message || t('esg:factCreatePage.toast.evidenceDownloadFailed'))
    }
  }

  const handleDeleteEvidence = async (evidenceId: string) => {
    if (!props.canWrite) return
    try {
      await deleteEvidence.mutateAsync({ factId: props.factId, evidenceId })
      toast.success(t('esg:factCreatePage.toast.evidenceDeleted'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:factCreatePage.toast.evidenceDeleteFailed'))
    }
  }

  const handleUploadEvidence = async (file: File, opts?: { title?: string; description?: string }) => {
    if (!props.canWrite) return
    try {
      const uploaded = await uploadAsset.mutateAsync({ file, kind: 'attachment' })
      const meta = evidenceMetaPayload()
      await createEvidence.mutateAsync({
        factId: props.factId,
        data: {
          type: 'file',
          title: opts?.title?.trim() || file.name,
          description: opts?.description?.trim() || null,
          source: meta.source,
          source_date: meta.source_date,
          owner_user_id: meta.owner_user_id,
          asset_id: uploaded.asset.asset_id,
        },
      })
      toast.success(t('esg:factCreatePage.toast.evidenceUploaded'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:factCreatePage.toast.evidenceUploadFailed'))
    }
  }

  const handleCreateLinkEvidence = async (payload: { title: string; url: string; description?: string }) => {
    if (!props.canWrite) return

    let parsedUrl: URL
    try {
      parsedUrl = new URL(payload.url)
    } catch {
      toast.error(t('esg:factCreatePage.validation.invalidUrl'))
      return
    }
    if (parsedUrl.protocol !== 'https:' && parsedUrl.protocol !== 'http:') {
      toast.error(t('esg:factCreatePage.validation.urlMustBeHttp'))
      return
    }

    try {
      const meta = evidenceMetaPayload()
      await createEvidence.mutateAsync({
        factId: props.factId,
        data: {
          type: 'link',
          title: payload.title,
          description: payload.description?.trim() || null,
          source: meta.source,
          source_date: meta.source_date,
          owner_user_id: meta.owner_user_id,
          url: parsedUrl.toString(),
        },
      })
      toast.success(t('esg:factCreatePage.toast.evidenceLinkAdded'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:factCreatePage.toast.evidenceLinkAddFailed'))
    }
  }

  const handleCreateNoteEvidence = async (payload: { title: string; note_md: string; description?: string }) => {
    if (!props.canWrite) return
    if (!payload.note_md.trim()) {
      toast.error(t('esg:factCreatePage.validation.noteRequired'))
      return
    }

    try {
      const meta = evidenceMetaPayload()
      await createEvidence.mutateAsync({
        factId: props.factId,
        data: {
          type: 'note',
          title: payload.title,
          description: payload.description?.trim() || null,
          source: meta.source,
          source_date: meta.source_date,
          owner_user_id: meta.owner_user_id,
          note_md: payload.note_md,
        },
      })
      toast.success(t('esg:factCreatePage.toast.evidenceNoteAdded'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:factCreatePage.toast.evidenceNoteAddFailed'))
    }
  }

  const submitNewEvidence = async () => {
    if (!props.canWrite) return
    if (!newEvidenceTitle.trim()) {
      toast.error(t('esg:factCreatePage.validation.evidenceTitleRequired'))
      return
    }

    if (newEvidenceType === 'file') {
      if (!newEvidenceFile) {
        toast.error(t('esg:factCreatePage.validation.evidenceFileRequired'))
        return
      }
      await handleUploadEvidence(newEvidenceFile, { title: newEvidenceTitle, description: newEvidenceDescription })
      resetEvidenceForm()
      return
    }

    if (newEvidenceType === 'link') {
      if (!newEvidenceUrl.trim()) {
        toast.error(t('esg:factCreatePage.validation.evidenceUrlRequired'))
        return
      }
      await handleCreateLinkEvidence({
        title: newEvidenceTitle.trim(),
        url: newEvidenceUrl.trim(),
        description: newEvidenceDescription,
      })
      resetEvidenceForm()
      return
    }

    await handleCreateNoteEvidence({
      title: newEvidenceTitle.trim(),
      note_md: newEvidenceNote,
      description: newEvidenceDescription,
    })
    resetEvidenceForm()
  }

  const submitEditEvidence = async () => {
    if (!props.canWrite) return
    if (!editEvidence) return

    const title = editTitle.trim()
    if (!title) {
      toast.error(t('esg:factCreatePage.validation.evidenceTitleRequired'))
      return
    }

    try {
      await updateEvidence.mutateAsync({
        factId: props.factId,
        evidenceId: editEvidence.evidence_id,
        data: {
          title,
          description: editDescription.trim() ? editDescription.trim() : null,
          source: editSource.trim() ? editSource.trim() : null,
          source_date: editSourceDate || null,
          owner_user_id: editOwnerUserId || null,
        },
      })
      toast.success(t('esg:factCreatePage.toast.evidenceUpdated'))
      setEditEvidence(null)
    } catch (e) {
      toast.error((e as Error).message || t('esg:factCreatePage.toast.evidenceUpdateFailed'))
    }
  }

  return (
    <Modal
      isOpen={props.isOpen}
      onClose={props.onClose}
      title={t('esg:factsPage.actions.evidence')}
      size="lg"
    >
      {props.meta && <p className={styles.meta}>{props.meta}</p>}
      <p className={styles.help}>{t('esg:factCreatePage.evidence.help')}</p>

      {props.canWrite && (
        <div className={styles.evidenceComposer}>
          <Select
            label={t('esg:factCreatePage.evidence.fields.type')}
            value={newEvidenceType}
            onChange={(e) => {
              setNewEvidenceType(e.target.value as EsgFactEvidenceType)
              resetEvidenceForm()
            }}
            options={evidenceTypeOptions}
          />
          <Input
            label={t('esg:factCreatePage.evidence.fields.title')}
            value={newEvidenceTitle}
            onChange={(e) => setNewEvidenceTitle(e.target.value)}
            placeholder={newEvidenceType === 'file' ? t('esg:factCreatePage.evidence.placeholders.fileTitle') : t('esg:factCreatePage.evidence.placeholders.shortTitle')}
          />
            <Input
              label={t('esg:factCreatePage.evidence.fields.description')}
              value={newEvidenceDescription}
              onChange={(e) => setNewEvidenceDescription(e.target.value)}
              placeholder={t('esg:factCreatePage.evidence.placeholders.description')}
            />
            <Input
              label={t('esg:factCreatePage.evidence.fields.source')}
              value={newEvidenceSource}
              onChange={(e) => setNewEvidenceSource(e.target.value)}
              placeholder={t('esg:factCreatePage.evidence.placeholders.source')}
            />
            <Input
              label={t('esg:factCreatePage.evidence.fields.sourceDate')}
              type="date"
              value={newEvidenceSourceDate}
              onChange={(e) => setNewEvidenceSourceDate(e.target.value)}
            />
            <Select
              label={t('esg:factCreatePage.evidence.fields.owner')}
              value={newEvidenceOwnerUserId}
              onChange={(e) => setNewEvidenceOwnerUserId(e.target.value)}
              options={ownerOptions}
            />

            {newEvidenceType === 'file' && (
            <div className={styles.evidenceFile}>
              <input
                type="file"
                onChange={(e) => {
                  const file = e.target.files?.[0] ?? null
                  setNewEvidenceFile(file)
                  if (file && !newEvidenceTitle.trim()) {
                    setNewEvidenceTitle(file.name)
                  }
                  e.currentTarget.value = ''
                }}
              />
              {newEvidenceFile && (
                <div className={styles.evidenceFileName} title={newEvidenceFile.name}>
                  {t('esg:factCreatePage.evidence.selectedFile')}: <span className={styles.monoInline}>{newEvidenceFile.name}</span>
                </div>
              )}
            </div>
          )}

          {newEvidenceType === 'link' && (
            <Input
              label={t('esg:factCreatePage.evidence.fields.url')}
              value={newEvidenceUrl}
              onChange={(e) => setNewEvidenceUrl(e.target.value)}
              placeholder={t('esg:factCreatePage.evidence.placeholders.url')}
            />
          )}

          {newEvidenceType === 'note' && (
            <div className={styles.gridFull}>
              <label className={styles.textareaLabel}>{t('esg:factCreatePage.evidence.fields.note')}</label>
              <textarea
                className={styles.textarea}
                value={newEvidenceNote}
                onChange={(e) => setNewEvidenceNote(e.target.value)}
                placeholder={t('esg:factCreatePage.evidence.placeholders.note')}
              />
            </div>
          )}

          <div className={styles.evidenceComposerActions}>
            <Button
              variant="secondary"
              onClick={resetEvidenceForm}
              disabled={createEvidence.isPending || uploadAsset.isPending}
            >
              {t('esg:factCreatePage.evidence.actions.clear')}
            </Button>
            <Button
              onClick={() => void submitNewEvidence()}
              disabled={createEvidence.isPending || uploadAsset.isPending}
            >
              {t('esg:factCreatePage.evidence.actions.add')}
            </Button>
          </div>
        </div>
      )}

      <ul className={styles.evidenceList}>
        {evidenceList.isLoading && <li className={styles.evidenceItem}>{t('common:common.loading')}</li>}
        {!evidenceList.isLoading &&
            (evidenceList.data ?? []).map((ev) => (
              <li key={ev.evidence_id} className={styles.evidenceItem}>
                <div className={styles.evidenceMeta}>
                  <div className={styles.evidenceTitle}>{ev.title}</div>
                  <div className={styles.evidenceSub}>
                    {ev.type}
                    {ev.url ? ` | ${ev.url}` : ''}
                    {ev.description ? ` | ${ev.description}` : ''}
                  </div>
                  <div className={styles.evidenceAttrs}>
                    <span className={styles.evidenceAttr}>
                      {t('esg:factCreatePage.evidence.fields.source')}: {ev.source || t('esg:factCreatePage.select.none')}
                    </span>
                    <span className={styles.evidenceAttr}>
                      {t('esg:factCreatePage.evidence.fields.sourceDate')}: {ev.source_date || t('esg:factCreatePage.select.none')}
                    </span>
                    <span className={styles.evidenceAttr}>
                      {t('esg:factCreatePage.evidence.fields.owner')}: {formatOwner(ev.owner_user_id)}
                    </span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  {ev.type === 'file' && ev.asset_id && (
                    <Button variant="secondary" size="sm" onClick={() => void handleDownloadEvidence(ev.asset_id!)}>
                      {t('esg:factCreatePage.evidence.actions.download')}
                    </Button>
                  )}
                {ev.type === 'link' && ev.url && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => window.open(ev.url!, '_blank', 'noopener,noreferrer')}
                  >
                    {t('esg:factCreatePage.evidence.actions.open')}
                  </Button>
                )}
                  {ev.type === 'note' && (
                    <Button variant="secondary" size="sm" onClick={() => setNotePreview(ev)}>
                      {t('esg:factCreatePage.evidence.actions.view')}
                    </Button>
                  )}
                  {props.canWrite && (
                    <Button variant="secondary" size="sm" onClick={() => setEditEvidence(ev)}>
                      {t('common:actions.edit')}
                    </Button>
                  )}
                  {props.canWrite && (
                    <Button variant="secondary" size="sm" onClick={() => setDeleteEvidenceId(ev.evidence_id)}>
                      {t('common:actions.delete')}
                    </Button>
                  )}
                </div>
              </li>
            ))}
      </ul>

      <ConfirmDialog
        isOpen={Boolean(deleteEvidenceId)}
        title={t('esg:factCreatePage.evidence.confirmDeleteTitle')}
        message={t('esg:factCreatePage.evidence.confirmDeleteMessage')}
        confirmLabel={t('common:actions.delete')}
        confirmLoading={deleteEvidence.isPending}
        onCancel={() => setDeleteEvidenceId(null)}
        onConfirm={() => {
          if (!deleteEvidenceId) return
          void handleDeleteEvidence(deleteEvidenceId).finally(() => setDeleteEvidenceId(null))
        }}
      />

        <Modal
          isOpen={Boolean(notePreview)}
          onClose={() => setNotePreview(null)}
          title={t('esg:factCreatePage.evidence.noteModalTitle')}
          size="lg"
      >
        {notePreview && (
          <div className={styles.notePreview}>
            <div className={styles.notePreviewTitle}>{notePreview.title}</div>
            {notePreview.description && <div className={styles.notePreviewMeta}>{notePreview.description}</div>}
            <pre className={styles.notePreviewBody}>{notePreview.note_md ?? ''}</pre>
          </div>
        )}
        </Modal>

        <Modal
          isOpen={Boolean(editEvidence)}
          onClose={() => setEditEvidence(null)}
          title={t('esg:factCreatePage.evidence.editModalTitle')}
          size="lg"
        >
          {editEvidence && (
            <>
              <Input
                label={t('esg:factCreatePage.evidence.fields.title')}
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
              />
              <Input
                label={t('esg:factCreatePage.evidence.fields.description')}
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                placeholder={t('esg:factCreatePage.evidence.placeholders.description')}
              />
              <Input
                label={t('esg:factCreatePage.evidence.fields.source')}
                value={editSource}
                onChange={(e) => setEditSource(e.target.value)}
                placeholder={t('esg:factCreatePage.evidence.placeholders.source')}
              />
              <Input
                label={t('esg:factCreatePage.evidence.fields.sourceDate')}
                type="date"
                value={editSourceDate}
                onChange={(e) => setEditSourceDate(e.target.value)}
              />
              <Select
                label={t('esg:factCreatePage.evidence.fields.owner')}
                value={editOwnerUserId}
                onChange={(e) => setEditOwnerUserId(e.target.value)}
                options={ownerOptions}
              />
              <div className={styles.evidenceComposerActions}>
                <Button variant="secondary" onClick={() => setEditEvidence(null)} disabled={updateEvidence.isPending}>
                  {t('common:actions.cancel')}
                </Button>
                <Button onClick={() => void submitEditEvidence()} loading={updateEvidence.isPending}>
                  {t('common:actions.save')}
                </Button>
              </div>
            </>
          )}
        </Modal>
      </Modal>
    )
}
