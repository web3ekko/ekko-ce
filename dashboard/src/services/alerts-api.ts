/**
 * Alerts API Service
 * 
 * API calls for alert management
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS, type PaginatedResponse } from '../config/api'
import type { SimpleAlert } from '../store/simple-alerts'

// API Types - matches AlertInstanceCreateRequestSerializer on backend
export interface AlertInstanceCreateRequest {
  // vNext: create from saved AlertTemplate v2 (pinned executable bundle)
  template_id: string
  template_version: number
  name?: string
  enabled?: boolean
  trigger_type: 'event_driven' | 'periodic' | 'one_time'
  trigger_config?: Record<string, unknown>
  target_selector: {
    mode: 'keys' | 'group'
    keys?: string[]
    group_id?: string
  }
  variable_values?: Record<string, unknown>
  notification_overrides?: {
    title_template?: string
    body_template?: string
  }
}

export interface UpdateAlertRequest {
  name?: string
  enabled?: boolean
  nl_description?: string
  template_params?: Record<string, unknown>
  alert_type?: 'wallet' | 'network' | 'protocol' | 'token' | 'contract' | 'nft'
  target_group?: string | null
  target_keys?: string[]
}

export interface AlertsListParams {
  page?: number
  page_size?: number
  status?: string
  event_type?: string
  network?: string
  search?: string
  ordering?: string
}

export interface BulkDeleteRequest {
  alert_ids: string[]
}

// NLP Parse Types - Response from /api/alerts/parse/
export interface NLPParseRequest {
  nl_description: string
  pipeline_id?: string
  context?: Record<string, unknown>
}

export interface NLPParsedTemplate {
  event_type: string
  sub_event: string
  scope?: {
    chains?: string[]
    addresses?: string[]
  }
  trigger?: {
    mode?: string
    config?: Record<string, unknown>
  }
  condition?: {
    type?: string
    operator?: string
    threshold?: number
    config?: Record<string, unknown>
  }
  outputs?: {
    channels?: string[]
  }
}

export interface NLPPipelineMetadata {
  classification_confidence: number
  entities_extracted: number
  execution_time_ms?: number
  stages_completed?: string[]
}

export interface NLPParseResult {
  success: boolean
  template?: NLPParsedTemplate
  template_id?: string
  variable_schema?: Record<string, unknown>
  pipeline_metadata?: NLPPipelineMetadata
  error?: string
}

export interface ProposedSpec {
  schema_version?: string
  job_id?: string
  // v1 output (legacy)
  template?: Record<string, unknown>
  // v2 output (template-first authoring)
  // NOTE: NLP output is target-agnostic; targets are supplied via the form on instance creation.
  compiled_executable?: Record<string, unknown>
  compile_report?: Record<string, unknown>
  required_user_inputs?: {
    targets_required?: boolean
    target_kind?: string
    required_variables?: string[]
    suggested_defaults?: Record<string, unknown>
    supported_trigger_types?: string[]
  }
  human_preview?: {
    summary?: string
    segments?: Array<{ kind: string; text: string }>
  }
  confidence?: number
  missing_info?: Array<Record<string, unknown>>
  assumptions?: string[]
  warnings?: string[]
  [key: string]: unknown
}

export interface ParseJobResponse {
  success: boolean
  job_id?: string
  status?: string
  expires_at?: string
  estimated_wait_ms?: number
  error?: string
}

export interface ParseResultResponse {
  status: 'completed' | 'processing' | 'not_found'
  result?: ProposedSpec
  job_id?: string
  error?: string
}

export interface AlertTemplateSaveRequest {
  job_id: string
  publish_to_org?: boolean
  publish_to_marketplace?: boolean
}

export interface AlertTemplateSaveResponse {
  success: boolean
  template_id?: string
  template_version?: number
  fingerprint?: string
  spec_hash?: string
  visibility?: {
    publish_to_org: boolean
    publish_to_marketplace: boolean
  }
  code?: string
  message?: string
  existing_template?: {
    template_id: string
    template_version: number
    fingerprint: string
  }
}

export interface AlertTemplateSummary {
  id: string
  fingerprint: string
  name: string
  description: string
  target_kind: string
  usage_count: number
  is_public: boolean
  is_verified: boolean
  latest_template_version: number
  variable_names: string[]
  scope_networks: string[]
  created_by_email?: string
  created_at: string
  updated_at: string
}

export interface TemplateListParams {
  page?: number
  page_size?: number
  search?: string
  is_public?: boolean
  is_verified?: boolean
  target_kind?: string
  ordering?: string
}

export interface AlertTemplateLatestResponse {
  success: boolean
  template?: (AlertTemplateSummary & { latest_version_bundle?: unknown }) | null
  bundle?: {
    template_version: number
    spec_hash: string
    executable_id: string
    registry_snapshot: Record<string, unknown>
    template_spec: Record<string, unknown>
    executable: Record<string, unknown>
  } | null
  code?: string
  message?: string
}

// Preview/Dry-Run Types - matches PreviewConfigSerializer and PreviewResultSerializer on backend
export interface PreviewConfig {
  time_range?: '1h' | '24h' | '7d' | '30d'
  limit?: number
  include_near_misses?: boolean
  explain_mode?: boolean
  parameters?: Record<string, unknown>
  addresses?: string[]
  chain?: string
}

export interface PreviewSummary {
  total_events_evaluated: number
  would_have_triggered: number
  trigger_rate: number
  estimated_daily_triggers: number
  evaluation_time_ms: number
}

export interface SampleTrigger {
  timestamp: string
  data: Record<string, unknown>
  matched_condition: string
}

export interface NearMiss {
  timestamp: string
  data: Record<string, unknown>
  threshold_distance: number
  explanation: string
}

export interface PreviewResult {
  success: boolean
  preview_id?: string
  summary: PreviewSummary
  sample_triggers?: SampleTrigger[]
  near_misses?: NearMiss[]
  evaluation_mode: 'per_row' | 'aggregate' | 'window' | 'unknown'
  expression?: string
  data_source?: string
  time_range?: string
  requires_wasmcloud?: boolean
  wasmcloud_reason?: string
  error?: string
}

export interface AlertTemplatePreviewRequest {
  job_id: string
  target_selector: {
    mode: 'keys' | 'group'
    keys?: string[]
    group_id?: string
  }
  variable_values?: Record<string, unknown>
  sample_size?: number
  effective_as_of?: string
}

class AlertsApiService {
  // Get alerts list
  async getAlerts(params: AlertsListParams = {}): Promise<PaginatedResponse<SimpleAlert>> {
    try {
      const response = await httpClient.get<PaginatedResponse<SimpleAlert>>(
        API_ENDPOINTS.ALERTS.LIST,
        params
      )
      return response.data
    } catch (error: any) {
      console.error('Get alerts failed:', error)
      throw error
    }
  }

  // Get single alert
  async getAlert(alertId: string): Promise<SimpleAlert> {
    try {
      const response = await httpClient.get<SimpleAlert>(
        API_ENDPOINTS.ALERTS.DETAIL(alertId)
      )
      return response.data
    } catch (error: any) {
      console.error('Get alert failed:', error)
      throw error
    }
  }

  // Create alert
  async createAlert(data: AlertInstanceCreateRequest): Promise<SimpleAlert> {
    try {
      const response = await httpClient.post<SimpleAlert>(
        API_ENDPOINTS.ALERTS.CREATE,
        data
      )
      return response.data
    } catch (error: any) {
      console.error('Create alert failed:', error)
      throw error
    }
  }

  // Update alert
  async updateAlert(alertId: string, data: UpdateAlertRequest): Promise<SimpleAlert> {
    try {
      const response = await httpClient.patch<SimpleAlert>(
        API_ENDPOINTS.ALERTS.UPDATE(alertId),
        data
      )
      return response.data
    } catch (error: any) {
      console.error('Update alert failed:', error)
      throw error
    }
  }

  // Delete alert
  async deleteAlert(alertId: string): Promise<void> {
    try {
      await httpClient.delete(API_ENDPOINTS.ALERTS.DELETE(alertId))
    } catch (error: any) {
      console.error('Delete alert failed:', error)
      throw error
    }
  }

  // Toggle alert enabled/disabled
  async toggleAlert(alertId: string, enabled: boolean): Promise<SimpleAlert> {
    try {
      const response = await httpClient.patch<SimpleAlert>(API_ENDPOINTS.ALERTS.UPDATE(alertId), { enabled })
      return response.data
    } catch (error: any) {
      console.error('Toggle alert failed:', error)
      throw error
    }
  }

  // Bulk delete alerts
  async bulkDeleteAlerts(alertIds: string[]): Promise<void> {
    try {
      await Promise.all(alertIds.map((id) => this.deleteAlert(id)))
    } catch (error: any) {
      console.error('Bulk delete alerts failed:', error)
      throw error
    }
  }

  /**
   * Parse natural language description through NLP pipeline.
   *
   * This implements the two-step flow:
   * 1. Call parseNaturalLanguage to get NLP analysis
   * 2. Use the parsed result to create alert with createAlert
   *
   * @param description - Natural language description of the alert
   * @returns NLP analysis result with parsed template and confidence
   */
  async parseNaturalLanguage(description: string): Promise<NLPParseResult> {
    try {
      const response = await httpClient.post<NLPParseResult>(
        API_ENDPOINTS.ALERTS.PARSE,
        { nl_description: description }
      )
      return response.data
    } catch (error: any) {
      console.error('NLP parse failed:', error)
      // Return error result instead of throwing to allow graceful degradation
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'NLP parsing failed'
      }
    }
  }

  async parseNaturalLanguageJob(
    description: string,
    clientRequestId?: string,
    pipelineId?: string,
    context?: Record<string, unknown>
  ): Promise<ParseJobResponse> {
    try {
      const response = await httpClient.post<ParseJobResponse>(
        API_ENDPOINTS.ALERTS.PARSE,
        { nl_description: description, client_request_id: clientRequestId, pipeline_id: pipelineId, context }
      )
      return response.data
    } catch (error: any) {
      console.error('NLP parse job failed:', error)
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'NLP parsing failed'
      }
    }
  }

  async getParseResult(jobId: string): Promise<ParseResultResponse> {
    try {
      const response = await httpClient.get<ParseResultResponse>(
        `${API_ENDPOINTS.ALERTS.PARSE}${jobId}/`
      )
      return response.data
    } catch (error: any) {
      console.error('Get parse result failed:', error)
      return {
        status: 'not_found',
        error: error.response?.data?.error || error.message || 'Parse result not found',
        job_id: jobId,
      }
    }
  }

  async saveTemplateFromJob(request: AlertTemplateSaveRequest): Promise<AlertTemplateSaveResponse> {
    try {
      const response = await httpClient.post<AlertTemplateSaveResponse>(
        '/api/alert-templates/',
        request
      )
      return response.data
    } catch (error: any) {
      console.error('Save template failed:', error)
      return {
        success: false,
        code: error.response?.data?.code,
        message: error.response?.data?.message || error.message || 'Failed to save template',
      }
    }
  }

  async listTemplates(params: TemplateListParams = {}): Promise<PaginatedResponse<AlertTemplateSummary>> {
    try {
      const response = await httpClient.get<PaginatedResponse<AlertTemplateSummary>>(
        API_ENDPOINTS.ALERTS.TEMPLATES,
        params
      )
      return response.data
    } catch (error: any) {
      console.error('List templates failed:', error)
      throw error
    }
  }

  async getTemplateLatest(templateId: string): Promise<AlertTemplateLatestResponse> {
    try {
      const response = await httpClient.get<AlertTemplateLatestResponse>(
        `/api/alert-templates/${templateId}/latest/`
      )
      return response.data
    } catch (error: any) {
      console.error('Get template latest failed:', error)
      return {
        success: false,
        code: error.response?.data?.code,
        message: error.response?.data?.message || error.message || 'Failed to load template',
      }
    }
  }

  async previewTemplateFromJob(request: AlertTemplatePreviewRequest): Promise<PreviewResult> {
    try {
      const response = await httpClient.post<PreviewResult>('/api/alert-templates/preview/', request)
      return response.data
    } catch (error: any) {
      console.error('Template preview failed:', error)
      return {
        success: false,
        summary: {
          total_events_evaluated: 0,
          would_have_triggered: 0,
          trigger_rate: 0,
          estimated_daily_triggers: 0,
          evaluation_time_ms: 0,
        },
        evaluation_mode: 'unknown',
        error: error.response?.data?.message || error.response?.data?.error || error.message || 'Preview failed',
      }
    }
  }

  async getTemplateDetail(templateId: string): Promise<AlertTemplateSummary> {
    try {
      const response = await httpClient.get<AlertTemplateSummary>(
        API_ENDPOINTS.ALERTS.TEMPLATES + `${templateId}/`
      )
      return response.data
    } catch (error: any) {
      console.error('Get template detail failed:', error)
      throw error
    }
  }

  async getTemplate(templateId: string): Promise<{ id: string; version: number }> {
    const response = await httpClient.get<{ id: string; version: number }>(
      `/api/alert-templates/${templateId}/`
    )
    return response.data
  }

  /**
   * Reprocess a failed NLP alert through the pipeline.
   *
   * @param alertId - ID of the alert to reprocess
   * @returns Updated alert with new processing status
   */
  async reprocessAlert(alertId: string): Promise<SimpleAlert> {
    try {
      const response = await httpClient.post<{ message: string; alert: SimpleAlert }>(
        API_ENDPOINTS.ALERTS.REPROCESS(alertId),
        {}
      )
      return response.data.alert
    } catch (error: any) {
      console.error('Reprocess alert failed:', error)
      throw error
    }
  }

  /**
   * Preview an existing alert against historical data (dry-run).
   *
   * Tests alert conditions without creating any executions or side effects.
   *
   * @param alertId - ID of the alert to preview
   * @param config - Preview configuration (time range, limit, etc.)
   * @returns Preview results with trigger statistics and sample matches
   */
  async previewAlert(alertId: string, config: PreviewConfig = {}): Promise<PreviewResult> {
    try {
      const response = await httpClient.post<PreviewResult>(
        API_ENDPOINTS.ALERTS.PREVIEW(alertId),
        config
      )
      return response.data
    } catch (error: any) {
      console.error('Preview alert failed:', error)
      // Return error result instead of throwing to allow graceful degradation
      return {
        success: false,
        summary: {
          total_events_evaluated: 0,
          would_have_triggered: 0,
          trigger_rate: 0,
          estimated_daily_triggers: 0,
          evaluation_time_ms: 0,
        },
        evaluation_mode: 'unknown',
        error: error.response?.data?.error || error.message || 'Preview failed'
      }
    }
  }

  /**
   * Preview an alert template against historical data (dry-run).
   *
   * Tests template conditions with provided parameters before creating an alert.
   *
   * @param templateId - ID of the template to preview
   * @param config - Preview configuration including parameters to test
   * @returns Preview results with trigger statistics and sample matches
   */
  async previewTemplate(templateId: string, config: PreviewConfig = {}): Promise<PreviewResult> {
    try {
      const response = await httpClient.post<PreviewResult>(
        API_ENDPOINTS.ALERTS.TEMPLATE_PREVIEW(templateId),
        config
      )
      return response.data
    } catch (error: any) {
      console.error('Preview template failed:', error)
      // Return error result instead of throwing to allow graceful degradation
      return {
        success: false,
        summary: {
          total_events_evaluated: 0,
          would_have_triggered: 0,
          trigger_rate: 0,
          estimated_daily_triggers: 0,
          evaluation_time_ms: 0,
        },
        evaluation_mode: 'unknown',
        error: error.response?.data?.error || error.message || 'Preview failed'
      }
    }
  }

  /**
   * Preview an alert using inline spec (no template_id required).
   * This is the primary flow for NL-based alert creation where the spec
   * comes directly from the NLP parse result.
   */
  async previewInline(
    spec: Record<string, unknown>,
    config: PreviewConfig = {},
    alertType: string = 'wallet'
  ): Promise<PreviewResult> {
    try {
      const response = await httpClient.post<PreviewResult>(
        API_ENDPOINTS.ALERTS.INLINE_PREVIEW,
        {
          spec,
          alert_type: alertType,
          ...config,
        }
      )
      return response.data
    } catch (error: any) {
      console.error('Inline preview failed:', error)
      // Return error result instead of throwing to allow graceful degradation
      return {
        success: false,
        summary: {
          total_events_evaluated: 0,
          would_have_triggered: 0,
          trigger_rate: 0,
          estimated_daily_triggers: 0,
          evaluation_time_ms: 0,
        },
        evaluation_mode: 'unknown',
        error: error.response?.data?.error || error.message || 'Preview failed'
      }
    }
  }
}

export const alertsApiService = new AlertsApiService()
export default alertsApiService
