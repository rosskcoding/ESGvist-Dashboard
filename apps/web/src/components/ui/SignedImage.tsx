/**
 * SignedImage - Image component that uses signed URLs for secure asset access.
 * 
 * Automatically fetches a signed URL before loading the image.
 * Shows a placeholder while loading, and handles errors gracefully.
 * 
 * Usage:
 *   <SignedImage assetId="..." alt="My image" className={styles.thumbnail} />
 */

import { useState, useEffect, useCallback, memo } from 'react'
import { getAssetSignedUrl } from '@/api/hooks'
import { IconX } from './Icons'

interface SignedImageProps extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'src'> {
  /** Asset UUID to load */
  assetId: string
  /** Alt text for accessibility */
  alt: string
  /** Fallback content to show on error */
  fallback?: React.ReactNode
  /** Placeholder while loading signed URL */
  placeholder?: React.ReactNode
  /** TTL for signed URL in seconds (default: 300) */
  ttlSeconds?: number
}

// In-memory cache for signed URLs to avoid redundant API calls
const signedUrlCache = new Map<string, { url: string; expiresAt: number }>()

// Get cached URL if still valid (with 30 second buffer)
function getCachedUrl(assetId: string): string | null {
  const cached = signedUrlCache.get(assetId)
  if (cached && cached.expiresAt > Date.now() / 1000 + 30) {
    return cached.url
  }
  return null
}

// Store URL in cache
function setCachedUrl(assetId: string, url: string, expiresAt: number) {
  signedUrlCache.set(assetId, { url, expiresAt })
}

/**
 * Clear signed URL cache for a specific asset or all assets.
 * Call this after uploading a new image to ensure fresh URLs.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function clearSignedUrlCache(assetId?: string) {
  if (assetId) {
    signedUrlCache.delete(assetId)
  } else {
    signedUrlCache.clear()
  }
}

export const SignedImage = memo(function SignedImage({
  assetId,
  alt,
  fallback = <IconX size={18} />,
  placeholder = null,
  ttlSeconds = 300,
  loading = 'lazy',
  ...imgProps
}: SignedImageProps) {
  const [signedUrl, setSignedUrl] = useState<string | null>(() => getCachedUrl(assetId))
  const [isLoading, setIsLoading] = useState(!signedUrl)
  const [hasError, setHasError] = useState(false)

  // Fetch signed URL
  useEffect(() => {
    let cancelled = false

    async function fetchUrl() {
      // Check cache first
      const cached = getCachedUrl(assetId)
      if (cached) {
        setSignedUrl(cached)
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        setHasError(false)
        
        const url = await getAssetSignedUrl(assetId, ttlSeconds)
        
        if (!cancelled) {
          // Parse expires from URL token
          const tokenMatch = url.match(/token=(\d+)\./)
          const expiresAt = tokenMatch ? parseInt(tokenMatch[1], 10) : Date.now() / 1000 + ttlSeconds
          
          setCachedUrl(assetId, url, expiresAt)
          setSignedUrl(url)
          setIsLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to get signed URL:', err)
          setHasError(true)
          setIsLoading(false)
        }
      }
    }

    fetchUrl()

    return () => {
      cancelled = true
    }
  }, [assetId, ttlSeconds])

  // Handle image load error
  const handleError = useCallback(() => {
    setHasError(true)
    // Clear cache on error (URL might have expired)
    signedUrlCache.delete(assetId)
  }, [assetId])

  // Show placeholder while loading
  if (isLoading) {
    return placeholder ? <>{placeholder}</> : null
  }

  // Show fallback on error
  if (hasError || !signedUrl) {
    return <>{fallback}</>
  }

  return (
    <img
      {...imgProps}
      src={signedUrl}
      alt={alt}
      loading={loading}
      onError={handleError}
    />
  )
})

/**
 * Hook to get a signed URL for an asset.
 * Returns { url, isLoading, error } for more control.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useSignedAssetUrl(assetId: string | null, ttlSeconds = 300) {
  const [url, setUrl] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    if (!assetId) {
      setUrl(null)
      return
    }

    // Capture the non-null assetId for the async function
    const id = assetId
    let cancelled = false

    async function fetchUrl() {
      // Check cache
      const cached = getCachedUrl(id)
      if (cached) {
        setUrl(cached)
        return
      }

      try {
        setIsLoading(true)
        setError(null)
        
        const signedUrl = await getAssetSignedUrl(id, ttlSeconds)
        
        if (!cancelled) {
          const tokenMatch = signedUrl.match(/token=(\d+)\./)
          const expiresAt = tokenMatch ? parseInt(tokenMatch[1], 10) : Date.now() / 1000 + ttlSeconds
          
          setCachedUrl(id, signedUrl, expiresAt)
          setUrl(signedUrl)
          setIsLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error('Failed to get signed URL'))
          setIsLoading(false)
        }
      }
    }

    fetchUrl()

    return () => {
      cancelled = true
    }
  }, [assetId, ttlSeconds])

  return { url, isLoading, error }
}
