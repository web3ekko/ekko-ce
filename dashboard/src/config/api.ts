/**
 * API Configuration
 * 
 * Central configuration for API endpoints and settings
 */

// API Base URLs
export const API_CONFIG = {
  // Django API base URL
  BASE_URL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  
  // API version
  VERSION: 'v1',
  
  // Timeout settings
  TIMEOUT: 30000, // 30 seconds
  
  // Retry settings
  RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 1000, // 1 second
} as const

// API Endpoints
export const API_ENDPOINTS = {
  // Authentication - Signup
  AUTH: {
    // Signup flow
    SIGNUP: '/api/auth/signup/',
    SIGNUP_VERIFY_CODE: '/api/auth/signup/verify-code/',
    SIGNUP_PASSKEY_REGISTER: '/api/auth/signup/passkey/register/',
    SIGNUP_PASSKEY_SKIP: '/api/auth/signup/passkey/skip/',

    // Auth options (check account status)
    OPTIONS: '/api/auth/options/',
    CHECK_ACCOUNT_STATUS: '/api/auth/check-account-status/',

    // Sign-in - Passkey flow
    SIGNIN_PASSKEY_BEGIN: '/api/auth/signin/passkey/begin/',
    SIGNIN_PASSKEY_COMPLETE: '/api/auth/signin/passkey/complete/',

    // Sign-in - Email code flow
    SIGNIN_EMAIL_SEND_CODE: '/api/auth/signin/email/send-code/',
    SIGNIN_EMAIL_VERIFY_CODE: '/api/auth/signin/email/verify-code/',

    // Common
    RESEND_CODE: '/api/auth/resend-code/',
    LOGOUT: '/api/auth/logout/',
    PROFILE: '/api/auth/profile/',

    // Passkey management
    PASSKEY_REGISTER: '/api/auth/passkey/register/',
    PASSKEY_AUTHENTICATE: '/api/auth/passkey/authenticate/',
    PASSKEY_LIST: '/api/auth/passkey/list/',
    PASSKEY_DELETE: (id: number) => `/api/auth/passkey/${id}/delete/`,

    // Recovery
    RECOVERY_REQUEST: '/api/auth/recovery/request/',
    RECOVERY_VERIFY_CODE: '/api/auth/recovery/verify-code/',
    RECOVERY_COMPLETE: '/api/auth/recovery/complete/',

    // Firebase
    FIREBASE_TOKEN: '/api/auth/firebase-token/',
    FIREBASE_CONFIG: '/api/auth/firebase/config/',

    // Knox tokens
    TOKEN_REFRESH: '/api/auth/knox/refresh/',
    TOKEN_INFO: '/api/auth/knox/token-info/',


    PASSKEY_CHALLENGE: '/api/auth/signin/passkey/begin/',
    PASSKEY_VERIFY: '/api/auth/signin/passkey/complete/',
    ME: '/api/auth/profile/',
  },
  
  // Alerts
  ALERTS: {
    LIST: '/api/alerts/',
    CREATE: '/api/alerts/',
    DETAIL: (id: string) => `/api/alerts/${id}/`,
    UPDATE: (id: string) => `/api/alerts/${id}/`,
    DELETE: (id: string) => `/api/alerts/${id}/`,
    TOGGLE: (id: string) => `/api/alerts/${id}/toggle/`,
    BULK_DELETE: '/api/alerts/bulk-delete/',
    TEMPLATES: '/api/alert-templates/',
    // NLP Parse endpoint - parse natural language without creating alert
    PARSE: '/api/alerts/parse/',
    REPROCESS: (id: string) => `/api/alerts/${id}/reprocess/`,
    // Preview/Dry-Run endpoints - test alerts against historical data
    PREVIEW: (id: string) => `/api/alerts/${id}/preview/`,
    TEMPLATE_PREVIEW: (id: string) => `/api/alert-templates/${id}/preview/`,
    // Inline preview - accepts spec directly, no template_id required
    INLINE_PREVIEW: '/api/alerts/inline-preview/',
  },
  
  // Dashboard Stats API (v1)
  DASHBOARD: {
    STATS: '/api/v1/dashboard/stats/',
    ACTIVITY: '/api/v1/dashboard/activity/',
    CHAIN_STATS: '/api/v1/dashboard/chain-stats/',
    // Legacy aliases
    RECENT_ALERTS: '/api/v1/dashboard/activity/',
  },
  
  // User Profile API (v1)
  PROFILE: {
    GET: '/api/v1/profile/',
    UPDATE: '/api/v1/profile/',
    PREFERENCES: '/api/v1/profile/preferences/',
    AVATAR: '/api/v1/profile/avatar/',
    CONNECTED_SERVICES: '/api/v1/profile/connected-services/',
    CONNECTED_SERVICE_DETAIL: (id: string) => `/api/v1/profile/connected-services/${id}/`,
    SESSIONS: '/api/v1/profile/sessions/',
    SESSION_DETAIL: (id: string) => `/api/v1/profile/sessions/${id}/`,
    SESSIONS_REVOKE_ALL: '/api/v1/profile/sessions/revoke-all/',
    EXPORT_DATA: '/api/v1/profile/export/',
    DELETE_ACCOUNT: '/api/v1/profile/delete/',
  },

  // Teams API (v1)
  TEAMS: {
    LIST: '/api/v1/teams/',
    MEMBERS: (teamId: string) => `/api/v1/teams/${teamId}/members/`,
    INVITE: (teamId: string) => `/api/v1/teams/${teamId}/invite/`,
    MEMBER_DETAIL: (teamId: string, memberId: string) =>
      `/api/v1/teams/${teamId}/members/${memberId}/`,
    MEMBER_RESEND_INVITE: (teamId: string, memberId: string) =>
      `/api/v1/teams/${teamId}/members/${memberId}/resend-invite/`,
  },

  // Generic Groups (unified API for all group types)
  GROUPS: {
    LIST: '/api/groups/',
    PUBLIC: '/api/groups/public/',
    CREATE: '/api/groups/',
    DETAIL: (id: string) => `/api/groups/${id}/`,
    UPDATE: (id: string) => `/api/groups/${id}/`,
    DELETE: (id: string) => `/api/groups/${id}/`,
    // Accounts (system wallet group)
    ACCOUNTS: '/api/groups/accounts/',
    ACCOUNTS_ADD_WALLET: '/api/groups/accounts/add_wallet/',
    ACCOUNTS_ADD_WALLETS: '/api/groups/accounts/add_wallets/',
    // Member management
    ADD_MEMBERS: (id: string) => `/api/groups/${id}/add_members/`,
    REMOVE_MEMBERS: (id: string) => `/api/groups/${id}/remove_members/`,
    UPDATE_MEMBERS: (id: string) => `/api/groups/${id}/update_members/`,
    LIST_MEMBERS: (id: string) => `/api/groups/${id}/members/`,
    // AlertGroups
    TEMPLATES: (id: string) => `/api/groups/${id}/templates/`,
    // Filtering
    BY_TYPE: '/api/groups/by_type/',
    SUMMARY: '/api/groups/summary/',
  },

  // Group Subscriptions (link alert groups to target groups)
  SUBSCRIPTIONS: {
    LIST: '/api/subscriptions/',
    CREATE: '/api/subscriptions/',
    DETAIL: (id: string) => `/api/subscriptions/${id}/`,
    UPDATE: (id: string) => `/api/subscriptions/${id}/`,
    DELETE: (id: string) => `/api/subscriptions/${id}/`,
    TOGGLE: (id: string) => `/api/subscriptions/${id}/toggle/`,
    BY_ALERT_GROUP: '/api/subscriptions/by_alert_group/',
    BY_TARGET_GROUP: '/api/subscriptions/by_target_group/',
  },

  // Wallet nicknames (user-scoped)
  WALLET_NICKNAMES: {
    LIST: '/api/wallet-nicknames/',
    CREATE: '/api/wallet-nicknames/',
    DETAIL: (id: string) => `/api/wallet-nicknames/${id}/`,
    UPDATE: (id: string) => `/api/wallet-nicknames/${id}/`,
    DELETE: (id: string) => `/api/wallet-nicknames/${id}/`,
  },

  // Chains (read-only)
  CHAINS: {
    LIST: '/api/chains/',
    SUB_CHAINS: (id: string) => `/api/chains/${id}/sub_chains/`,
  },



  // Alert Templates
  ALERT_TEMPLATES: {
    LIST: '/api/alert-templates/',
    DETAIL: (id: string) => `/api/alert-templates/${id}/`,
    CATEGORIES: '/api/alert-templates/by_event_type/',
    POPULAR: '/api/alert-templates/popular/',
    INSTANTIATE: (id: string) => `/api/alert-templates/${id}/instantiate/`,
  },

  // Global Search
  SEARCH: {
    GLOBAL: '/api/v1/search/',
    ALERTS: '/api/v1/search/alerts/',
    WALLETS: '/api/v1/search/wallets/',
    TRANSACTIONS: '/api/v1/search/transactions/',
    SUGGESTIONS: '/api/v1/search/suggestions/',
  },

  // Billing API (v1)
  BILLING: {
    OVERVIEW: '/api/v1/billing/overview/',
    SUBSCRIPTION: '/api/v1/billing/subscription/',
  },

  // Developer API (v1)
  DEVELOPER: {
    API_KEYS: '/api/v1/developer/api-keys/',
    API_KEY_DETAIL: (id: string) => `/api/v1/developer/api-keys/${id}/`,
    API_KEY_REVOKE: (id: string) => `/api/v1/developer/api-keys/${id}/revoke/`,
    USAGE: '/api/v1/developer/usage/',
    ENDPOINTS: '/api/v1/developer/endpoints/',
  },

  // Analytics & Newsfeed
  ANALYTICS: {
    HEALTH: '/api/v1/analytics/health/',
    SNAPSHOTS: '/api/v1/analytics/snapshots/',
    TABLES: '/api/v1/analytics/tables/',
    TABLE_SCHEMA: (tableName: string) => `/api/v1/analytics/tables/${tableName}/schema/`,
    WALLET_TRANSACTIONS: (address: string) => `/api/v1/analytics/wallet/${address}/transactions/`,
    WALLET_TRANSFERS: (address: string) => `/api/v1/analytics/wallet/${address}/transfers/`,
    WALLET_BALANCES: (address: string) => `/api/v1/analytics/wallet/${address}/balances/`,
    BLOCK_INFO: (blockNumber: number) => `/api/v1/analytics/block/${blockNumber}/`,
    TOKEN_PRICES: (tokenAddress: string) => `/api/v1/analytics/token/${tokenAddress}/prices/`,
    // Newsfeed - Transaction feed for monitored wallets
    NEWSFEED_TRANSACTIONS: '/api/v1/analytics/newsfeed/transactions/',
  },
  
  // Notifications
  NOTIFICATIONS: {
    CHANNELS: '/api/notifications/channels/',
    CHANNEL_DETAIL: (id: string) => `/api/notifications/channels/${id}/`,
    CHANNEL_TEST: (id: string) => `/api/notifications/channels/${id}/test/`,
    CHANNEL_STATS: (id: string) => `/api/notifications/channels/${id}/stats/`,
    CHANNEL_VERIFY: (id: string) => `/api/notifications/channels/${id}/verify/`,
    CHANNEL_REQUEST_VERIFICATION: (id: string) => `/api/notifications/channels/${id}/request_verification/`,
    CHANNEL_RESEND_VERIFICATION: (id: string) => `/api/notifications/channels/${id}/resend_verification/`,
    SETTINGS: '/api/notification-settings/',
    TEST: '/api/notification-settings/test_notification/',
    DELIVERIES: '/api/notification-deliveries/',
    DELIVERY_STATS: '/api/notification-deliveries/statistics/',
    HISTORY: '/api/notifications/history/',
  },
} as const

// Build full API URL
export const buildApiUrl = (endpoint: string): string => {
  const baseUrl = API_CONFIG.BASE_URL.replace(/\/$/, '') // Remove trailing slash
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  
  return `${baseUrl}${cleanEndpoint}`
}

// HTTP Methods
export const HTTP_METHODS = {
  GET: 'GET',
  POST: 'POST',
  PUT: 'PUT',
  PATCH: 'PATCH',
  DELETE: 'DELETE',
} as const

// Content Types
export const CONTENT_TYPES = {
  JSON: 'application/json',
  FORM_DATA: 'multipart/form-data',
  URL_ENCODED: 'application/x-www-form-urlencoded',
} as const

// API Response Types
export interface ApiResponse<T = any> {
  data: T
  message?: string
  status: number
  success: boolean
}

export interface ApiError {
  message: string
  status: number
  code?: string
  details?: Record<string, any>
}

export interface PaginatedResponse<T> {
  results: T[]
  count: number
  next: string | null
  previous: string | null
  page: number
  page_size: number
  total_pages: number
}

// Request/Response Interceptor Types
export interface RequestConfig {
  url: string
  method: string
  headers?: Record<string, string>
  data?: any
  params?: Record<string, any>
  timeout?: number
}

export interface ResponseConfig<T = any> {
  data: T
  status: number
  statusText: string
  headers: Record<string, string>
  config: RequestConfig
}
