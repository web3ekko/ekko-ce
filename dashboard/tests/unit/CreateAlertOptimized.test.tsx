/**
 * Create Alert Optimized component test
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { MantineProvider } from '@mantine/core'
import { CreateAlertOptimized } from '../../src/components/alerts/CreateAlertOptimized'

const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <MantineProvider>{children}</MantineProvider>
)

type FetchArgs = Parameters<typeof fetch>

const mockSaveTemplateFromJob = vi.fn()
const mockGetTemplateLatest = vi.fn()
const mockCreateAlert = vi.fn()
const mockRunInlinePreview = vi.fn()
const mockRunTemplatePreviewFromJob = vi.fn()
const mockClearPreview = vi.fn()
const mockSubmitJob = vi.fn()
const mockReset = vi.fn()
const mockNlpResult = {
  schema_version: 'proposed_spec_v2',
  template: { schema_version: 'alert_template_v2', variables: [] },
  required_user_inputs: {
    supported_trigger_types: ['event_driven'],
    required_variables: [],
    targets_required: false,
  },
  human_preview: { summary: 'Test alert' },
}
let nlpResult: typeof mockNlpResult | null = null

vi.mock('../../src/services/alerts-api', () => ({
  alertsApiService: {
    saveTemplateFromJob: (...args: unknown[]) => mockSaveTemplateFromJob(...args),
    getTemplateLatest: (...args: unknown[]) => mockGetTemplateLatest(...args),
  },
}))

vi.mock('../../src/store/simple-alerts', () => ({
  useSimpleAlerts: () => ({
    previewResult: null,
    isPreviewLoading: false,
    runInlinePreview: mockRunInlinePreview,
    runTemplatePreviewFromJob: mockRunTemplatePreviewFromJob,
    clearPreview: mockClearPreview,
    createAlert: mockCreateAlert,
  }),
}))

vi.mock('../../src/hooks/useNLPWebSocket', () => ({
  useNLPWebSocket: () => ({
    status: 'completed',
    jobId: 'job-1',
    result: nlpResult,
    error: null,
    progress: null,
    submitJob: mockSubmitJob,
    reset: mockReset,
  }),
}))

describe('CreateAlertOptimized', () => {
  const originalFetch = global.fetch
  const originalLocalStorage = globalThis.localStorage

  beforeEach(() => {
    mockSaveTemplateFromJob.mockReset()
    mockGetTemplateLatest.mockReset()
    mockCreateAlert.mockReset()
    mockRunInlinePreview.mockReset()
    mockRunTemplatePreviewFromJob.mockReset()
    mockClearPreview.mockReset()
    mockSubmitJob.mockReset()
    mockReset.mockReset()
    nlpResult = null

    mockSaveTemplateFromJob.mockResolvedValue({
      success: true,
      template_id: 'tpl-1',
      template_version: 1,
      fingerprint: 'fingerprint-1',
    })

    mockGetTemplateLatest.mockResolvedValue({
      success: true,
      template: {
        id: 'tpl-market-1',
        fingerprint: 'market-fp',
      },
      bundle: {
        template_version: 3,
        spec_hash: 'spec-hash',
        executable_id: 'exec-id',
        registry_snapshot: { kind: 'datasource_catalog', version: 'v1', hash: 'sha256:x' },
        template_spec: { schema_version: 'alert_template_v2', name: 'Marketplace Template', target_kind: 'wallet', variables: [], scope: { networks: ['ETH:mainnet'] }, trigger: { evaluation_mode: 'periodic' } },
        executable: { schema_version: 'alert_executable_v1' },
      },
    })

    const store = new Map<string, string>()
    globalThis.localStorage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value)
      },
      removeItem: (key: string) => {
        store.delete(key)
      },
      clear: () => {
        store.clear()
      },
      key: (index: number) => Array.from(store.keys())[index] ?? null,
      get length() {
        return store.size
      },
    } as Storage

    globalThis.localStorage.removeItem('alert_draft_v1')
    global.fetch = vi.fn(async (input: FetchArgs[0]) => {
      const url = typeof input === 'string' ? input : input.url

      if (url.includes('/api/groups/accounts/')) {
        return {
          ok: false,
          status: 404,
          headers: { get: () => 'application/json' },
          json: async () => ({ detail: 'Not found' }),
          text: async () => JSON.stringify({ detail: 'Not found' }),
        } as Response
      }

      if (url.includes('/api/groups/by_type/')) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => 'application/json' },
          json: async () => ([]),
          text: async () => '[]',
        } as Response
      }

      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({}),
        text: async () => '{}',
      } as Response
    })
  })

  afterEach(() => {
    global.fetch = originalFetch
    globalThis.localStorage = originalLocalStorage
  })

  it('renders without update-depth errors on mount', async () => {
    expect(() => {
      render(
        <TestWrapper>
          <CreateAlertOptimized onAlertCreated={() => {}} onCancel={() => {}} />
        </TestWrapper>
      )
    }).not.toThrow()

    expect(screen.getByLabelText(/ethereum logo/i)).toBeInTheDocument()

    await new Promise((resolve) => setTimeout(resolve, 0))
  })

  it('shows alert creation errors inline', async () => {
    const user = userEvent.setup()
    mockCreateAlert.mockRejectedValueOnce({
      response: {
        data: {
          error: 'Backend rejected alert',
        },
      },
    })

    render(
      <TestWrapper>
        <CreateAlertOptimized onAlertCreated={() => {}} onCancel={() => {}} />
      </TestWrapper>
    )

    const [input] = screen.getAllByRole('textbox')
    await user.type(input, 'Alert me when my wallet receives more than 1 ETH')

    nlpResult = mockNlpResult
    await user.type(input, ' ')

    const saveButton = screen.getByRole('button', { name: /save template/i })
    await waitFor(() => expect(saveButton).toBeEnabled())
    await user.click(saveButton)

    const createButton = screen.getByRole('button', { name: /create alert/i })
    await waitFor(() => expect(createButton).toBeEnabled())
    await user.click(createButton)

    await waitFor(() => {
      expect(screen.getByText('Backend rejected alert')).toBeInTheDocument()
    })
  }, 10000)

  it('auto-saves the template when creating an alert (no explicit Save Template click)', async () => {
    const user = userEvent.setup()

    render(
      <TestWrapper>
        <CreateAlertOptimized onAlertCreated={() => {}} onCancel={() => {}} />
      </TestWrapper>
    )

    const [input] = screen.getAllByRole('textbox')
    await user.type(input, 'Alert me when my wallet receives more than 1 ETH')

    nlpResult = mockNlpResult
    await user.type(input, ' ')

    mockCreateAlert.mockResolvedValueOnce({ id: 'a1' })

    const createButton = screen.getByRole('button', { name: /create alert/i })
    await waitFor(() => expect(createButton).toBeEnabled())
    await user.click(createButton)

    await waitFor(() => {
      expect(mockSaveTemplateFromJob).toHaveBeenCalled()
      expect(mockCreateAlert).toHaveBeenCalled()
      expect(mockCreateAlert.mock.calls[0][0]).toMatchObject({
        template_id: 'tpl-1',
        template_version: 1,
      })
    })
  })

  it('boots from a marketplace template ref and creates an instance from the pinned template version', async () => {
    const user = userEvent.setup()

    render(
      <TestWrapper>
        <CreateAlertOptimized
          initialTemplateRef={{ templateId: 'tpl-market-1', templateVersion: 3 }}
          onAlertCreated={() => {}}
          onCancel={() => {}}
        />
      </TestWrapper>
    )

    await waitFor(() => expect(mockGetTemplateLatest).toHaveBeenCalledWith('tpl-market-1'))
    expect(screen.queryByText('Save Template')).not.toBeInTheDocument()

    // Open instance settings (targets live in the advanced section).
    await user.click(screen.getByLabelText(/toggle alert instance settings/i))

    // Switch to key mode and provide a wallet key.
    await user.click(screen.getByText(/specific wallets/i))
    const textarea = screen.getByPlaceholderText(/paste wallet addresses/i)
    await user.type(textarea, '0xabc')

    mockCreateAlert.mockResolvedValueOnce({ id: 'a1' })

    const createButton = screen.getByRole('button', { name: /create alert/i })
    await user.click(createButton)

    await waitFor(() => {
      expect(mockCreateAlert).toHaveBeenCalled()
      expect(mockCreateAlert.mock.calls[0][0]).toMatchObject({
        template_id: 'tpl-market-1',
        template_version: 3,
      })
    })
  })

  it('runs template preview (Test Alert) using job_id + selected targets for template-first ProposedSpec', async () => {
    const user = userEvent.setup()

    render(
      <TestWrapper>
        <CreateAlertOptimized onAlertCreated={() => {}} onCancel={() => {}} />
      </TestWrapper>
    )

    const [input] = screen.getAllByRole('textbox')
    await user.type(input, 'Alert me when balance drops below 0.5')

    nlpResult = {
      schema_version: 'proposed_spec_v2',
      template: { schema_version: 'alert_template_v2', variables: [] },
      compiled_executable: { schema_version: 'alert_executable_v1' },
      required_user_inputs: {
        supported_trigger_types: ['periodic'],
        required_variables: [],
        targets_required: true,
      },
      human_preview: { summary: 'Test alert' },
    }
    await user.type(input, ' ')

    // Open instance settings (targets live in the advanced section).
    await user.click(screen.getByLabelText(/toggle alert instance settings/i))

    await user.click(screen.getByText(/specific wallets/i))
    const textarea = screen.getByPlaceholderText(/paste wallet addresses/i)
    await user.type(textarea, '0xabc')

    const testButton = screen.getByRole('button', { name: /test alert/i })
    await user.click(testButton)

    await waitFor(() => {
      expect(mockRunTemplatePreviewFromJob).toHaveBeenCalled()
      expect(mockRunTemplatePreviewFromJob.mock.calls[0][0]).toMatchObject({
        job_id: 'job-1',
        target_selector: { mode: 'keys', keys: ['ETH:mainnet:0xabc'] },
        sample_size: 50,
      })
    })
  })

  it('disables save/test actions when ProposedSpec includes blocking missing_info', async () => {
    const user = userEvent.setup()

    render(
      <TestWrapper>
        <CreateAlertOptimized onAlertCreated={() => {}} onCancel={() => {}} />
      </TestWrapper>
    )

    const [input] = screen.getAllByRole('textbox')
    await user.type(input, 'Alert me when balance drops below 0.5')

    nlpResult = {
      schema_version: 'proposed_spec_v2',
      template: { schema_version: 'alert_template_v2', variables: [] },
      compiled_executable: { schema_version: 'alert_executable_v1' },
      required_user_inputs: {
        supported_trigger_types: ['periodic'],
        required_variables: [],
        targets_required: false,
      },
      confidence: 0.4,
      missing_info: [{ code: 'missing_network', message: 'Select a network.' }],
      human_preview: { summary: 'Test alert' },
    }

    await user.type(input, ' ')

    const saveButton = screen.getByRole('button', { name: /save template/i })
    await waitFor(() => expect(saveButton).toBeDisabled())

    const testButton = screen.getByRole('button', { name: /test alert/i })
    expect(testButton).toBeDisabled()
  })

  it('passes notification overrides when provided', async () => {
    const user = userEvent.setup()

    render(
      <TestWrapper>
        <CreateAlertOptimized onAlertCreated={() => {}} onCancel={() => {}} />
      </TestWrapper>
    )

    const [input] = screen.getAllByRole('textbox')
    await user.type(input, 'Alert me when my wallet receives more than 1 ETH')

    nlpResult = mockNlpResult
    await user.type(input, ' ')

    const toggleAdvanced = screen.getByLabelText(/toggle alert instance settings/i)
    await user.click(toggleAdvanced)

    const titleInput = await screen.findByLabelText(/notification title/i)
    const bodyInput = await screen.findByLabelText(/notification body/i)

    await user.clear(titleInput)
    await user.type(titleInput, 'Custom title')
    await user.clear(bodyInput)
    await user.type(bodyInput, 'Custom body with target short')

    const createButton = screen.getByRole('button', { name: /create alert/i })
    await waitFor(() => expect(createButton).toBeEnabled())
    await user.click(createButton)

    await waitFor(() => {
      expect(mockCreateAlert).toHaveBeenCalledWith(expect.objectContaining({
        notification_overrides: {
          title_template: 'Custom title',
          body_template: 'Custom body with target short',
        },
      }))
    })
  }, 10000)
})
