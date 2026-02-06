/**
 * Protected Route Component
 *
 * Wrapper component that protects routes requiring authentication.
 * Validates Knox token with backend on mount to ensure token is still valid.
 * Can be bypassed with VITE_DEMO_MODE=true for demos and testing.
 */

import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../store/auth'
import { LoadingOverlay } from '@mantine/core'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, tokens, validateSession } = useAuthStore()
  const location = useLocation()
  const [isValidating, setIsValidating] = useState(true)
  const [isValid, setIsValid] = useState<boolean | null>(null)

  // Demo mode - allows access without authentication for demos/testing
  const isDemoMode = import.meta.env.VITE_DEMO_MODE === 'true'

  // Validate token on mount
  useEffect(() => {
    // Skip validation in demo mode
    if (isDemoMode) {
      setIsValidating(false)
      setIsValid(true)
      return
    }

    // If no tokens, no need to validate
    if (!tokens?.access) {
      setIsValidating(false)
      setIsValid(false)
      return
    }

    // Validate the token with backend
    validateSession()
      .then((valid) => {
        setIsValid(valid)
      })
      .catch(() => {
        setIsValid(false)
      })
      .finally(() => {
        setIsValidating(false)
      })
  }, [tokens?.access, validateSession, isDemoMode])

  // Show loading while checking authentication or validating token
  if (isLoading || isValidating) {
    return <LoadingOverlay visible />
  }

  // Allow access without authentication in demo mode
  if (isDemoMode) {
    return <>{children}</>
  }

  // Redirect to login if not authenticated or token validation failed
  if (!isAuthenticated || isValid === false) {
    return (
      <Navigate
        to="/auth/login"
        state={{ from: location }}
        replace
      />
    )
  }

  // Render protected content
  return <>{children}</>
}
