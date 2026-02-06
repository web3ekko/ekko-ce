/**
 * Search API Service
 *
 * API calls for global search functionality (Command Palette)
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS } from '../config/api'

// Types
export type SearchResultType = 'alert' | 'wallet' | 'transaction' | 'page' | 'action' | 'template'

export interface SearchResult {
  id: string
  type: SearchResultType
  title: string
  subtitle?: string
  description?: string
  icon?: string
  url?: string
  metadata?: Record<string, any>
  score?: number
}

export interface AlertSearchResult extends SearchResult {
  type: 'alert'
  metadata: {
    status?: string
    event_type?: string
    network?: string
    trigger_count?: number
    enabled?: boolean
    chain?: string
  }
}

export interface WalletSearchResult extends SearchResult {
  type: 'wallet'
  metadata: {
    address: string
    network: string
    balance?: string
    label?: string
  }
}

export interface TransactionSearchResult extends SearchResult {
  type: 'transaction'
  metadata: {
    hash: string
    network: string
    from: string
    to: string
    value?: string
    timestamp: string
  }
}

export interface PageSearchResult extends SearchResult {
  type: 'page'
  metadata: {
    path: string
    section?: string
  }
}

export interface ActionSearchResult extends SearchResult {
  type: 'action'
  metadata: {
    action: string
    shortcut?: string
  }
}

export interface TemplateSearchResult extends SearchResult {
  type: 'template'
  metadata: {
    event_type?: string
    usage_count?: number
  }
}

export interface GlobalSearchResponse {
  results: SearchResult[]
  total: number
  categories?: {
    alerts: number
    wallets: number
    transactions: number
    pages: number
    actions: number
    templates?: number
  }
  query?: string
  took_ms?: number
}

export interface SearchSuggestion {
  text: string
  type: SearchResultType
  count?: number
}

export interface SearchSuggestionsResponse {
  suggestions: SearchSuggestion[]
  recent_searches: string[]
}

export interface SearchParams {
  query: string
  types?: SearchResultType[]
  limit?: number
  offset?: number
}

class SearchApiService {
  // Global search across all entity types
  async globalSearch(params: SearchParams): Promise<GlobalSearchResponse> {
    try {
      const response = await httpClient.get<GlobalSearchResponse>(
        API_ENDPOINTS.SEARCH.GLOBAL,
        {
          q: params.query,
          types: params.types?.join(','),
          limit: params.limit || 20,
          offset: params.offset || 0,
        }
      )
      return response.data
    } catch (error: any) {
      console.error('Global search failed:', error)
      throw error
    }
  }

  // Search alerts only
  async searchAlerts(query: string, limit: number = 10): Promise<AlertSearchResult[]> {
    try {
      const response = await httpClient.get<{ results: AlertSearchResult[] }>(
        API_ENDPOINTS.SEARCH.ALERTS,
        { q: query, limit }
      )
      return response.data.results
    } catch (error: any) {
      console.error('Search alerts failed:', error)
      throw error
    }
  }

  // Search wallets only
  async searchWallets(query: string, limit: number = 10): Promise<WalletSearchResult[]> {
    try {
      const response = await httpClient.get<{ results: WalletSearchResult[] }>(
        API_ENDPOINTS.SEARCH.WALLETS,
        { q: query, limit }
      )
      return response.data.results
    } catch (error: any) {
      console.error('Search wallets failed:', error)
      throw error
    }
  }

  // Search transactions only
  async searchTransactions(query: string, limit: number = 10): Promise<TransactionSearchResult[]> {
    try {
      const response = await httpClient.get<{ results: TransactionSearchResult[] }>(
        API_ENDPOINTS.SEARCH.TRANSACTIONS,
        { q: query, limit }
      )
      return response.data.results
    } catch (error: any) {
      console.error('Search transactions failed:', error)
      throw error
    }
  }

  // Get search suggestions
  async getSuggestions(query: string): Promise<SearchSuggestionsResponse> {
    try {
      const response = await httpClient.get<SearchSuggestionsResponse>(
        API_ENDPOINTS.SEARCH.SUGGESTIONS,
        { q: query }
      )
      return response.data
    } catch (error: any) {
      console.error('Get search suggestions failed:', error)
      throw error
    }
  }

  // Static pages for navigation search
  private getNavigationPages(): PageSearchResult[] {
    return [
      {
        id: 'page-dashboard',
        type: 'page',
        title: 'Dashboard',
        subtitle: 'Overview and statistics',
        icon: 'home',
        url: '/dashboard',
        metadata: { path: '/dashboard', section: 'main' },
      },
      {
        id: 'page-alerts',
        type: 'page',
        title: 'Alerts',
        subtitle: 'Manage your alerts',
        icon: 'bell',
        url: '/dashboard/alerts',
        metadata: { path: '/dashboard/alerts', section: 'main' },
      },
      {
        id: 'page-alert-groups',
        type: 'page',
        title: 'Alert Groups',
        subtitle: 'Discover and subscribe to alert groups',
        icon: 'folder',
        url: '/dashboard/alerts/groups',
        metadata: { path: '/dashboard/alerts/groups', section: 'alerts' },
      },
      {
        id: 'page-marketplace',
        type: 'page',
        title: 'Marketplace',
        subtitle: 'Browse alert templates',
        icon: 'compass',
        url: '/dashboard/marketplace',
        metadata: { path: '/dashboard/marketplace', section: 'alerts' },
      },
      {
        id: 'page-wallets',
        type: 'page',
        title: 'Wallets',
        subtitle: 'Manage watched wallets',
        icon: 'wallet',
        url: '/dashboard/wallets',
        metadata: { path: '/dashboard/wallets', section: 'main' },
      },
      {
        id: 'page-wallet-groups',
        type: 'page',
        title: 'Wallet Groups',
        subtitle: 'Organize wallets into groups',
        icon: 'folder',
        url: '/dashboard/wallets/groups',
        metadata: { path: '/dashboard/wallets/groups', section: 'wallets' },
      },
      {
        id: 'page-developer',
        type: 'page',
        title: 'Developer API',
        subtitle: 'API keys, webhooks, and documentation',
        icon: 'code',
        url: '/dashboard/api',
        metadata: { path: '/dashboard/api', section: 'main' },
      },
      {
        id: 'page-team',
        type: 'page',
        title: 'Team',
        subtitle: 'Manage team members and permissions',
        icon: 'users',
        url: '/dashboard/team',
        metadata: { path: '/dashboard/team', section: 'main' },
      },
      {
        id: 'page-settings',
        type: 'page',
        title: 'Settings',
        subtitle: 'Account and application settings',
        icon: 'settings',
        url: '/dashboard/settings',
        metadata: { path: '/dashboard/settings', section: 'settings' },
      },
      {
        id: 'page-profile',
        type: 'page',
        title: 'Profile',
        subtitle: 'Your profile and preferences',
        icon: 'user',
        url: '/dashboard/profile',
        metadata: { path: '/dashboard/profile', section: 'settings' },
      },
      {
        id: 'page-security',
        type: 'page',
        title: 'Security',
        subtitle: 'Passkeys and security settings',
        icon: 'shield',
        url: '/dashboard/settings/security',
        metadata: { path: '/dashboard/settings/security', section: 'settings' },
      },
      {
        id: 'page-notifications',
        type: 'page',
        title: 'Notifications',
        subtitle: 'Notification channels and preferences',
        icon: 'bell',
        url: '/dashboard/settings/notifications',
        metadata: { path: '/dashboard/settings/notifications', section: 'settings' },
      },
      {
        id: 'page-billing',
        type: 'page',
        title: 'Billing',
        subtitle: 'Subscription and payment',
        icon: 'credit-card',
        url: '/dashboard/settings/billing',
        metadata: { path: '/dashboard/settings/billing', section: 'settings' },
      },
      {
        id: 'page-help',
        type: 'page',
        title: 'Help & Support',
        subtitle: 'Documentation and support',
        icon: 'help-circle',
        url: '/dashboard/help',
        metadata: { path: '/dashboard/help', section: 'main' },
      },
    ]
  }

  // Static actions for command palette
  private getQuickActions(): ActionSearchResult[] {
    return [
      {
        id: 'action-create-alert',
        type: 'action',
        title: 'Create Alert',
        subtitle: 'Create a new alert',
        icon: 'plus',
        metadata: { action: 'create-alert', shortcut: 'Cmd+Shift+A' },
      },
      {
        id: 'action-add-wallet',
        type: 'action',
        title: 'Add Wallet',
        subtitle: 'Watch a new wallet address',
        icon: 'plus',
        metadata: { action: 'add-wallet', shortcut: 'Cmd+Shift+W' },
      },
      {
        id: 'action-create-group',
        type: 'action',
        title: 'Create Alert Group',
        subtitle: 'Create a new alert group',
        icon: 'folder-plus',
        metadata: { action: 'create-alert-group' },
      },
      {
        id: 'action-export-data',
        type: 'action',
        title: 'Export Data',
        subtitle: 'Download your data',
        icon: 'download',
        metadata: { action: 'export-data' },
      },
      {
        id: 'action-toggle-theme',
        type: 'action',
        title: 'Toggle Theme',
        subtitle: 'Switch between light and dark mode',
        icon: 'sun-moon',
        metadata: { action: 'toggle-theme', shortcut: 'Cmd+Shift+T' },
      },
      {
        id: 'action-logout',
        type: 'action',
        title: 'Sign Out',
        subtitle: 'Sign out of your account',
        icon: 'log-out',
        metadata: { action: 'logout' },
      },
    ]
  }

  // Get all navigable pages (for offline search)
  getPages(): PageSearchResult[] {
    return this.getNavigationPages()
  }

  // Get all quick actions (for offline search)
  getActions(): ActionSearchResult[] {
    return this.getQuickActions()
  }
}

export const searchApiService = new SearchApiService()
export default searchApiService
