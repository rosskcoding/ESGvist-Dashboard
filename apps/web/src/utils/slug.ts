/**
 * Slug utilities for URL generation
 */

import type { Section } from '@/types/api'

/**
 * Get section slug for URL from source locale
 * 
 * @param section - Section with i18n array
 * @param sourceLocale - Report's source locale
 * @returns Slug from source locale or first available, or section_id as fallback
 */
export function getSectionSlug(section: Section, sourceLocale: string): string {
  // Try to find slug in source locale
  const sourceI18n = section.i18n.find(i => i.locale === sourceLocale)
  if (sourceI18n?.slug) {
    return sourceI18n.slug
  }

  // Fallback to first available slug
  const firstI18n = section.i18n[0]
  if (firstI18n?.slug) {
    return firstI18n.slug
  }

  // Ultimate fallback to ID
  return section.section_id
}

/**
 * Find section by slug in source locale
 * 
 * @param sections - Array of sections
 * @param slug - Section slug to find
 * @param sourceLocale - Report's source locale
 * @returns Section if found, undefined otherwise
 */
export function findSectionBySlug(
  sections: Section[],
  slug: string,
  sourceLocale: string
): Section | undefined {
  return sections.find(section => {
    const i18n = section.i18n.find(i => i.locale === sourceLocale)
    return i18n?.slug === slug
  })
}




