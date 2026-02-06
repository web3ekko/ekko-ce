import { useCallback, useEffect, useRef, useState } from 'react'
import { alertsApiService, type ProposedSpec, type ParseJobResponse, type ParseResultResponse } from '../services/alerts-api'
import { websocketService } from '../services/websocket'

export type NLPJobStatus = 'idle' | 'connecting' | 'processing' | 'completed' | 'error'

type NLPProgress = {
  message: string
  percent?: number
}

const NLP_FALLBACK_TIMEOUT_MS = 90000

type UseNLPWebSocketOptions = {
  onComplete?: (spec: ProposedSpec) => void
  onError?: (message: string) => void
}

const PROGRESS_STEPS: string[] = [
  'Analyzing intent...',
  'Checking chain support...',
  'Drafting alert logic...',
]

function stageToMessage(stage: unknown): string | null {
  if (typeof stage !== 'string') return null
  const s = stage.trim().toLowerCase()
  if (!s) return null
  if (s === 'classify' || s === 'classification') return 'Analyzing intent...'
  if (s === 'resolve_scope' || s === 'resolve-targets' || s === 'resolve_targets') return 'Checking chain support...'
  if (s === 'draft_plan' || s === 'draft_template') return 'Drafting alert logic...'
  if (s === 'validate') return 'Validating...'
  if (s === 'compile') return 'Compiling executable...'
  if (s === 'assemble_preview') return 'Assembling preview...'
  return stage
}

function extractJobId(payload: Record<string, unknown>): string | null {
  const direct = payload.job_id || payload.jobId || payload.client_request_id
  if (typeof direct === 'string' && direct.length > 0) return direct
  const nested = payload.data
  if (nested && typeof nested === 'object') {
    const nestedJob = (nested as Record<string, unknown>).job_id
    if (typeof nestedJob === 'string' && nestedJob.length > 0) return nestedJob
  }
  return null
}

function extractSpec(payload: Record<string, unknown>): ProposedSpec | null {
  const candidates = [
    payload.spec,
    payload.result,
    payload.proposed_spec,
    payload.data,
  ]
  for (const candidate of candidates) {
    if (candidate && typeof candidate === 'object') {
      return candidate as ProposedSpec
    }
  }
  return null
}

export function useNLPWebSocket(options: UseNLPWebSocketOptions = {}) {
  const [status, setStatus] = useState<NLPJobStatus>('idle')
  const [jobId, setJobId] = useState<string | null>(null)
  const [result, setResult] = useState<ProposedSpec | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<NLPProgress | null>(null)

  const activeJobRef = useRef<string | null>(null)
  const activeFingerprintRef = useRef<string | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const progressRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const clearTimers = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    if (progressRef.current) {
      clearInterval(progressRef.current)
      progressRef.current = null
    }
  }

  const reset = useCallback(() => {
    clearTimers()
    activeJobRef.current = null
    activeFingerprintRef.current = null
    setJobId(null)
    setStatus('idle')
    setResult(null)
    setError(null)
    setProgress(null)
  }, [])

  const startProgressTicker = useCallback(() => {
    let idx = 0
    setProgress({ message: PROGRESS_STEPS[idx] })
    if (progressRef.current) clearInterval(progressRef.current)
    progressRef.current = setInterval(() => {
      idx = (idx + 1) % PROGRESS_STEPS.length
      setProgress({ message: PROGRESS_STEPS[idx] })
    }, 1600)
  }, [])

  const submitJob = useCallback(async (
    description: string,
    clientRequestId?: string,
    pipelineId?: string,
    context?: Record<string, unknown>,
    fingerprint?: string
  ) => {
    if (
      fingerprint &&
      activeFingerprintRef.current === fingerprint &&
      (status === 'connecting' || status === 'processing')
    ) {
      return
    }
    clearTimers()
    setStatus('connecting')
    setError(null)
    setResult(null)
    setProgress({ message: 'Submitting request...' })

    const response: ParseJobResponse = await alertsApiService.parseNaturalLanguageJob(description, clientRequestId, pipelineId, context)

    if (!response.success || !response.job_id) {
      const message = response.error || 'Failed to start NLP job'
      setStatus('error')
      setError(message)
      setProgress(null)
      options.onError?.(message)
      return
    }

    setJobId(response.job_id)
    activeJobRef.current = response.job_id
    activeFingerprintRef.current = fingerprint || null
    setStatus('processing')
    startProgressTicker()

    timeoutRef.current = setTimeout(async () => {
      if (!activeJobRef.current) return
      const fallback: ParseResultResponse = await alertsApiService.getParseResult(activeJobRef.current)
      if (fallback.status === 'completed' && fallback.result) {
        setStatus('completed')
        setResult(fallback.result)
        setProgress({ message: 'Complete' })
        clearTimers()
        options.onComplete?.(fallback.result)
        return
      }
      const message = fallback.error || 'NLP processing timed out. Please retry.'
      setStatus('error')
      setError(message)
      setProgress(null)
      options.onError?.(message)
    }, NLP_FALLBACK_TIMEOUT_MS)
  }, [options, startProgressTicker, status])

  useEffect(() => {
    const handleStatus = (payload: Record<string, unknown>) => {
      const incomingJobId = extractJobId(payload)
      if (incomingJobId && incomingJobId !== activeJobRef.current) return
      const rawProgress = payload.progress
      const percent =
        typeof rawProgress === 'number' && Number.isFinite(rawProgress)
          ? Math.max(0, Math.min(100, rawProgress))
          : undefined
      const stageMsg = stageToMessage(payload.stage)
      const message =
        typeof payload.message === 'string'
          ? payload.message
          : stageMsg
            ? stageMsg
            : typeof payload.status === 'string'
              ? payload.status
              : 'Processing...'
      setStatus('processing')
      setProgress({ message, percent })

      // Once we get deterministic progress updates, stop the spinner-ticker.
      if (percent !== undefined && progressRef.current) {
        clearInterval(progressRef.current)
        progressRef.current = null
      }
    }

    const handleComplete = (payload: Record<string, unknown>) => {
      const incomingJobId = extractJobId(payload)
      if (incomingJobId && incomingJobId !== activeJobRef.current) return
      const spec = extractSpec(payload)
      if (!spec) return
      setResult(spec)
      setStatus('completed')
      setProgress({ message: 'Complete' })
      clearTimers()
      activeFingerprintRef.current = null
      options.onComplete?.(spec)
    }

    const handleError = (payload: Record<string, unknown>) => {
      const incomingJobId = extractJobId(payload)
      if (incomingJobId && incomingJobId !== activeJobRef.current) return
      const message =
        typeof payload.message === 'string'
          ? payload.message
          : typeof payload.error === 'string'
            ? payload.error
            : 'NLP processing failed'
      setStatus('error')
      setError(message)
      setProgress(null)
      clearTimers()
      activeFingerprintRef.current = null
      options.onError?.(message)
    }

    const unsubStatus = websocketService.on('nlp.status', handleStatus)
    const unsubProgress = websocketService.on('nlp.progress', handleStatus)
    const unsubComplete = websocketService.on('nlp.complete', handleComplete)
    const unsubError = websocketService.on('nlp.error', handleError)

    return () => {
      unsubStatus()
      unsubProgress()
      unsubComplete()
      unsubError()
      clearTimers()
    }
  }, [options])

  return {
    status,
    jobId,
    result,
    error,
    progress,
    submitJob,
    reset,
  }
}
