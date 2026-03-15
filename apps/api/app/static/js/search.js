/**
 * ESG Report Creator - Client-side Search
 * Spec reference: 09_Search.md
 */

class ReportSearch {
  constructor(locale) {
    this.locale = locale
    this.index = null
    this.isLoaded = false
  }

  async init() {
    if (this.isLoaded) return
    
    try {
      const assetsBase =
        document.documentElement.getAttribute('data-assets-base') || '/assets'
      const response = await fetch(`${assetsBase}/search/index.${this.locale}.json`)
      this.index = await response.json()
      this.isLoaded = true
      console.log(`Search index loaded: ${this.index.total_chunks} entries`)
    } catch (err) {
      console.error('Failed to load search index:', err)
    }
  }

  search(query) {
    if (!this.index || !query) return []
    
    const normalized = query.toLowerCase().trim()
    const results = []
    
    for (const entry of this.index.entries) {
      const content = entry.content.toLowerCase()
      const sectionTitle = entry.section_title.toLowerCase()
      
      // Simple relevance scoring
      let score = 0
      
      if (sectionTitle.includes(normalized)) {
        score += 10
      }
      
      if (content.includes(normalized)) {
        score += 5
      }
      
      // Check for word boundaries (better match)
      const wordBoundary = new RegExp(`\\b${normalized}\\b`, 'i')
      if (wordBoundary.test(content)) {
        score += 3
      }
      
      if (score > 0) {
        results.push({
          ...entry,
          score,
          snippet: this._generateSnippet(entry.content, normalized),
        })
      }
    }
    
    // Sort by score descending
    results.sort((a, b) => b.score - a.score)
    
    return results.slice(0, 50) // Limit to top 50
  }

  _generateSnippet(content, query, contextLength = 150) {
    const lowerContent = content.toLowerCase()
    const lowerQuery = query.toLowerCase()
    const index = lowerContent.indexOf(lowerQuery)
    
    if (index === -1) {
      return content.slice(0, contextLength) + '...'
    }
    
    const start = Math.max(0, index - contextLength / 2)
    const end = Math.min(content.length, index + query.length + contextLength / 2)
    
    let snippet = content.slice(start, end)
    
    if (start > 0) snippet = '...' + snippet
    if (end < content.length) snippet = snippet + '...'
    
    // Highlight query
    const regex = new RegExp(`(${query})`, 'gi')
    snippet = snippet.replace(regex, '<mark>$1</mark>')
    
    return snippet
  }
}

// Initialize search on page load
let searchInstance = null

function _normalizePathnameToFile(pathname) {
  // pathname is typically like "/ru/sections/00-intro/index.html"
  // or "/ru/" when served with directory indexes.
  let p = pathname || ''
  // Strip query/hash if present (defensive)
  p = p.split('?')[0].split('#')[0]
  // Drop leading slash
  p = p.replace(/^\//, '')
  // Treat empty as index.html
  if (!p) return 'index.html'
  // If ends with slash, assume index.html
  if (p.endsWith('/')) return p + 'index.html'
  return p
}

function _relUrl(fromFile, toFile) {
  const [toPath, hash] = toFile.split('#', 2)

  const fromParts = fromFile.split('/').slice(0, -1) // directory parts
  const toParts = toPath.split('/').filter(Boolean)

  // Find common prefix
  let common = 0
  while (common < fromParts.length && common < toParts.length) {
    if (fromParts[common] === toParts[common]) common += 1
    else break
  }

  const upCount = fromParts.length - common
  const downParts = toParts.slice(common)

  const parts = []
  for (let i = 0; i < upCount; i += 1) parts.push('..')
  parts.push(...downParts)

  let rel = parts.length ? parts.join('/') : '.'
  if (hash) rel += `#${hash}`
  return rel
}

document.addEventListener('DOMContentLoaded', () => {
  const locale = document.documentElement.lang || 'en'
  searchInstance = new ReportSearch(locale)
  
  // Setup search input
  const searchInput = document.getElementById('search-input')
  const searchResults = document.getElementById('search-results')
  
  if (searchInput) {
    let debounceTimer
    
    searchInput.addEventListener('input', async (e) => {
      clearTimeout(debounceTimer)
      
      debounceTimer = setTimeout(async () => {
        const query = e.target.value
        
        if (!query || query.length < 2) {
          searchResults.innerHTML = ''
          searchResults.style.display = 'none'
          return
        }
        
        // Lazy load index
        if (!searchInstance.isLoaded) {
          searchResults.innerHTML = '<div class="search-loading">Loading search index...</div>'
          searchResults.style.display = 'block'
          await searchInstance.init()
        }
        
        // Perform search
        const results = searchInstance.search(query)
        
        if (results.length === 0) {
          searchResults.innerHTML = '<div class="search-empty">No results found</div>'
        } else {
          const fromFile = _normalizePathnameToFile(window.location.pathname)
          searchResults.innerHTML = results.map(r => `
            <a href="${_relUrl(fromFile, r.url)}" class="search-result">
              <div class="search-result__section">${r.section_title}</div>
              <div class="search-result__content">${r.snippet}</div>
            </a>
          `).join('')
        }
        
        searchResults.style.display = 'block'
      }, 300)
    })
    
    // Close results on click outside
    document.addEventListener('click', (e) => {
      if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
        searchResults.style.display = 'none'
      }
    })
  }
})
