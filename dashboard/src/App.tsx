import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useCallback } from 'react'
import { useAuthStore } from './store/auth'
import { WebSocketProvider } from './providers/WebSocketProvider'

// Layout components
import { AuthLayout } from './components/layout/AuthLayout'
import { DashboardLayout } from './components/layout/DashboardLayout'

// Auth pages
import { LoginPage } from './pages/auth/LoginPage'
import { SignupPage } from './pages/auth/SignupPage'
// Alternate auth routes (email-only)
import { LoginPageNew } from './pages/auth/LoginPageNew'
import { SignupPageNew } from './pages/auth/SignupPageNew'
import { RecoveryPage } from './pages/auth/RecoveryPage'

// Dashboard pages
import { DashboardHome } from './pages/dashboard/DashboardHome'
import { DashboardHomeExecutive } from './pages/dashboard/DashboardHomeExecutive'
import { AlertsPage } from './pages/AlertsPage'
import { WalletsPage } from './pages/WalletsPage'
import { DeveloperAPIPage } from './pages/DeveloperAPIPage'
import { TeamPage } from './pages/TeamPage'
import { MarketplacePage } from './pages/marketplace/MarketplacePage'
import { MarketplaceTemplateDetailPage } from './pages/marketplace/MarketplaceTemplateDetailPage'
import { HelpPage } from './pages/HelpPage'
import { ProfilePage } from './pages/settings/ProfilePage'
import { SettingsPage } from './pages/settings/SettingsPage'
import { SecurityPage } from './pages/settings/SecurityPage'
import { BillingPage } from './pages/settings/BillingPage'
import { NotificationsPage } from './pages/settings/NotificationsPage'
import { WalletGroupsPage } from './pages/wallets/WalletGroupsPage'
import { WalletGroupDetailPage } from './pages/wallets/WalletGroupDetailPage'
import { WalletDetailPage } from './pages/wallets/WalletDetailPage'
import { ProviderWalletsPage } from './pages/wallets/ProviderWalletsPage'
import { AlertGroupsPage } from './pages/alerts/AlertGroupsPage'
import { AlertGroupDetailPage } from './pages/alerts/AlertGroupDetailPage'
import { WebhooksPage } from './pages/dashboard/WebhooksPage'
import { AlertDetailPage } from './pages/dashboard/AlertDetailPage'
import { TestPage } from './pages/TestPage'



// Protected route component
import { ProtectedRoute } from './components/auth/ProtectedRoute'

function App() {
  const { isAuthenticated, logout } = useAuthStore()

  // Handle session expired events from http-client
  const handleSessionExpired = useCallback(() => {
    // Clear auth state and let the isAuthenticated change trigger redirect
    logout()
  }, [logout])

  useEffect(() => {
    window.addEventListener('auth:session-expired', handleSessionExpired)
    return () => {
      window.removeEventListener('auth:session-expired', handleSessionExpired)
    }
  }, [handleSessionExpired])

  return (
      <Routes>
        {/* Test route */}
        <Route path="/test" element={<TestPage />} />


        {/* Public routes */}
        <Route path="/auth" element={<AuthLayout />}>
          <Route path="login" element={<LoginPage />} />
          <Route path="signup" element={<SignupPage />} />
          <Route path="recovery" element={<RecoveryPage />} />
          {/* Alternate auth routes for testing */}
          <Route path="login-new" element={<LoginPageNew />} />
          <Route path="signup-new" element={<SignupPageNew />} />
        </Route>

        {/* Protected routes */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <WebSocketProvider>
                <DashboardLayout />
              </WebSocketProvider>
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardHomeExecutive />} />
          <Route path="classic" element={<DashboardHome />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="alerts/groups" element={<AlertGroupsPage />} />
          <Route path="alerts/groups/:id" element={<AlertGroupDetailPage />} />
          <Route path="alerts/:id" element={<AlertDetailPage />} />
          <Route path="wallets" element={<WalletsPage />} />
          <Route path="wallets/:id" element={<WalletDetailPage />} />
          <Route path="wallets/groups" element={<WalletGroupsPage />} />
          <Route path="wallets/groups/:id" element={<WalletGroupDetailPage />} />
          <Route path="wallets/providers" element={<ProviderWalletsPage />} />
          <Route path="marketplace" element={<MarketplacePage />} />
          <Route path="marketplace/templates/:id" element={<MarketplaceTemplateDetailPage />} />
          <Route path="api" element={<DeveloperAPIPage />} />
          <Route path="webhooks" element={<WebhooksPage />} />
          <Route path="team" element={<TeamPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="settings/security" element={<SecurityPage />} />
          <Route path="settings/billing" element={<BillingPage />} />
          <Route path="settings/notifications" element={<NotificationsPage />} />
          <Route path="help" element={<HelpPage />} />
        </Route>

        {/* Root redirect */}
        <Route
          path="/"
          element={
            isAuthenticated ? (
              <Navigate to="/dashboard" replace />
            ) : (
              <Navigate to="/auth/login" replace />
            )
          }
        />

        {/* Catch all redirect */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
  )
}

export default App
