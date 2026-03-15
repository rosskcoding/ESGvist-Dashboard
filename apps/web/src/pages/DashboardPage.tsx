import { Navigate } from 'react-router-dom'

/**
 * Legacy dashboard route — redirects to the ESG dashboard.
 */
export function DashboardPage() {
  return <Navigate to="/esg" replace />
}
