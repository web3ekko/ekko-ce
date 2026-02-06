/**
 * Alert System Types
 * 
 * TypeScript interfaces for alerts and templates
 * that match the Django API and alert specification structure
 */

// Base alert specification structure (matches backend)
export interface AlertSpec {
  name: string
  nl_description: string
  event_type: EventType
  sub_event: string
  scope: AlertScope
  trigger: AlertTrigger
  condition: AlertCondition
  outputs: AlertOutputs
  version: number
  enabled: boolean
  created_at: string
  author: string
}

// Event taxonomy
export type EventType = 
  | 'ACCOUNT_EVENT'
  | 'CONTRACT_EVENT' 
  | 'PROTOCOL_EVENT'
  | 'ANOMALY_EVENT'
  | 'PERFORMANCE_EVENT'

export interface AlertScope {
  chains: string[]
  addresses?: string[]
  contracts?: string[]
  window: {
    size: string  // e.g., "10m", "1h", "1d"
    grace: string // e.g., "2m", "5m"
  }
  filters?: Record<string, any>
}

export interface AlertTrigger {
  mode: 'event' | 'schedule'
  event?: {
    source: string
    conditions?: Record<string, any>
  }
  schedule?: {
    cron: string
    timezone: string
  }
  priority: 'high' | 'normal' | 'low'
  max_runtime_ms: number
}

export interface AlertCondition {
  engine: 'polars' | 'sql'
  code: string
  return_on_match: string[]
  parameters?: Record<string, any>
}

export interface AlertOutputs {
  channels: string[]
  payload_template: {
    title: string
    body: string
    variables?: Record<string, any>
  }
  throttle: {
    mode: 'debounce' | 'rate_limit'
    interval: string
  }
  escalation?: EscalationRule[]
}

export interface EscalationRule {
  after: string // e.g., "15m"
  channels: string[]
  condition?: string
}

// Alert entity (database record)
export interface Alert {
  id: string
  name: string
  description: string
  spec: AlertSpec
  template_id?: string
  template_params?: Record<string, any>
  
  // Metadata
  created_by: string
  created_at: string
  updated_at: string
  team_id?: string
  
  // Status
  enabled: boolean
  status: AlertStatus
  last_triggered?: string
  trigger_count: number
  
  // Performance
  avg_execution_time?: number
  success_rate?: number
  error_count: number
  last_error?: string
}

export type AlertStatus = 
  | 'active'
  | 'paused' 
  | 'error'
  | 'draft'

// Alert templates
export interface AlertTemplate {
  id: string
  name: string
  description: string
  category: TemplateCategory
  tags: string[]
  
  // Template specification
  spec_template: Partial<AlertSpec>
  parameters: TemplateParameter[]
  example_values: Record<string, any>
  
  // Metadata
  created_by: string
  created_at: string
  updated_at: string
  is_public: boolean
  
  // Usage stats
  usage_count: number
  rating: number
  reviews_count: number
}

export type TemplateCategory = 
  | 'account_monitoring'
  | 'contract_events'
  | 'defi_protocols'
  | 'nft_tracking'
  | 'governance'
  | 'security'
  | 'performance'
  | 'custom'

export interface TemplateParameter {
  name: string
  type: 'string' | 'number' | 'boolean' | 'array' | 'address' | 'token'
  description: string
  required: boolean
  default_value?: any
  validation?: {
    min?: number
    max?: number
    pattern?: string
    options?: string[]
  }
  placeholder?: string
  help_text?: string
}

// Alert execution and monitoring
export interface AlertExecution {
  id: string
  alert_id: string
  started_at: string
  completed_at?: string
  status: ExecutionStatus
  trigger_data?: any
  result_data?: any
  execution_time_ms?: number
  error_message?: string
  notifications_sent: number
}

export type ExecutionStatus = 
  | 'running'
  | 'completed'
  | 'failed'
  | 'timeout'
  | 'cancelled'

export interface AlertMetrics {
  alert_id: string
  period: string // e.g., "24h", "7d", "30d"
  executions: number
  successes: number
  failures: number
  avg_execution_time: number
  notifications_sent: number
  last_execution: string
}

// API request/response types
export interface CreateAlertRequest {
  name: string
  description?: string
  spec: AlertSpec
  template_id?: string
  template_params?: Record<string, any>
  team_id?: string
}

export interface UpdateAlertRequest {
  name?: string
  description?: string
  spec?: Partial<AlertSpec>
  enabled?: boolean
}

export interface AlertListResponse {
  alerts: Alert[]
  total: number
  page: number
  per_page: number
  has_next: boolean
  has_prev: boolean
}

export interface AlertFilters {
  status?: AlertStatus[]
  event_type?: EventType[]
  created_by?: string[]
  team_id?: string
  search?: string
  tags?: string[]
  date_range?: {
    start: string
    end: string
  }
}

export interface AlertSortOptions {
  field: 'name' | 'created_at' | 'updated_at' | 'last_triggered' | 'trigger_count'
  direction: 'asc' | 'desc'
}

// Notification channel types (for alert outputs)
export interface NotificationChannel {
  id: string
  name: string
  type: ChannelType
  configuration: ChannelConfiguration
  enabled: boolean
  team_id?: string
  created_by: string
}

export type ChannelType = 
  | 'email'
  | 'slack'
  | 'discord'
  | 'webhook'
  | 'sms'
  | 'push'
  | 'teams'
  | 'pagerduty'

export interface ChannelConfiguration {
  // Email
  email_address?: string
  email_template?: string
  
  // Slack
  slack_webhook_url?: string
  slack_channel?: string
  slack_mention_users?: string[]
  
  // Discord
  discord_webhook_url?: string
  discord_channel_id?: string
  
  // Webhook
  webhook_url?: string
  webhook_headers?: Record<string, string>
  webhook_method?: 'POST' | 'PUT'
  
  // SMS
  phone_number?: string
  
  // Teams
  teams_webhook_url?: string
  
  // PagerDuty
  pagerduty_integration_key?: string
  pagerduty_severity?: 'info' | 'warning' | 'error' | 'critical'
}

// Error types
export interface AlertError {
  code: string
  message: string
  details?: Record<string, any>
  timestamp: string
}
