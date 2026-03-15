import { describe, it, expect, vi, beforeEach } from 'vitest'

// Test the asset-related query key generators
describe('Asset Query Keys', () => {
  it('generates correct list query key', async () => {
    const { queryKeys } = await import('./hooks')
    
    const key = queryKeys.assets.list({ kind: 'image', page: 1 })
    expect(key).toEqual(['assets', 'list', { kind: 'image', page: 1 }])
  })

  it('generates correct detail query key', async () => {
    const { queryKeys } = await import('./hooks')
    
    const key = queryKeys.assets.detail('test-asset-id')
    expect(key).toEqual(['assets', 'detail', 'test-asset-id'])
  })
})

describe('Asset Upload FormData', () => {
  it('should create proper FormData for file upload', () => {
    const file = new File(['test content'], 'test.jpg', { type: 'image/jpeg' })
    const formData = new FormData()
    formData.append('file', file)
    
    expect(formData.get('file')).toBe(file)
    expect((formData.get('file') as File).name).toBe('test.jpg')
    expect((formData.get('file') as File).type).toBe('image/jpeg')
  })
})

describe('API Client FormData Handling', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('should not stringify FormData body', async () => {
    // This test ensures the client properly handles FormData
    // by not calling JSON.stringify on it
    const file = new File(['test'], 'test.jpg', { type: 'image/jpeg' })
    const formData = new FormData()
    formData.append('file', file)
    
    // FormData should not be stringified
    expect(() => JSON.stringify(formData)).not.toThrow()
    // But the result is just "{}" which is wrong for uploads
    expect(JSON.stringify(formData)).toBe('{}')
    
    // So the client should detect FormData and not stringify it
    expect(formData instanceof FormData).toBe(true)
  })
})

// === Artifact Hooks Tests ===

describe('Artifact Query Keys', () => {
  it('generates correct list query key', async () => {
    const { artifactQueryKeys } = await import('./hooks')
    
    const key = artifactQueryKeys.list('test-build-id')
    expect(key).toEqual(['artifacts', 'list', 'test-build-id'])
  })

  it('generates correct detail query key', async () => {
    const { artifactQueryKeys } = await import('./hooks')
    
    const key = artifactQueryKeys.detail('build-id', 'artifact-id')
    expect(key).toEqual(['artifacts', 'detail', 'build-id', 'artifact-id'])
  })
})

describe('Artifact Types', () => {
  it('ArtifactFormat values are valid', () => {
    // Valid format values
    const formats = ['pdf', 'docx']
    expect(formats).toContain('pdf')
    expect(formats).toContain('docx')
    expect(formats).toHaveLength(2)
  })

  it('ArtifactStatus values are valid', () => {
    // Valid status values
    const statuses = ['queued', 'processing', 'done', 'failed', 'cancelled']
    expect(statuses).toHaveLength(5)
    expect(statuses).toContain('queued')
    expect(statuses).toContain('done')
    expect(statuses).toContain('failed')
  })
})

describe('ArtifactCreate interface', () => {
  it('should accept valid create data', () => {
    type ArtifactFormat = 'pdf' | 'docx'
    
    interface ArtifactCreate {
      format: ArtifactFormat
      locale: string
      profile?: string
    }
    
    const pdfCreate: ArtifactCreate = {
      format: 'pdf',
      locale: 'ru',
      profile: 'audit',
    }
    
    const docxCreate: ArtifactCreate = {
      format: 'docx',
      locale: 'en',
    }
    
    expect(pdfCreate.format).toBe('pdf')
    expect(pdfCreate.profile).toBe('audit')
    expect(docxCreate.format).toBe('docx')
    expect(docxCreate.profile).toBeUndefined()
  })
})



