/**
 * ESG Report Creator - Static Site Scripts
 * Spec reference: 10_Static_Export.md
 */

// Mobile navigation toggle
document.addEventListener('DOMContentLoaded', () => {
  const navToggle = document.getElementById('nav-toggle')
  const nav = document.querySelector('.rpt-nav')
  
  if (navToggle && nav) {
    navToggle.addEventListener('click', () => {
      nav.classList.toggle('rpt-nav--open')
      navToggle.setAttribute(
        'aria-expanded',
        nav.classList.contains('rpt-nav--open')
      )
    })
  }
  
  // Close nav on link click (mobile)
  if (nav) {
    nav.querySelectorAll('.rpt-nav__link').forEach(link => {
      link.addEventListener('click', () => {
        nav.classList.remove('rpt-nav--open')
        if (navToggle) {
          navToggle.setAttribute('aria-expanded', 'false')
        }
      })
    })
  }
  
  // Smooth scroll to anchors
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      e.preventDefault()
      const target = document.querySelector(this.getAttribute('href'))
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    })
  })

  // Preview iframe navigation helper:
  // In authoring UI we render preview via srcDoc (parent fetches HTML with Authorization).
  // Links inside preview that point to /api/v1/preview/* would otherwise 401.
  // We intercept these clicks and ask the parent window to navigate.
  if (window.parent && window.parent !== window) {
    document.addEventListener('click', (e) => {
      const target = e.target
      if (!(target instanceof Element)) return

      const link = target.closest('a[href]')
      if (!link) return

      const href = link.getAttribute('href') || ''
      if (!href.startsWith('/api/v1/preview/')) return

      e.preventDefault()
      e.stopPropagation()
      
      try {
        // Use '*' as targetOrigin because srcDoc iframes have origin 'null'
        console.log('[preview] Navigating to:', href)
        window.parent.postMessage({ type: 'preview:navigate', url: href }, '*')
      } catch (err) {
        console.error('[preview] postMessage failed:', err)
      }
    }, true) // Use capture phase to intercept before other handlers
  }
  
  // Table overflow shadow indicators
  document.querySelectorAll('.rpt-table-wrapper').forEach(wrapper => {
    const table = wrapper.querySelector('.rpt-table')
    if (!table) return
    
    const updateShadows = () => {
      const scrollLeft = wrapper.scrollLeft
      const scrollWidth = wrapper.scrollWidth
      const clientWidth = wrapper.clientWidth
      
      wrapper.classList.toggle('has-scroll-left', scrollLeft > 0)
      wrapper.classList.toggle('has-scroll-right', scrollLeft + clientWidth < scrollWidth - 1)
    }
    
    wrapper.addEventListener('scroll', updateShadows)
    updateShadows()
  })
})

// Print optimization
window.addEventListener('beforeprint', () => {
  document.body.classList.add('is-printing')
})

window.addEventListener('afterprint', () => {
  document.body.classList.remove('is-printing')
})

