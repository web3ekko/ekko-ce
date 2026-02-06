/**
 * Optimized Create Alert Form
 *
 * Async NLP flow with template save + instance creation
 */

import { useState, useEffect, useMemo, useRef, useCallback, useDeferredValue } from 'react'
import {
  Stack,
  Card,
  Group,
  Title,
  Text,
  Button,
  Collapse,
  Box,
  Alert,
  ActionIcon,
  Tooltip,
  Badge,
  Checkbox,
  Select,
  SegmentedControl,
  TextInput,
  Textarea,
  NumberInput,
  Divider,
  Switch,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import {
  IconWand,
  IconSettings,
  IconAlertCircle,
  IconCheck,
  IconX,
  IconChevronDown,
  IconChevronUp,
  IconTestPipe,
  IconTemplate,
  IconInfoCircle,
} from '@tabler/icons-react'
import { motion, AnimatePresence } from 'framer-motion'

import { NaturalLanguageInputEnhanced } from './NaturalLanguageInputEnhanced'
import { RealtimeUnderstandingPanel } from './RealtimeUnderstandingPanel'
import { VisualQueryPreview } from './VisualQueryPreview'
import { ConfidenceIndicator } from './ConfidenceIndicator'
import { PreviewResultsModal } from './preview'
import { ProgressIndicator } from './ProgressIndicator'
import { AlertEventBadge } from './AlertEventBadge'
import { ChainLogo } from '../brand/ChainLogo'
import { useSimpleAlerts } from '../../store/simple-alerts'
import {
  alertsApiService,
  type AlertTemplateSaveResponse,
  type ProposedSpec,
} from '../../services/alerts-api'
import { useNLPWebSocket } from '../../hooks/useNLPWebSocket'
import { groupsApiService, GroupType, type GenericGroup } from '../../services/groups-api'
import {
  getChainIdentity,
  normalizeChainKey,
} from '../../utils/chain-identity'
import {
  extractTemplateVariables,
  getVariableId,
  isValueProvided,
  type TemplateVariable,
  type TemplateLike,
} from '../../utils/alert-templates'

// Pipeline id is still named "plan compiler" server-side, but it produces AlertTemplate v2 semantics.
const NLP_TEMPLATE_PIPELINE_ID = 'dspy_plan_compiler_v1'
const NLP_MIN_LENGTH = 10
const NLP_DEBOUNCE_MS = 1400
const NLP_CONTEXT_DEBOUNCE_MS = 500
const NLP_SUBMIT_COOLDOWN_MS = 2500

function normalizeNlpInput(input: string): string {
  return input.trim().replace(/\s+/g, ' ')
}

function normalizeForFingerprint(input: string): string {
  return normalizeNlpInput(input).replace(/[.?!,;:]+$/g, '')
}

function stableSerialize(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value !== 'object') return String(value)
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableSerialize(item)).join(',')}]`
  }
  const entries = Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b))
  return `{${entries.map(([key, val]) => `${key}:${stableSerialize(val)}`).join(',')}}`
}

function sanitizeContext(context: Record<string, unknown>): Record<string, unknown> {
  const nextContext = { ...context }
  Object.keys(nextContext).forEach((key) => {
    const value = nextContext[key]
    if (value === null || value === undefined || value === '') delete nextContext[key]
  })
  return nextContext
}

function buildFingerprint(description: string, context: Record<string, unknown>, pipelineId?: string): string {
  const normalized = normalizeForFingerprint(description)
  return `${pipelineId || 'default'}::${normalized}::${stableSerialize(context)}`
}

interface CreateAlertOptimizedProps {
  onAlertCreated: (alert: any) => void
  onCancel: () => void
  initialTemplateRef?: { templateId: string; templateVersion: number } | null
}

export interface ParsedCondition {
  type: string
  field: string
  operator: string
  value: any
  unit?: string
}

export interface ThresholdValue {
  name: string
  value: number
  unit: string
}

export interface VisualQuery {
  when: string
  where: string
  condition: string
  action: string
}

interface UnderstandingState {
  eventType?: string
  subEvent?: string
  conditions?: ParsedCondition[]
  chains?: string[]
  wallets?: string[]
  thresholds?: ThresholdValue[]
}

const initialVisualQuery: VisualQuery = {
  when: '',
  where: '',
  condition: '',
  action: '',
}

const DRAFT_STORAGE_KEY = 'alert_draft_v1'

export function CreateAlertOptimized({ onAlertCreated, onCancel, initialTemplateRef }: CreateAlertOptimizedProps) {
  const [naturalLanguage, setNaturalLanguage] = useState('')
  const [understanding, setUnderstanding] = useState<UnderstandingState>({})
  const [confidence, setConfidence] = useState(0)
  const [visualQuery, setVisualQuery] = useState<VisualQuery>(initialVisualQuery)
  const [parseErrors, setParseErrors] = useState<string[]>([])
  const [proposedSpec, setProposedSpec] = useState<ProposedSpec | null>(null)
  const [savedTemplate, setSavedTemplate] = useState<AlertTemplateSaveResponse | null>(null)
  const [existingTemplate, setExistingTemplate] = useState<AlertTemplateSaveResponse['existing_template'] | null>(null)
  const [isSavingTemplate, setIsSavingTemplate] = useState(false)
  const [isCreatingAlert, setIsCreatingAlert] = useState(false)
  const [templateError, setTemplateError] = useState<string | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)

  const [advancedOpened, { toggle: toggleAdvanced }] = useDisclosure(false)
  const [showUnderstanding, setShowUnderstanding] = useState(false)
  const [showPreview, setShowPreview] = useState(false)

  const [walletGroups, setWalletGroups] = useState<GenericGroup[]>([])
  const [targetMode, setTargetMode] = useState<'group' | 'keys'>('group')
  const [targetGroupId, setTargetGroupId] = useState<string | null>(null)
  const [targetKeysInput, setTargetKeysInput] = useState('')
  const [variableValues, setVariableValues] = useState<Record<string, unknown>>({})
  const [notificationTitle, setNotificationTitle] = useState('')
  const [notificationBody, setNotificationBody] = useState('')
  const [notificationTouched, setNotificationTouched] = useState(false)
  const [triggerType, setTriggerType] = useState<'event_driven' | 'periodic' | 'one_time'>('event_driven')
  const [triggerTypeTouched, setTriggerTypeTouched] = useState(false)
  const [frequencyPreset, setFrequencyPreset] = useState<'realtime' | '5min' | '15min' | '1hour' | 'daily'>('realtime')
  const [frequencyPresetTouched, setFrequencyPresetTouched] = useState(false)
  const [oneTimeRunAt, setOneTimeRunAt] = useState('')
  const [publishToOrg, setPublishToOrg] = useState(false)
  const [publishToMarketplace, setPublishToMarketplace] = useState(false)
  const [nlpContextOverrides, setNlpContextOverrides] = useState<Record<string, unknown>>({})
  const [preferredNetworkTouched, setPreferredNetworkTouched] = useState(false)

  const { previewResult, isPreviewLoading, runInlinePreview, runTemplatePreviewFromJob, clearPreview, createAlert } = useSimpleAlerts()

  const [previewModalOpened, setPreviewModalOpened] = useState(false)
  const [previewTimeRange] = useState<'1h' | '24h' | '7d' | '30d'>('7d')

  const lastSubmittedFingerprintRef = useRef<string | null>(null)
  const lastSubmitAtRef = useRef<number>(0)
  const pendingFingerprintRef = useRef<string | null>(null)
  const parseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const contextChangeRef = useRef(false)

  const isUsingMarketplaceTemplate = Boolean(initialTemplateRef?.templateId)

  const getNotificationDefaults = useCallback((template: unknown) => {
    if (!template || typeof template !== 'object') {
      return { title: '', body: '' }
    }
    const notification = (template as { notification?: unknown }).notification
    if (!notification || typeof notification !== 'object') {
      return { title: '', body: '' }
    }
    const title = (notification as { title_template?: unknown }).title_template
    const body = (notification as { body_template?: unknown }).body_template
    return {
      title: typeof title === 'string' ? title : '',
      body: typeof body === 'string' ? body : '',
    }
  }, [])

  const handleNlpComplete = useCallback((spec: ProposedSpec) => {
    setProposedSpec(spec)
  }, [])

  const handleNlpError = useCallback((message: string) => {
    setParseErrors([message])
  }, [])

  const nlpHandlers = useMemo(
    () => ({ onComplete: handleNlpComplete, onError: handleNlpError }),
    [handleNlpComplete, handleNlpError]
  )

  const { status: nlpStatus, jobId, result, error, progress, submitJob, reset } = useNLPWebSocket(nlpHandlers)
  const reduceMotion = nlpStatus === 'connecting' || nlpStatus === 'processing'
  const deferredNaturalLanguage = useDeferredValue(naturalLanguage)

  const scheduleNlpSubmit = useCallback((
    description: string,
    context: Record<string, unknown>,
    baseDelayMs: number
  ) => {
    const trimmed = normalizeNlpInput(description)
    if (trimmed.length < NLP_MIN_LENGTH) return

    const sanitizedContext = sanitizeContext(context)
    const fingerprint = buildFingerprint(trimmed, sanitizedContext, NLP_TEMPLATE_PIPELINE_ID)
    if (fingerprint === lastSubmittedFingerprintRef.current || fingerprint === pendingFingerprintRef.current) {
      return
    }

    const now = Date.now()
    const cooldownRemaining = Math.max(0, lastSubmitAtRef.current + NLP_SUBMIT_COOLDOWN_MS - now)
    const delay = Math.max(baseDelayMs, cooldownRemaining)

    if (parseTimerRef.current) {
      clearTimeout(parseTimerRef.current)
    }

    pendingFingerprintRef.current = fingerprint
    parseTimerRef.current = setTimeout(() => {
      pendingFingerprintRef.current = null
      lastSubmittedFingerprintRef.current = fingerprint
      lastSubmitAtRef.current = Date.now()
      submitJob(
        trimmed,
        undefined,
        NLP_TEMPLATE_PIPELINE_ID,
        Object.keys(sanitizedContext).length ? sanitizedContext : undefined,
        fingerprint
      )
    }, delay)
  }, [submitJob])

  useEffect(() => {
    return () => {
      if (parseTimerRef.current) {
        clearTimeout(parseTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (notificationTouched) return
    if (proposedSpec?.template) {
      const defaults = getNotificationDefaults(proposedSpec.template)
      setNotificationTitle(defaults.title)
      setNotificationBody(defaults.body)
      return
    }
    if (!isUsingMarketplaceTemplate) {
      setNotificationTitle('')
      setNotificationBody('')
    }
  }, [getNotificationDefaults, isUsingMarketplaceTemplate, notificationTouched, proposedSpec])

  const rerunTemplateCompiler = useCallback((patch: Record<string, unknown>) => {
    if (isUsingMarketplaceTemplate) return
    const trimmed = normalizeNlpInput(naturalLanguage)
    if (trimmed.length < NLP_MIN_LENGTH) return

    const nextContext = sanitizeContext({ ...nlpContextOverrides, ...patch })

    setNlpContextOverrides(nextContext)
    setSavedTemplate(null)
    setExistingTemplate(null)
    setTemplateError(null)
    setCreateError(null)
    contextChangeRef.current = true
  }, [isUsingMarketplaceTemplate, naturalLanguage, nlpContextOverrides])

  useEffect(() => {
    if (isUsingMarketplaceTemplate) return
    const draft = localStorage.getItem(DRAFT_STORAGE_KEY)
    if (draft && draft.trim().length > 0) {
      setNaturalLanguage(draft)
    }
  }, [isUsingMarketplaceTemplate])

  useEffect(() => {
    if (!isUsingMarketplaceTemplate || !initialTemplateRef?.templateId) return

    let isActive = true
    const load = async () => {
      const resp = await alertsApiService.getTemplateLatest(initialTemplateRef.templateId)
      if (!isActive) return
      if (!resp.success || !resp.bundle) {
        setCreateError(resp.message || 'Failed to load template')
        return
      }

      const templateSpec = resp.bundle.template_spec
      const variables = Array.isArray((templateSpec as any)?.variables) ? ((templateSpec as any).variables as any[]) : []
      const requiredVariables = variables
        .map((v) => (v && typeof v === 'object' ? (v.id || v.name) : null))
        .filter((v): v is string => typeof v === 'string' && v.length > 0)

      const suggestedDefaults: Record<string, unknown> = {}
      variables.forEach((v) => {
        if (!v || typeof v !== 'object') return
        const id = (v.id || v.name) as string | undefined
        if (!id) return
        if (v.default !== undefined) suggestedDefaults[id] = v.default
      })

      if (!notificationTouched) {
        const defaults = getNotificationDefaults(templateSpec)
        setNotificationTitle(defaults.title)
        setNotificationBody(defaults.body)
      }

      const evalMode = (templateSpec as any)?.trigger?.evaluation_mode
      const supportedTriggerTypes =
        evalMode === 'event_driven'
          ? ['event_driven']
          : evalMode === 'one_time'
            ? ['one_time']
            : evalMode === 'periodic'
              ? ['periodic']
              : ['event_driven', 'periodic']

      setProposedSpec({
        schema_version: 'proposed_spec_v2',
        job_id: 'marketplace',
        template: templateSpec,
        compiled_executable: resp.bundle.executable,
        required_user_inputs: {
          targets_required: true,
          target_kind: String((templateSpec as any)?.target_kind || 'wallet'),
          required_variables: requiredVariables,
          suggested_defaults: suggestedDefaults,
          supported_trigger_types: supportedTriggerTypes,
        },
        human_preview: {
          summary: String((templateSpec as any)?.name || 'Marketplace template'),
          segments: [],
        },
      })

      setSavedTemplate({
        success: true,
        template_id: initialTemplateRef.templateId,
        template_version: resp.bundle.template_version,
        fingerprint: (resp.template as any)?.fingerprint,
      })

      // Seed a reasonable network context for instance trigger config + target-key building.
      const scopeNetworks = Array.isArray((templateSpec as any)?.scope?.networks) ? ((templateSpec as any).scope.networks as string[]) : []
      const inferredChains = scopeNetworks
        .map((n) => n.split(':')[0]?.toUpperCase())
        .map((prefix) => {
          if (prefix === 'ETH') return 'ethereum'
          if (prefix === 'AVAX') return 'avalanche'
          return null
        })
        .filter((c): c is string => Boolean(c))

      if (inferredChains.length) {
        setUnderstanding((prev) => ({ ...prev, chains: inferredChains }))
      }

      // Avoid accidentally kicking off NLP parse when we hydrate naturalLanguage.
      setNaturalLanguage(String((templateSpec as any)?.name || ''))
      reset()
    }

    load()
    return () => {
      isActive = false
    }
  }, [initialTemplateRef, isUsingMarketplaceTemplate, reset])

  useEffect(() => {
    if (!naturalLanguage) return
    localStorage.setItem(DRAFT_STORAGE_KEY, naturalLanguage)
  }, [naturalLanguage])

  useEffect(() => {
    if (result) {
      setProposedSpec(result)
      setParseErrors([])
      if (typeof result.confidence === 'number' && Number.isFinite(result.confidence)) {
        const pct = Math.max(0, Math.min(100, Math.round(result.confidence * 100)))
        setConfidence(pct)
      }
    }
  }, [result])

  useEffect(() => {
    if (error) {
      setParseErrors([error])
    }
  }, [error])

  useEffect(() => {
    if (isUsingMarketplaceTemplate) return
    const trimmed = normalizeNlpInput(naturalLanguage)
    if (trimmed.length < NLP_MIN_LENGTH) {
      if (parseTimerRef.current) {
        clearTimeout(parseTimerRef.current)
        parseTimerRef.current = null
      }
      pendingFingerprintRef.current = null
      lastSubmittedFingerprintRef.current = null
      lastSubmitAtRef.current = 0
      contextChangeRef.current = false
      setShowUnderstanding(false)
      setShowPreview(false)
      setProposedSpec(null)
      setSavedTemplate(null)
      setExistingTemplate(null)
      setParseErrors([])
      setTemplateError(null)
      setCreateError(null)
      reset()
      return
    }

    setSavedTemplate(null)
    setExistingTemplate(null)
    setTemplateError(null)
    setCreateError(null)

    const baseDelay = contextChangeRef.current ? NLP_CONTEXT_DEBOUNCE_MS : NLP_DEBOUNCE_MS
    contextChangeRef.current = false
    scheduleNlpSubmit(trimmed, nlpContextOverrides, baseDelay)

    return () => {
      if (parseTimerRef.current) {
        clearTimeout(parseTimerRef.current)
      }
    }
  }, [naturalLanguage, reset, isUsingMarketplaceTemplate, nlpContextOverrides, scheduleNlpSubmit])

  useEffect(() => {
    if (proposedSpec?.required_user_inputs?.supported_trigger_types?.length) {
      const supported = proposedSpec.required_user_inputs.supported_trigger_types
      if (supported.includes(triggerType)) return
      const fallback = supported[0] as 'event_driven' | 'periodic' | 'one_time'
      setTriggerType(fallback)
    }
  }, [proposedSpec, triggerType])

  useEffect(() => {
    // If NLP/marketplace selection forces "Scheduled", ensure we have a valid preset so
    // we don't create periodic instances with an empty cron string.
    if (triggerType !== 'periodic') return
    if (frequencyPreset === '5min' || frequencyPreset === '15min' || frequencyPreset === '1hour' || frequencyPreset === 'daily') {
      return
    }
    setFrequencyPreset('5min')
  }, [triggerType, frequencyPreset])

  useEffect(() => {
    if (!proposedSpec?.required_user_inputs?.suggested_defaults) return
    setVariableValues((prev) => ({
      ...proposedSpec.required_user_inputs?.suggested_defaults,
      ...prev,
    }))
  }, [proposedSpec])

  useEffect(() => {
    const loadGroups = async () => {
      try {
        const walletGroupsResponse = await groupsApiService.getGroupsByType(GroupType.WALLET)
        const groups = walletGroupsResponse.results || []
        const accountsGroup =
          groups.find((group) => (group.settings as { system_key?: string })?.system_key === 'accounts') || null
        const orderedGroups = accountsGroup
          ? [accountsGroup, ...groups.filter((group) => group.id !== accountsGroup.id)]
          : groups
        setWalletGroups(orderedGroups)
        if (accountsGroup && !targetGroupId) {
          setTargetGroupId(accountsGroup.id)
        }
      } catch (loadError) {
        console.error('Failed to load wallet groups:', loadError)
      }
    }

    loadGroups()
  }, [targetGroupId])

  const handleLocalUnderstanding = useCallback((input: string) => {
    const trimmed = normalizeNlpInput(input)
    if (trimmed.length < NLP_MIN_LENGTH) {
      setUnderstanding({})
      setConfidence(0)
      setVisualQuery(initialVisualQuery)
      return
    }

    const localEventType = detectEventType(trimmed)
    const nextUnderstanding: UnderstandingState = {
      eventType: localEventType,
      conditions: extractConditions(trimmed),
      chains: extractChains(trimmed),
      wallets: extractWallets(trimmed),
      thresholds: extractThresholds(trimmed),
    }

    const nextConfidence = calculateConfidence(nextUnderstanding)
    const nextVisualQuery = generateVisualQuery(trimmed, nextUnderstanding)

    setUnderstanding(nextUnderstanding)
    setConfidence(nextConfidence)
    setVisualQuery(nextVisualQuery)

    setShowUnderstanding(true)
    setShowPreview(nextConfidence > 60)
  }, [])

  useEffect(() => {
    if (isUsingMarketplaceTemplate) return
    handleLocalUnderstanding(deferredNaturalLanguage)
  }, [deferredNaturalLanguage, handleLocalUnderstanding, isUsingMarketplaceTemplate])

  const templateVariables: TemplateVariable[] = useMemo(() => {
    if (!proposedSpec?.template) return []
    return extractTemplateVariables(proposedSpec.template as TemplateLike)
  }, [proposedSpec])

  const notificationTokens = useMemo(() => {
    const tokens = new Set<string>(['{{target.short}}', '{{target.key}}', '{{alert_name}}'])
    templateVariables.forEach((variable) => {
      const id = getVariableId(variable)
      if (id) tokens.add(`{{${id}}}`)
    })
    return Array.from(tokens)
  }, [templateVariables])

  const requiredVariableIds = useMemo(() => {
    const ids = new Set<string>()
    const required = proposedSpec?.required_user_inputs?.required_variables || []
    required.forEach((id) => ids.add(id.toLowerCase()))
    templateVariables.forEach((variable) => {
      const id = getVariableId(variable)
      if (!id) return
      if (variable.required) ids.add(id.toLowerCase())
    })
    return ids
  }, [proposedSpec, templateVariables])

  const variablesToRender = useMemo(() => {
    if (requiredVariableIds.size === 0) return templateVariables
    return templateVariables.filter((variable) => {
      const id = getVariableId(variable)
      if (!id) return false
      return requiredVariableIds.has(id.toLowerCase())
    })
  }, [templateVariables, requiredVariableIds])

  const missingVariables = useMemo(() => {
    if (variablesToRender.length === 0) return []
    return variablesToRender.filter((variable) => {
      const id = getVariableId(variable)
      if (!id) return false
      return requiredVariableIds.has(id.toLowerCase()) && !isValueProvided(variableValues[id])
    })
  }, [variablesToRender, requiredVariableIds, variableValues])

  const targetsRequired = proposedSpec?.required_user_inputs?.targets_required !== false
  const missingInfo = useMemo(() => {
    const items = proposedSpec?.missing_info
    return Array.isArray(items) ? items : []
  }, [proposedSpec])
  const hasBlockingMissingInfo = missingInfo.length > 0
  const networkMissingInfo = useMemo(() => {
    for (const item of missingInfo) {
      if (!item || typeof item !== 'object') continue
      const code = (item as any).code
      const field = (item as any).field
      const options = (item as any).options
      if (code !== 'network_required' && field !== 'scope.networks') continue
      if (!Array.isArray(options) || options.length === 0) continue
      return { code, field, options }
    }
    return null
  }, [missingInfo])
  const preferredNetwork = typeof nlpContextOverrides.preferred_network === 'string'
    ? (nlpContextOverrides.preferred_network as string)
    : null

  const templateScopeNetworks = useMemo(() => {
    const networks = (proposedSpec as any)?.template?.scope?.networks
    if (!Array.isArray(networks)) return []
    return networks.map((n: unknown) => String(n)).filter((n: string) => n.trim().length > 0)
  }, [proposedSpec])

  const defaultNetworkKey = useMemo(() => (
    preferredNetwork || templateScopeNetworks[0] || 'ETH:mainnet'
  ), [preferredNetwork, templateScopeNetworks])
  const proposedSpecConfidencePct = useMemo(() => {
    const c = proposedSpec?.confidence
    if (typeof c !== 'number' || !Number.isFinite(c)) return null
    return Math.max(0, Math.min(100, Math.round(c * 100)))
  }, [proposedSpec])
  const canTestAlert = !hasBlockingMissingInfo && (proposedSpecConfidencePct === null || proposedSpecConfidencePct >= 60)
  const compileErrors = useMemo(() => {
    const errors = (proposedSpec as any)?.compile_report?.errors
    if (!Array.isArray(errors)) return []
    return errors.map((e) => String(e)).filter((e) => e.trim().length > 0)
  }, [proposedSpec])
  const specWarnings = useMemo(() => {
    const warnings = proposedSpec?.warnings
    if (!Array.isArray(warnings)) return []
    return warnings.map((w) => String(w)).filter((w) => w.trim().length > 0)
  }, [proposedSpec])

  const targetKeys = useMemo(() => {
    if (!targetKeysInput.trim()) return []
    return targetKeysInput
      .split(/[\n,\s]+/)
      .map((value) => value.trim())
      .filter(Boolean)
      .map((value) => (value.includes(':') ? value : `${defaultNetworkKey}:${value}`))
  }, [targetKeysInput, defaultNetworkKey])

  const hasValidTargets = useMemo(() => {
    if (!targetsRequired) return true
    if (targetMode === 'group') return Boolean(targetGroupId)
    return targetKeys.length > 0
  }, [targetsRequired, targetMode, targetGroupId, targetKeys])

  const selectedChainKey = useMemo(() => (
    normalizeChainKey(understanding.chains?.[0] || 'ethereum') || 'ethereum'
  ), [understanding.chains])

  const selectedChainLabel = useMemo(() => (
    getChainIdentity(selectedChainKey)?.name || selectedChainKey
  ), [selectedChainKey])

  const getCronForPreset = (preset: string) => {
    switch (preset) {
      case '5min':
        return '*/5 * * * *'
      case '15min':
        return '*/15 * * * *'
      case '1hour':
        return '0 * * * *'
      case 'daily':
        return '0 0 * * *'
      default:
        return ''
    }
  }

  const buildTriggerConfig = () => {
    if (triggerType === 'event_driven') {
      const networks = templateScopeNetworks.length ? templateScopeNetworks : [defaultNetworkKey]
      return { networks }
    }
    if (triggerType === 'periodic') {
      return {
        cron: getCronForPreset(frequencyPreset),
        timezone: 'UTC',
        data_lag_secs: 120,
      }
    }
    return {
      run_at: oneTimeRunAt,
      data_lag_secs: 120,
    }
  }

  useEffect(() => {
    if (triggerTypeTouched) return
    const mode = String((proposedSpec as any)?.template?.trigger?.evaluation_mode || '').toLowerCase()
    if (mode === 'event_driven') setTriggerType('event_driven')
    else if (mode === 'periodic') setTriggerType('periodic')
    else if (mode === 'one_time') setTriggerType('one_time')
    else if (mode === 'hybrid' && triggerType !== 'event_driven') setTriggerType('event_driven')
  }, [proposedSpec, triggerTypeTouched, triggerType])

  useEffect(() => {
    if (frequencyPresetTouched) return
    const cadence = Number((proposedSpec as any)?.template?.trigger?.cron_cadence_seconds)
    if (!Number.isFinite(cadence) || cadence <= 0) return
    if (cadence === 300) setFrequencyPreset('5min')
    else if (cadence === 900) setFrequencyPreset('15min')
    else if (cadence === 3600) setFrequencyPreset('1hour')
    else if (cadence === 86400) setFrequencyPreset('daily')
  }, [proposedSpec, frequencyPresetTouched])

  useEffect(() => {
    // If the user has picked targets, infer a preferred network so the NLP compiler doesn't
    // need the end-user to mention chains or internal IDs.
    if (preferredNetworkTouched) return
    if (targetMode !== 'group' || !targetGroupId) return
    const group = walletGroups.find((g) => g.id === targetGroupId)
    if (!group) return

    const networks = new Set<string>()
    for (const key of group.member_keys || []) {
      const parts = String(key).split(':')
      if (parts.length < 2) continue
      networks.add(`${parts[0].toUpperCase()}:${parts[1].toLowerCase()}`)
    }
    if (networks.size !== 1) return
    const only = Array.from(networks)[0]
    if (preferredNetwork === only) return

    setNlpContextOverrides((prev) => ({ ...prev, preferred_network: only }))
  }, [preferredNetworkTouched, targetMode, targetGroupId, walletGroups, preferredNetwork])

  const resolveErrorMessage = (error: unknown, fallback: string) => {
    if (!error) return fallback
    if (typeof error === 'string') return error
    if (error instanceof Error && error.message) return error.message

    const responseData = (error as { response?: { data?: unknown } })?.response?.data

    if (typeof responseData === 'string') return responseData
    if (responseData && typeof responseData === 'object') {
      const data = responseData as { error?: string; detail?: string; message?: string; errors?: string[] }
      if (data.error) return data.error
      if (data.detail) return data.detail
      if (data.message) return data.message
      if (Array.isArray(data.errors)) return data.errors.join(' ')
    }

    return fallback
  }

  const handleSaveTemplate = async () => {
    if (isUsingMarketplaceTemplate) return

    if (!jobId) {
      setTemplateError('Please wait for analysis to complete before saving.')
      notifications.show({
        title: 'No Parse Job',
        message: 'Please wait for analysis to complete before saving.',
        color: 'orange',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    if (hasBlockingMissingInfo) {
      notifications.show({
        title: 'More Info Needed',
        message: 'Answer the missing details before saving this template.',
        color: 'orange',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    setTemplateError(null)
    setIsSavingTemplate(true)

    const response = await alertsApiService.saveTemplateFromJob({
      job_id: jobId,
      publish_to_org: publishToOrg,
      publish_to_marketplace: publishToMarketplace,
    })

    if (response.success) {
      setSavedTemplate(response)
      setExistingTemplate(null)
      setTemplateError(null)
      notifications.show({
        title: 'Template Saved',
        message: 'Your alert template is ready to use.',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
    } else if (response.code === 'marketplace_template_exists' && response.existing_template) {
      setExistingTemplate(response.existing_template)
      notifications.show({
        title: 'Template Already Exists',
        message: 'Use the existing marketplace template instead of creating a duplicate.',
        color: 'blue',
      })
    } else {
      setTemplateError(response.message || 'Please try again.')
      notifications.show({
        title: 'Failed to Save Template',
        message: response.message || 'Please try again.',
        color: 'red',
        icon: <IconX size={16} />,
      })
    }

    setIsSavingTemplate(false)
  }

  const handleUseExistingTemplate = () => {
    if (!existingTemplate) return
    setSavedTemplate({
      success: true,
      template_id: existingTemplate.template_id,
      template_version: existingTemplate.template_version,
      fingerprint: existingTemplate.fingerprint,
    })
    setExistingTemplate(null)
    setTemplateError(null)
    notifications.show({
      title: 'Template Selected',
      message: 'Using the existing marketplace template.',
      color: 'green',
    })
  }

  const ensureSavedTemplateForCreate = async (): Promise<AlertTemplateSaveResponse | null> => {
    if (savedTemplate?.template_id && savedTemplate.template_version) return savedTemplate
    if (isUsingMarketplaceTemplate) return savedTemplate

    if (!jobId || nlpStatus !== 'completed') {
      setCreateError('Please wait for analysis to complete before creating an alert.')
      notifications.show({
        title: 'Analysis In Progress',
        message: 'Please wait for analysis to complete before creating an alert.',
        color: 'orange',
        icon: <IconAlertCircle size={16} />,
      })
      return null
    }

    setTemplateError(null)
    setIsSavingTemplate(true)

    const response = await alertsApiService.saveTemplateFromJob({
      job_id: jobId,
      publish_to_org: publishToOrg,
      publish_to_marketplace: publishToMarketplace,
    })

    setIsSavingTemplate(false)

    if (response.success) {
      setSavedTemplate(response)
      setExistingTemplate(null)
      setTemplateError(null)
      return response
    }

    if (response.code === 'marketplace_template_exists' && response.existing_template) {
      const adopted: AlertTemplateSaveResponse = {
        success: true,
        template_id: response.existing_template.template_id,
        template_version: response.existing_template.template_version,
        fingerprint: response.existing_template.fingerprint,
      }
      setSavedTemplate(adopted)
      setExistingTemplate(null)
      setTemplateError(null)
      return adopted
    }

    const message = response.message || 'Failed to save the template needed to create this alert.'
    setTemplateError(message)
    setCreateError(message)
    notifications.show({
      title: 'Failed to Save Template',
      message,
      color: 'red',
      icon: <IconX size={16} />,
    })
    return null
  }

  const handleCreateAlert = async () => {
    if (hasBlockingMissingInfo) {
      setCreateError('Answer the missing details before creating this alert.')
      notifications.show({
        title: 'More Info Needed',
        message: 'Answer the missing details before creating this alert.',
        color: 'orange',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    if (targetsRequired) {
      if (targetMode === 'group' && !targetGroupId) {
        setCreateError('Choose a wallet group to monitor.')
        notifications.show({
          title: 'Select Target Group',
          message: 'Choose a wallet group to monitor.',
          color: 'orange',
          icon: <IconAlertCircle size={16} />,
        })
        return
      }
      if (targetMode === 'keys' && targetKeys.length === 0) {
        setCreateError('Provide at least one wallet address.')
        notifications.show({
          title: 'Add Wallet Keys',
          message: 'Provide at least one wallet address.',
          color: 'orange',
          icon: <IconAlertCircle size={16} />,
        })
        return
      }
    }

    if (missingVariables.length > 0) {
      setCreateError('Please fill in required alert parameters.')
      notifications.show({
        title: 'Missing Variables',
        message: 'Please fill in required alert parameters.',
        color: 'orange',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    if (triggerType === 'periodic' && !getCronForPreset(frequencyPreset)) {
      setCreateError('Choose a schedule frequency before creating this alert.')
      notifications.show({
        title: 'Select Schedule',
        message: 'Choose a schedule frequency before creating this alert.',
        color: 'orange',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    setCreateError(null)
    setIsCreatingAlert(true)

    const templateHandle = await ensureSavedTemplateForCreate()
    if (!templateHandle?.template_id || !templateHandle.template_version) {
      setIsCreatingAlert(false)
      return
    }

    const alertName = proposedSpec?.human_preview?.summary
      ? proposedSpec.human_preview.summary
      : naturalLanguage.substring(0, 80)

    const targetSelector =
      targetMode === 'group'
        ? { mode: 'group', group_id: targetGroupId || undefined }
        : { mode: 'keys', keys: targetKeys }

    const trimmedTitle = notificationTitle.trim()
    const trimmedBody = notificationBody.trim()
    const notificationOverrides =
      notificationTouched && (trimmedTitle || trimmedBody)
        ? {
            title_template: trimmedTitle || undefined,
            body_template: trimmedBody || undefined,
          }
        : undefined

    try {
      await createAlert({
        template_id: templateHandle.template_id,
        template_version: templateHandle.template_version,
        name: alertName,
        enabled: true,
        trigger_type: triggerType,
        trigger_config: buildTriggerConfig(),
        target_selector: targetSelector,
        variable_values: variableValues,
        notification_overrides: notificationOverrides,
      })

      notifications.show({
        title: 'Alert Created Successfully',
        message: 'Your alert instance is now active.',
        color: 'green',
        icon: <IconCheck size={16} />,
      })

      setCreateError(null)
      onAlertCreated({
        name: alertName,
        description: naturalLanguage,
        event_type: understanding.eventType,
      })
    } catch (createError) {
      const errorMessage = resolveErrorMessage(createError, 'Please try again or contact support.')
      setCreateError(errorMessage)
      console.error('Failed to create alert instance:', createError)
      notifications.show({
        title: 'Failed to Create Alert',
        message: errorMessage,
        color: 'red',
        icon: <IconX size={16} />,
      })
    } finally {
      setIsCreatingAlert(false)
    }
  }

  const handleTestAlert = async () => {
    if (!proposedSpec) {
      return
    }

    if (proposedSpecConfidencePct !== null && proposedSpecConfidencePct < 60) {
      notifications.show({
        title: 'Low Confidence',
        message: 'Try adding more detail before testing this alert.',
        color: 'orange',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    if (hasBlockingMissingInfo) {
      notifications.show({
        title: 'More Info Needed',
        message: 'Answer the missing details before testing this alert.',
        color: 'orange',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    // Legacy fallback: template-only specs (no compiled_executable) use inline preview.
    if (proposedSpec.template && !proposedSpec.compiled_executable) {
      const chain = normalizeChainKey(understanding.chains?.[0] || 'ethereum') || 'ethereum'
      const previewConfig = {
        time_range: previewTimeRange,
        limit: 1000,
        include_near_misses: true,
        explain_mode: true,
        addresses: understanding.wallets || [],
        chain,
      }

      setPreviewModalOpened(true)
      await runInlinePreview(proposedSpec.template as Record<string, unknown>, previewConfig, 'wallet')
      return
    }

    if (!proposedSpec.compiled_executable || !jobId) {
      notifications.show({
        title: 'Preview Not Available',
        message: 'Re-run analysis before testing this alert.',
        color: 'orange',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    if (targetsRequired) {
      if (targetMode === 'group' && !targetGroupId) {
        notifications.show({
          title: 'Select Target Group',
          message: 'Choose a wallet group to test.',
          color: 'orange',
          icon: <IconAlertCircle size={16} />,
        })
        return
      }
      if (targetMode === 'keys' && targetKeys.length === 0) {
        notifications.show({
          title: 'Add Wallet Keys',
          message: 'Provide at least one wallet to test.',
          color: 'orange',
          icon: <IconAlertCircle size={16} />,
        })
        return
      }
    }

    if (missingVariables.length > 0) {
      notifications.show({
        title: 'Missing Variables',
        message: 'Fill in required alert parameters before testing.',
        color: 'orange',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    const targetSelector =
      targetMode === 'group'
        ? { mode: 'group', group_id: targetGroupId || undefined }
        : { mode: 'keys', keys: targetKeys }

    setPreviewModalOpened(true)
    await runTemplatePreviewFromJob({
      job_id: jobId,
      target_selector: targetSelector,
      variable_values: variableValues,
      sample_size: 50,
    })
  }

  const handleClosePreviewModal = () => {
    setPreviewModalOpened(false)
    clearPreview()
  }

  const handleAdjustThreshold = () => {
    setPreviewModalOpened(false)
    notifications.show({
      title: 'Adjust Your Alert',
      message: 'Modify the threshold in your description to change trigger sensitivity',
      color: 'blue',
    })
  }

  return (
    <Stack gap="xl" style={{ maxWidth: 840, margin: '0 auto', width: '100%' }}>
      <Group justify="space-between" wrap="wrap" align="center">
        <Title order={2}>Create Alert</Title>
        <Group gap="xs" wrap="wrap" align="center">
          <ConfidenceIndicator confidence={confidence} />
          {understanding.eventType && (
            <AlertEventBadge eventType={understanding.eventType} subEvent={understanding.subEvent} chain={understanding.chains?.[0]} />
          )}
          <ActionIcon variant="subtle" onClick={onCancel}>
            <IconX size={20} />
          </ActionIcon>
        </Group>
      </Group>

      <NaturalLanguageInputEnhanced
        value={naturalLanguage}
        onChange={(value) => {
          setNaturalLanguage(value)
        }}
        isProcessing={!isUsingMarketplaceTemplate && (nlpStatus === 'connecting' || nlpStatus === 'processing')}
      />

      <AnimatePresence>
        {nlpStatus !== 'idle' && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: reduceMotion ? 0.1 : 0.2 }}
          >
            <ProgressIndicator status={nlpStatus} message={progress?.message} percent={progress?.percent} />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showUnderstanding && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: reduceMotion ? 0.15 : 0.3 }}
          >
            <RealtimeUnderstandingPanel
              understanding={understanding}
              confidence={confidence}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showPreview && confidence > 60 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: reduceMotion ? 0.15 : 0.3, delay: reduceMotion ? 0 : 0.2 }}
          >
            <VisualQueryPreview visualQuery={visualQuery} />
          </motion.div>
        )}
      </AnimatePresence>

      {!isUsingMarketplaceTemplate && (
        <Card p="md" radius="md" withBorder>
          <Stack gap="md">
            <Group justify="space-between" wrap="wrap" align="center">
              <Group gap="xs">
                <IconTemplate size={18} />
                <Text size="sm" fw={600}>Save Template</Text>
                {savedTemplate?.template_id && (
                  <Badge size="xs" color="green" variant="light">Saved</Badge>
                )}
              </Group>
              <Group gap="xs" wrap="wrap">
                <Switch
                  size="sm"
                  label="Share with org"
                  checked={publishToOrg}
                  onChange={(e) => setPublishToOrg(e.currentTarget.checked)}
                />
                <Switch
                  size="sm"
                  label="Publish to marketplace"
                  checked={publishToMarketplace}
                  onChange={(e) => setPublishToMarketplace(e.currentTarget.checked)}
                />
              </Group>
            </Group>

            <Group justify="space-between">
              <Text size="sm" c="dimmed">
                Save a reusable template (optional). Creating the alert will auto-save if needed.
              </Text>
              <Button
                variant="light"
                leftSection={<IconCheck size={16} />}
                loading={isSavingTemplate}
                disabled={!proposedSpec || nlpStatus !== 'completed' || hasBlockingMissingInfo}
                onClick={handleSaveTemplate}
              >
                Save Template
              </Button>
            </Group>

            {hasBlockingMissingInfo && (
              <Alert icon={<IconAlertCircle />} color="orange">
                <Stack gap={6}>
                  <Text size="sm" fw={600}>
                    More info needed
                  </Text>
                  {networkMissingInfo && (
                    <Select
                      label="Network"
                      placeholder="Choose a network"
                      data={(networkMissingInfo.options as Array<{ id: string; label?: string }>).map((opt) => ({
                        value: opt.id,
                        label: opt.label || opt.id,
                      }))}
                      value={preferredNetwork}
                      onChange={(next) => {
                        if (!next) return
                        const selected = (networkMissingInfo.options as Array<{ id: string; context_patch?: unknown }>).find(
                          (opt) => opt.id === next
                        )
                      const patch = selected?.context_patch
                      if (patch && typeof patch === 'object') {
                          rerunTemplateCompiler(patch as Record<string, unknown>)
                          return
                        }
                        rerunTemplateCompiler({ preferred_network: next })
                      }}
                    />
                  )}
                  <Stack gap={4}>
                    {missingInfo.map((item, idx) => (
                      <Text key={idx} size="sm">
                        {String((item as any)?.message || (item as any)?.code || 'Missing detail')}
                      </Text>
                    ))}
                  </Stack>
                </Stack>
              </Alert>
            )}

            {Array.isArray(proposedSpec?.assumptions) && proposedSpec.assumptions.length > 0 && (
              <Alert icon={<IconInfoCircle />} color="blue" variant="light">
                <Stack gap={6}>
                  <Text size="sm" fw={600}>
                    Assumptions
                  </Text>
                  <Stack gap={4}>
                    {proposedSpec.assumptions.map((assumption, idx) => (
                      <Text key={idx} size="sm">
                        {assumption}
                      </Text>
                    ))}
                  </Stack>
                </Stack>
              </Alert>
            )}

            {compileErrors.length > 0 && (
              <Alert icon={<IconAlertCircle />} color="red" variant="light">
                <Stack gap={6}>
                  <Text size="sm" fw={600}>
                    Compile Errors
                  </Text>
                  <Stack gap={4}>
                    {compileErrors.map((err, idx) => (
                      <Text key={idx} size="sm">
                        {err}
                      </Text>
                    ))}
                  </Stack>
                </Stack>
              </Alert>
            )}

            {specWarnings.length > 0 && (
              <Alert icon={<IconInfoCircle />} color="yellow" variant="light">
                <Stack gap={6}>
                  <Text size="sm" fw={600}>
                    Warnings
                  </Text>
                  <Stack gap={4}>
                    {specWarnings.map((warn, idx) => (
                      <Text key={idx} size="sm">
                        {warn}
                      </Text>
                    ))}
                  </Stack>
                </Stack>
              </Alert>
            )}

            {templateError && (
              <Alert icon={<IconAlertCircle />} color="red">
                {templateError}
              </Alert>
            )}

            {existingTemplate && (
              <Group justify="space-between" p="xs" style={{ background: '#EFF6FF', borderRadius: 8 }}>
                <Text size="sm" c="#1D4ED8">
                  A marketplace template already matches your alert.
                </Text>
                <Button size="xs" onClick={handleUseExistingTemplate}>
                  Use Existing Template
                </Button>
              </Group>
            )}
          </Stack>
        </Card>
      )}

      <Card p="md" radius="md" withBorder>
        <Stack gap="md">
          <Group justify="space-between">
            <Group gap="xs">
              <IconSettings size={18} />
              <Text size="sm" fw={600}>Alert Instance Settings</Text>
              <Badge
                size="sm"
                variant="light"
                color="blue"
                leftSection={<ChainLogo chain={selectedChainKey} size="sm" />}
              >
                {selectedChainLabel}
              </Badge>
            </Group>
            <ActionIcon variant="subtle" onClick={toggleAdvanced} aria-label="Toggle alert instance settings">
              {advancedOpened ? <IconChevronUp size={18} /> : <IconChevronDown size={18} />}
            </ActionIcon>
          </Group>

          <Collapse in={advancedOpened}>
            <Stack gap="md" mt="md">
              <Divider />
              {!isUsingMarketplaceTemplate && (
                <div>
                  <Text size="sm" fw={600} mb="xs">NLP Context</Text>
                  <Select
                    placeholder="Auto (from your text)"
                    label="Preferred network"
                    data={[
                      { value: 'ETH:mainnet', label: 'Ethereum Mainnet' },
                      { value: 'AVAX:mainnet', label: 'Avalanche C-Chain' },
                    ]}
                    value={preferredNetwork}
                    onChange={(next) => {
                      setPreferredNetworkTouched(Boolean(next))
                      rerunTemplateCompiler({ preferred_network: next || null })
                    }}
                    clearable
                    description="Helps the compiler choose the right chain without you pasting addresses."
                  />
                </div>
              )}
              <div>
                <Text size="sm" fw={600} mb="xs">Target Selection</Text>
                <SegmentedControl
                  data={[
                    { value: 'group', label: 'Wallet Group' },
                    { value: 'keys', label: 'Specific Wallets' },
                  ]}
                  value={targetMode}
                  onChange={(value) => setTargetMode(value as 'group' | 'keys')}
                />

                {targetMode === 'group' ? (
                  <Select
                    mt="sm"
                    placeholder="Choose a wallet group"
                    data={walletGroups.map((group) => ({ value: group.id, label: group.name }))}
                    value={targetGroupId}
                    onChange={setTargetGroupId}
                  />
                ) : (
                  <Textarea
                    mt="sm"
                    placeholder="Paste wallet addresses (one per line)"
                    value={targetKeysInput}
                    onChange={(e) => setTargetKeysInput(e.currentTarget.value)}
                    minRows={3}
                  />
                )}
              </div>

              <div>
                <Text size="sm" fw={600} mb="xs">Trigger Type</Text>
                <SegmentedControl
                  data={[
                    { value: 'event_driven', label: 'Real-time' },
                    { value: 'periodic', label: 'Scheduled' },
                    { value: 'one_time', label: 'One-time' },
                  ]}
                  value={triggerType}
                  onChange={(value) => {
                    setTriggerTypeTouched(true)
                    setTriggerType(value as 'event_driven' | 'periodic' | 'one_time')
                  }}
                />

                {triggerType === 'periodic' && (
                  <Select
                    mt="sm"
                    data={[
                      { value: '5min', label: 'Every 5 minutes' },
                      { value: '15min', label: 'Every 15 minutes' },
                      { value: '1hour', label: 'Hourly' },
                      { value: 'daily', label: 'Daily summary' },
                    ]}
                    value={frequencyPreset}
                    onChange={(value) => {
                      setFrequencyPresetTouched(true)
                      setFrequencyPreset((value || '5min') as typeof frequencyPreset)
                    }}
                  />
                )}

                {triggerType === 'one_time' && (
                  <TextInput
                    mt="sm"
                    placeholder="2026-01-15T12:34:56Z"
                    value={oneTimeRunAt}
                    onChange={(e) => setOneTimeRunAt(e.currentTarget.value)}
                  />
                )}
              </div>

              {variablesToRender.length > 0 && (
                <div>
                  <Text size="sm" fw={600} mb="xs">Required Variables</Text>
                  <Stack gap="sm">
                    {variablesToRender.map((variable) => {
                      const id = getVariableId(variable)
                      if (!id) return null
                      const value = variableValues[id]
                      const label = variable.label || id
                      const description = variable.description
                      const type = variable.type || 'string'
                      const isRequired = requiredVariableIds.has(id.toLowerCase())

                      if (type === 'integer' || type === 'decimal') {
                        return (
                          <NumberInput
                            key={id}
                            label={label}
                            description={description}
                            value={typeof value === 'number' ? value : undefined}
                            onChange={(next) => setVariableValues((prev) => ({ ...prev, [id]: next }))}
                            required={isRequired}
                          />
                        )
                      }

                      if (type === 'boolean') {
                        return (
                          <Checkbox
                            key={id}
                            label={label}
                            description={description}
                            checked={Boolean(value)}
                            onChange={(e) => setVariableValues((prev) => ({ ...prev, [id]: e.currentTarget.checked }))}
                          />
                        )
                      }

                      if (type === 'enum' && variable.validation?.options) {
                        const options = (variable.validation.options as Array<{ value: string; label?: string }>).map((opt) => ({
                          value: opt.value,
                          label: opt.label || opt.value,
                        }))
                        return (
                          <Select
                            key={id}
                            label={label}
                            description={description}
                            data={options}
                            value={typeof value === 'string' ? value : undefined}
                            onChange={(next) => setVariableValues((prev) => ({ ...prev, [id]: next }))}
                            required={isRequired}
                          />
                        )
                      }

                      return (
                        <TextInput
                          key={id}
                          label={label}
                          description={description}
                          value={typeof value === 'string' ? value : ''}
                          onChange={(e) => setVariableValues((prev) => ({ ...prev, [id]: e.currentTarget.value }))}
                          required={isRequired}
                        />
                      )
                    })}
                  </Stack>
                </div>
              )}

              <div>
                <Text size="sm" fw={600} mb="xs">Notification Message</Text>
                <Stack gap="sm">
                  <TextInput
                    label="Notification title"
                    placeholder="Alert triggered for your wallet"
                    value={notificationTitle}
                    onChange={(e) => {
                      setNotificationTouched(true)
                      setNotificationTitle(e.currentTarget.value)
                    }}
                  />
                  <Textarea
                    label="Notification body"
                    placeholder="Your wallet {{target.short}} has met this alert condition."
                    minRows={3}
                    value={notificationBody}
                    onChange={(e) => {
                      setNotificationTouched(true)
                      setNotificationBody(e.currentTarget.value)
                    }}
                  />
                  {notificationTokens.length > 0 && (
                    <Text size="xs" c="dimmed">
                      Available tokens: {notificationTokens.join(' ')}
                    </Text>
                  )}
                </Stack>
              </div>

              {proposedSpec?.pipeline_metadata && (
                <div>
                  <Text size="sm" fw={600} mb="xs">Compiler Diagnostics</Text>
                  <Stack gap={4}>
                    <Text size="xs" c="dimmed">
                      Model: {String((proposedSpec.pipeline_metadata as any)?.model || 'unknown')}
                    </Text>
                    <Text size="xs" c="dimmed">
                      Latency: {String((proposedSpec.pipeline_metadata as any)?.latency_ms ?? 'n/a')} ms
                    </Text>
                    {((proposedSpec.pipeline_metadata as any)?.stage_timings_ms &&
                      typeof (proposedSpec.pipeline_metadata as any).stage_timings_ms === 'object') && (
                      <Text size="xs" c="dimmed">
                        Stage timings: {JSON.stringify((proposedSpec.pipeline_metadata as any).stage_timings_ms)}
                      </Text>
                    )}
                  </Stack>
                </div>
              )}
            </Stack>
          </Collapse>
        </Stack>
      </Card>

      <Group justify="space-between">
        <Button variant="subtle" onClick={onCancel}>
          Cancel
        </Button>
        <Group gap="sm">
          {proposedSpec && !isUsingMarketplaceTemplate && (
            <Tooltip label="Test this alert on a small sample before creating">
              <Button
                variant="light"
                leftSection={<IconTestPipe size={18} />}
                loading={isPreviewLoading}
                disabled={!canTestAlert}
                onClick={handleTestAlert}
                size="md"
              >
                Test Alert
              </Button>
            </Tooltip>
          )}
          <Button
            leftSection={<IconWand size={18} />}
            loading={isCreatingAlert}
            disabled={!proposedSpec || nlpStatus !== 'completed' || hasBlockingMissingInfo || missingVariables.length > 0 || !hasValidTargets}
            onClick={handleCreateAlert}
            size="md"
          >
            Create Alert
          </Button>
        </Group>
      </Group>

      {createError && (
        <Alert icon={<IconAlertCircle />} color="red">
          {createError}
        </Alert>
      )}

      <PreviewResultsModal
        opened={previewModalOpened}
        onClose={handleClosePreviewModal}
        result={previewResult}
        isLoading={isPreviewLoading}
        onAdjustThreshold={handleAdjustThreshold}
        onCreate={handleCreateAlert}
        timeRange={previewTimeRange}
      />

      {parseErrors.length > 0 && (
        <Alert icon={<IconAlertCircle />} color="red">
          {parseErrors.join('. ')}
        </Alert>
      )}
    </Stack>
  )
}

// Local event type detection for UI feedback
const detectEventType = (input: string): string => {
  const desc = input.toLowerCase()

  if (desc.includes('transfer') || desc.includes('send')) {
    return 'transfer'
  } else if (desc.includes('swap') || desc.includes('trade')) {
    return 'swap'
  } else if (desc.includes('gas') || desc.includes('fee')) {
    return 'gas_price'
  } else if (desc.includes('liquidity') || desc.includes('pool')) {
    return 'liquidity'
  } else if (desc.includes('nft') || desc.includes('opensea')) {
    return 'nft'
  } else if (desc.includes('balance') || desc.includes('above') || desc.includes('below')) {
    return 'balance_change'
  }
  return 'custom'
}

const extractConditions = (input: string): ParsedCondition[] => {
  const conditions: ParsedCondition[] = []
  const lower = input.toLowerCase()

  if (lower.includes('above') || lower.includes('over') || lower.includes('>')) {
    conditions.push({
      type: 'threshold',
      field: 'value',
      operator: '>',
      value: extractFirstNumber(input) || 0,
      unit: extractUnit(input),
    })
  } else if (lower.includes('below') || lower.includes('under') || lower.includes('<')) {
    conditions.push({
      type: 'threshold',
      field: 'value',
      operator: '<',
      value: extractFirstNumber(input) || 0,
      unit: extractUnit(input),
    })
  }

  return conditions
}

const extractChains = (input: string): string[] => {
  const chains: string[] = []
  const lowerInput = input.toLowerCase()

  if (lowerInput.includes('eth') || lowerInput.includes('ethereum')) chains.push('ethereum')
  if (lowerInput.includes('btc') || lowerInput.includes('bitcoin')) chains.push('bitcoin')
  if (lowerInput.includes('sol') || lowerInput.includes('solana')) chains.push('solana')
  if (lowerInput.includes('avax') || lowerInput.includes('avalanche')) chains.push('avalanche')
  if (lowerInput.includes('matic') || lowerInput.includes('polygon')) chains.push('polygon')
  if (lowerInput.includes('arb') || lowerInput.includes('arbitrum')) chains.push('arbitrum')
  if (lowerInput.includes('optimism') || lowerInput.includes('op ')) chains.push('optimism')
  if (lowerInput.includes('base')) chains.push('base')
  if (lowerInput.includes('bsc') || lowerInput.includes('bnb')) chains.push('bsc')

  return chains.length > 0 ? chains : ['ethereum']
}

const extractWallets = (input: string): string[] => {
  const walletPattern = /0x[a-fA-F0-9]{40}/g
  const matches = input.match(walletPattern)
  return matches || []
}

const extractThresholds = (input: string): ThresholdValue[] => {
  const thresholds: ThresholdValue[] = []
  const numberPattern = /(\d+(?:\.\d+)?)\s*(\w+)?/g
  const matches = [...input.matchAll(numberPattern)]

  matches.forEach((match) => {
    const value = parseFloat(match[1])
    const unit = match[2] || ''

    if (unit.toLowerCase().includes('eth') || unit.toLowerCase().includes('btc')) {
      thresholds.push({ name: 'amount', value, unit })
    } else if (unit.toLowerCase().includes('gwei')) {
      thresholds.push({ name: 'gas', value, unit: 'gwei' })
    } else if (unit === 'k' || unit === 'K') {
      thresholds.push({ name: 'amount', value: value * 1000, unit: 'USD' })
    }
  })

  return thresholds
}

const extractFirstNumber = (input: string): number | null => {
  const match = input.match(/\d+(?:\.\d+)?/)
  return match ? parseFloat(match[0]) : null
}

const extractUnit = (input: string): string => {
  const units = ['ETH', 'BTC', 'SOL', 'AVAX', 'MATIC', 'USD', 'gwei']
  const lowerInput = input.toLowerCase()

  for (const unit of units) {
    if (lowerInput.includes(unit.toLowerCase())) {
      return unit
    }
  }
  return 'USD'
}

const generateVisualQuery = (input: string, understandingState: UnderstandingState): VisualQuery => {
  const { eventType, conditions, chains } = understandingState

  let when = 'Unknown event'
  let where = 'Any wallet'
  let condition = 'No conditions set'
  const action = 'Send notification'

  if (eventType === 'balance_change') {
    when = 'Balance changes'
  } else if (eventType === 'transaction') {
    when = 'Transaction occurs'
  } else if (eventType === 'gas_price') {
    when = 'Gas price changes'
  }

  if (chains?.length) {
    where = `On ${chains.join(', ')}`
  }

  if (conditions?.length) {
    const cond = conditions[0]
    condition = `Amount ${cond.operator} ${cond.value} ${cond.unit || ''}`
  }

  return { when, where, condition, action }
}

const calculateConfidence = (understandingState: UnderstandingState): number => {
  let score = 0

  if (understandingState.eventType && understandingState.eventType !== 'custom') score += 30
  if (understandingState.conditions?.length) score += 25
  if (understandingState.chains?.length) score += 20
  if (understandingState.thresholds?.length) score += 15
  if (understandingState.wallets?.length) score += 10

  return Math.min(score, 100)
}
