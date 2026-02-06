import { useEffect, useMemo, useState } from 'react'
import {
  Modal,
  Stack,
  TextInput,
  PasswordInput,
  Group,
  Button,
  Text,
  Textarea,
  Select,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertCircle, IconCheck } from '@tabler/icons-react'
import {
  notificationsApiService,
  type NotificationChannelEndpoint,
  type WebhookChannelConfig,
} from '../../services/notifications-api'

interface ConfigureWebhookModalProps {
  opened: boolean
  onClose: () => void
  channel?: NotificationChannelEndpoint | null
  onSaved?: (channel: NotificationChannelEndpoint) => void
}

interface WebhookFormState {
  label: string
  url: string
  method: 'POST' | 'GET'
  secret: string
  headers: string
}

const DEFAULT_FORM: WebhookFormState = {
  label: '',
  url: '',
  method: 'POST',
  secret: '',
  headers: '',
}

export function ConfigureWebhookModal({
  opened,
  onClose,
  channel = null,
  onSaved,
}: ConfigureWebhookModalProps) {
  const [formData, setFormData] = useState<WebhookFormState>(DEFAULT_FORM)
  const [isLoading, setIsLoading] = useState(false)

  const mode = channel ? 'edit' : 'create'

  useEffect(() => {
    if (!opened) return

    if (channel) {
      const config = (channel.config || {}) as Partial<WebhookChannelConfig>
      setFormData({
        label: channel.label || '',
        url: config.url || '',
        method: (config.method || 'POST') as WebhookFormState['method'],
        secret: '',
        headers: config.headers ? JSON.stringify(config.headers, null, 2) : '',
      })
    } else {
      setFormData(DEFAULT_FORM)
    }
  }, [channel, opened])

  const headerParseResult = useMemo(() => {
    if (!formData.headers.trim()) return { headers: undefined, error: null }
    try {
      const parsed = JSON.parse(formData.headers)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        return { headers: null, error: 'Headers must be a JSON object.' }
      }
      return { headers: parsed as Record<string, string>, error: null }
    } catch {
      return { headers: null, error: 'Headers must be valid JSON.' }
    }
  }, [formData.headers])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()

    if (headerParseResult.error) {
      notifications.show({
        title: 'Invalid headers',
        message: headerParseResult.error,
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    setIsLoading(true)
    try {
      const label = formData.label.trim()
      const url = formData.url.trim()
      const secret = formData.secret.trim()

      if (!label || !url) {
        throw new Error('Name and endpoint URL are required.')
      }

      const configPayload: WebhookChannelConfig = {
        url,
        method: formData.method,
        headers: headerParseResult.headers || {},
      }

      if (secret) {
        configPayload.secret = secret
      }

      let saved: NotificationChannelEndpoint

      if (mode === 'edit' && channel) {
        saved = await notificationsApiService.updateChannel(channel.id, {
          label,
          config: {
            ...(channel.config || {}),
            ...configPayload,
          },
        })
      } else {
        saved = await notificationsApiService.createWebhookChannel({
          label,
          url,
          method: formData.method,
          headers: headerParseResult.headers || {},
          secret: secret || undefined,
        })
      }

      notifications.show({
        title: mode === 'edit' ? 'Webhook updated' : 'Webhook configured',
        message: 'Your webhook endpoint is ready for alert delivery.',
        color: 'green',
        icon: <IconCheck size={16} />,
      })

      setFormData(DEFAULT_FORM)
      onSaved?.(saved)
      onClose()
    } catch (error: any) {
      notifications.show({
        title: 'Webhook save failed',
        message: error?.message || 'Unable to save webhook configuration.',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={mode === 'edit' ? 'Edit Webhook Endpoint' : 'Configure Webhook Endpoint'}
      size="md"
    >
      <form onSubmit={handleSubmit}>
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Receive real-time JSON payloads for alerts and workflow automations.
          </Text>

          <TextInput
            label="Name"
            placeholder="Production webhook"
            value={formData.label}
            onChange={(event) => setFormData({ ...formData, label: event.target.value })}
            required
          />

          <TextInput
            label="Endpoint URL"
            placeholder="https://api.yourdomain.com/webhooks/ekko"
            value={formData.url}
            onChange={(event) => setFormData({ ...formData, url: event.target.value })}
            required
          />

          <Select
            label="HTTP Method"
            data={['POST', 'GET']}
            value={formData.method}
            onChange={(value) =>
              setFormData({
                ...formData,
                method: (value as WebhookFormState['method']) || 'POST',
              })
            }
          />

          <PasswordInput
            label="Signing Secret (Optional)"
            placeholder="whsec_..."
            description="Used to verify signatures of incoming requests"
            value={formData.secret}
            onChange={(event) => setFormData({ ...formData, secret: event.target.value })}
          />

          <Textarea
            label="Custom Headers (Optional)"
            placeholder='{"Authorization": "Bearer ..."}'
            description="Provide JSON-formatted headers for webhook requests."
            value={formData.headers}
            onChange={(event) => setFormData({ ...formData, headers: event.target.value })}
            minRows={4}
          />

          <Group justify="flex-end" mt="md">
            <Button variant="subtle" onClick={onClose} disabled={isLoading}>
              Cancel
            </Button>
            <Button type="submit" loading={isLoading} style={{ backgroundColor: '#0F172A' }}>
              {mode === 'edit' ? 'Save Changes' : 'Save Webhook'}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
