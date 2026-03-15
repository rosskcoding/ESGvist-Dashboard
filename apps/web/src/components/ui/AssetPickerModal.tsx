/**
 * AssetPickerModal - Universal asset selection/upload modal
 * 
 * Features:
 * - Gallery view of existing assets
 * - Drag & drop upload zone
 * - Filter by kind (image/attachment)
 * - Preview selected asset
 */

import { useState, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Modal } from './Modal'
import { Button } from './Button'
import { SignedImage } from './SignedImage'
import { IconCheck, IconClock, IconFileText, IconFolder, IconImage, IconTrash, IconX } from './Icons'
import { useAssets, useDeleteAsset, useUploadAsset } from '@/api/hooks'
import type { Asset, AssetKind } from '@/types/api'
import styles from './AssetPickerModal.module.css'

interface AssetPickerModalProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (asset: Asset) => void
  kind?: AssetKind
  title?: string
}

export function AssetPickerModal({
  isOpen,
  onClose,
  onSelect,
  kind = 'image',
  title,
}: AssetPickerModalProps) {
  const { t } = useTranslation(['ui', 'common'])
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const isWebdriver =
    typeof navigator !== 'undefined' &&
    (navigator as Navigator & { webdriver?: boolean }).webdriver === true

  const { data: assetsData, isLoading } = useAssets({ kind, pageSize: 50 })
  const uploadMutation = useUploadAsset()
  const deleteMutation = useDeleteAsset()

  const assets = assetsData?.items || []
  const resolvedTitle =
    title || (kind === 'image' ? t('ui:assetPicker.titleImage') : t('ui:assetPicker.titleAttachment'))

  const handleFileUpload = useCallback(
    async (file: File) => {
      setUploadError(null)

      // Validate file type
      const allowedTypes =
        kind === 'image'
          ? ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml']
          : ['application/pdf', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/csv']

      if (!allowedTypes.includes(file.type)) {
        setUploadError(t('ui:assetPicker.errors.unsupportedType', { type: file.type }))
        return
      }

      // Validate file size (10MB for images, 50MB for attachments)
      const maxSize = kind === 'image' ? 10 * 1024 * 1024 : 50 * 1024 * 1024
      if (file.size > maxSize) {
        setUploadError(
          t('ui:assetPicker.errors.tooLarge', { maxMb: maxSize / 1024 / 1024 })
        )
        return
      }

      try {
        const result = await uploadMutation.mutateAsync({ file, kind })
        setSelectedAsset(result.asset)
      } catch (err) {
        setUploadError(
          err instanceof Error ? err.message : t('ui:assetPicker.errors.uploadFailed')
        )
      }
    },
    [kind, t, uploadMutation]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragOver(false)

      const file = e.dataTransfer.files[0]
      if (file) {
        handleFileUpload(file)
      }
    },
    [handleFileUpload]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [])

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      // Reset input so the same file can be selected again
      e.target.value = ''
      if (file) {
        handleFileUpload(file)
      }
    },
    [handleFileUpload]
  )

  const openFileDialog = useCallback(() => {
    const input = fileInputRef.current
    if (!input) return

    try {
      // Use click() for maximum compatibility (Safari/Chrome/Firefox).
      // Note: In automation environments, OS dialogs may not appear; drag&drop remains available.
      input.click()
    } catch {
      // ignore
    }
  }, [])

  const handleConfirm = () => {
    if (selectedAsset) {
      onSelect(selectedAsset)
      onClose()
    }
  }

  const handleDeleteAsset = useCallback(
    async (asset: Asset) => {
      if (deleteMutation.isPending) return

      const ok = window.confirm(
        t('ui:assetPicker.confirm.deleteAsset', { filename: asset.filename })
      )
      if (!ok) return

      setUploadError(null)

      try {
        await deleteMutation.mutateAsync({ assetId: asset.asset_id, force: false })
        if (selectedAsset?.asset_id === asset.asset_id) setSelectedAsset(null)
        return
      } catch (err) {
        const msg = err instanceof Error ? err.message : t('ui:assetPicker.errors.deleteFailed')

        // If asset is linked to blocks, backend returns 409 with a hint to use force=true.
        const maybeLinked = msg.includes('force=true') || msg.toLowerCase().includes('linked')

        if (maybeLinked) {
          const forceOk = window.confirm(
            t('ui:assetPicker.confirm.forceDelete', { message: msg })
          )
          if (forceOk) {
            try {
              await deleteMutation.mutateAsync({ assetId: asset.asset_id, force: true })
              if (selectedAsset?.asset_id === asset.asset_id) setSelectedAsset(null)
              return
            } catch (forceErr) {
              setUploadError(
                forceErr instanceof Error
                  ? forceErr.message
                  : t('ui:assetPicker.errors.deleteFailed')
              )
              return
            }
          }
        }

        setUploadError(msg)
      }
    },
    [deleteMutation, selectedAsset, t]
  )

  const handleDeleteSelected = useCallback(async () => {
    if (!selectedAsset) return
    await handleDeleteAsset(selectedAsset)
  }, [handleDeleteAsset, selectedAsset])

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={resolvedTitle} size="xl">
      <div className={styles.container}>
        {/* Upload Zone */}
        <div
          className={`${styles.dropZone} ${isDragOver ? styles.dragOver : ''} ${
            uploadMutation.isPending ? styles.uploading : ''
          }`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={openFileDialog}
        >
          <input
            ref={fileInputRef}
            type="file"
            className={styles.fileInput}
            accept={kind === 'image' ? 'image/*' : '.pdf,.xlsx,.xls,.csv'}
            onChange={handleFileInputChange}
          />
          
          {uploadMutation.isPending ? (
            <div className={styles.uploadingState}>
              <span className={styles.spinner} aria-hidden="true">
                <IconClock size={18} />
              </span>
              <span>{t('ui:assetPicker.uploading')}</span>
            </div>
          ) : (
            <>
              <span className={styles.dropIcon}>
                {kind === 'image' ? <IconImage size={22} /> : <IconFolder size={22} />}
              </span>
              <span className={styles.dropText}>
                {t('ui:assetPicker.dropZone.text')}
              </span>
              <span className={styles.dropHint}>
                {kind === 'image'
                  ? t('ui:assetPicker.dropZone.imageHint')
                  : t('ui:assetPicker.dropZone.attachmentHint')}
              </span>
              {isWebdriver && (
                <span className={styles.dropHint}>
                  {t('ui:assetPicker.dropZone.webdriverHint')}
                </span>
              )}
            </>
          )}
        </div>

        {uploadError && <div className={styles.error}>{uploadError}</div>}

        {/* Assets Gallery */}
        <div className={styles.gallerySection}>
          <h4 className={styles.galleryTitle}>
            {kind === 'image'
              ? t('ui:assetPicker.gallery.titleImages')
              : t('ui:assetPicker.gallery.titleAttachments')}
          </h4>
          
          {isLoading ? (
            <div className={styles.loading}>{t('ui:assetPicker.gallery.loading')}</div>
          ) : assets.length === 0 ? (
            <div className={styles.emptyGallery}>
              <span>
                {kind === 'image'
                  ? t('ui:assetPicker.gallery.emptyImages')
                  : t('ui:assetPicker.gallery.emptyAttachments')}
              </span>
            </div>
          ) : (
            <div className={styles.gallery}>
              {assets.map((asset) => (
                <div
                  key={asset.asset_id}
                  className={`${styles.assetCard} ${
                    selectedAsset?.asset_id === asset.asset_id ? styles.selected : ''
                  }`}
                  onClick={() => setSelectedAsset(asset)}
                >
                  <button
                    type="button"
                    className={styles.deleteBtn}
                    title={t('ui:assetPicker.removeFile')}
                    aria-label={t('ui:assetPicker.removeFile')}
                    disabled={deleteMutation.isPending}
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      handleDeleteAsset(asset)
                    }}
                  >
                    <IconTrash size={16} />
                  </button>
                  {kind === 'image' ? (
                    <SignedImage
                      assetId={asset.asset_id}
                      alt={asset.filename}
                      className={styles.thumbnail}
                      placeholder={
                        <div className={styles.thumbnailPlaceholder}>
                          <IconClock size={18} />
                        </div>
                      }
                      fallback={
                        <div className={styles.thumbnailError}>
                          <IconX size={18} />
                        </div>
                      }
                    />
                  ) : (
                    <div className={styles.fileIcon}>
                      <IconFileText size={22} />
                    </div>
                  )}
                  <div className={styles.assetInfo}>
                    <span className={styles.assetName} title={asset.filename}>
                      {asset.filename.length > 20
                        ? `${asset.filename.slice(0, 17)}...`
                        : asset.filename}
                    </span>
                    <span className={styles.assetSize}>
                      {formatFileSize(asset.size_bytes)}
                    </span>
                  </div>
                  {selectedAsset?.asset_id === asset.asset_id && (
                    <div className={styles.checkmark} aria-hidden="true">
                      <IconCheck size={18} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Preview & Actions */}
        <div className={styles.footer}>
          {selectedAsset && (
            <div className={styles.preview}>
              {kind === 'image' ? (
                <SignedImage
                  assetId={selectedAsset.asset_id}
                  alt={selectedAsset.filename}
                  className={styles.previewImage}
                  placeholder={
                    <div className={styles.previewPlaceholder}>
                      <IconClock size={18} /> {t('ui:assetPicker.loading')}
                    </div>
                  }
                />
              ) : (
                <span className={styles.previewFile}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                    <IconFileText size={18} />
                    {selectedAsset.filename}
                  </span>
                </span>
              )}
            </div>
          )}
          
          <div className={styles.actions}>
            <Button variant="secondary" onClick={onClose}>
              {t('common:actions.cancel')}
            </Button>
            <Button
              variant="danger"
              onClick={handleDeleteSelected}
              disabled={!selectedAsset}
              loading={deleteMutation.isPending}
            >
              {t('ui:assetPicker.actions.delete')}
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={!selectedAsset || deleteMutation.isPending}
            >
              {t('ui:assetPicker.actions.select')}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  )
}
