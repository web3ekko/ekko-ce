import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Alert,
  Badge,
  Button,
  Center,
  Container,
  Divider,
  Group,
  Loader,
  Modal,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { IconAlertCircle, IconArrowLeft, IconCheck, IconEdit, IconTrash } from '@tabler/icons-react'
import { API_ENDPOINTS } from '../../config/api'
import { httpClient } from '../../services/http-client'
import { ChainLogo } from '../../components/brand/ChainLogo'
import { AlertEventBadge } from '../../components/alerts/AlertEventBadge'
import { AlertDetailSummaryCard } from '../../components/alerts/AlertDetailSummaryCard'
import { getChainIdentity } from '../../utils/chain-identity'

type AlertInstance = {
  id: string
  name: string
  nl_description: string
  enabled: boolean
  event_type: string
  sub_event: string
  alert_type?: string
  target_group?: string | null
  target_group_name?: string | null
  target_group_type?: string | null
  target_keys?: string[]
  processing_status?: string
  processing_error?: string
  created_at: string
  updated_at: string
  spec?: Record<string, unknown>
  chains?: string[]
}

function formatTargetSummary(alert: AlertInstance): string {
  if (alert.target_group_name) return `Group · ${alert.target_group_name}`
  if (alert.target_group) return `Group · ${alert.target_group}`
  if (Array.isArray(alert.target_keys) && alert.target_keys.length) {
    if (alert.target_keys.length === 1) return `Key · ${alert.target_keys[0]}`
    return `Keys · ${alert.target_keys.length}`
  }
  return 'No explicit target'
}

function getAlertChain(alert: AlertInstance): string | null {
  if (Array.isArray(alert.chains) && alert.chains.length > 0) {
    return alert.chains[0]
  }
  const spec = alert.spec as { scope?: { chains?: string[] } } | undefined
  const specChains = spec?.scope?.chains
  if (Array.isArray(specChains) && specChains.length > 0) {
    return specChains[0]
  }
  return null
}

export function AlertDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [alert, setAlert] = useState<AlertInstance | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  const [editOpened, editHandlers] = useDisclosure(false)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editEnabled, setEditEnabled] = useState(true)

  const statusBadge = useMemo(() => {
    if (!alert) return null
    const status = alert.enabled ? 'enabled' : 'disabled'
    return (
      <Badge color={alert.enabled ? 'green' : 'gray'} variant="light">
        {status}
      </Badge>
    )
  }, [alert])

  const load = async (alertId: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await httpClient.get<AlertInstance>(API_ENDPOINTS.ALERTS.DETAIL(alertId))
      setAlert(response.data)
    } catch (err) {
      console.error('Failed to load alert:', err)
      setError('Failed to load alert')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!id) return
    load(id)
  }, [id])

  useEffect(() => {
    if (!alert) return
    setEditName(alert.name)
    setEditDescription(alert.nl_description || '')
    setEditEnabled(!!alert.enabled)
  }, [alert])

  const handleSave = async () => {
    if (!alert) return
    setIsSaving(true)
    try {
      const response = await httpClient.patch<AlertInstance>(API_ENDPOINTS.ALERTS.UPDATE(alert.id), {
        name: editName,
        nl_description: editDescription,
        enabled: editEnabled,
      })
      setAlert(response.data)
      editHandlers.close()
      notifications.show({
        title: 'Saved',
        message: 'Alert updated',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
    } catch (err) {
      console.error('Failed to update alert:', err)
      notifications.show({
        title: 'Error',
        message: 'Failed to update alert',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!alert) return
    const ok = confirm('Delete this alert? This cannot be undone.')
    if (!ok) return

    setIsSaving(true)
    try {
      await httpClient.delete(API_ENDPOINTS.ALERTS.DELETE(alert.id))
      notifications.show({
        title: 'Deleted',
        message: 'Alert deleted',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      navigate('/dashboard/alerts')
    } catch (err) {
      console.error('Failed to delete alert:', err)
      notifications.show({
        title: 'Error',
        message: 'Failed to delete alert',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleToggleEnabled = async (nextEnabled: boolean) => {
    if (!alert) return
    setIsSaving(true)
    try {
      const response = await httpClient.patch<AlertInstance>(API_ENDPOINTS.ALERTS.UPDATE(alert.id), {
        enabled: nextEnabled,
      })
      setAlert(response.data)
    } catch (err) {
      console.error('Failed to toggle alert:', err)
      notifications.show({
        title: 'Error',
        message: 'Failed to toggle alert',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSaving(false)
    }
  }

  if (!id) {
    return (
      <Container size="lg" py="xl">
        <Alert icon={<IconAlertCircle size={16} />} color="red">
          Missing alert id
        </Alert>
      </Container>
    )
  }

  if (isLoading) {
    return (
      <Center h={320}>
        <Stack align="center" gap="sm">
          <Loader size="lg" />
          <Text c="dimmed">Loading alert…</Text>
        </Stack>
      </Center>
    )
  }

  if (error || !alert) {
    return (
      <Container size="lg" py="xl">
        <Alert icon={<IconAlertCircle size={16} />} color="red">
          {error || 'Alert not found'}
        </Alert>
        <Button mt="md" variant="light" onClick={() => navigate('/dashboard/alerts')}>
          Back to Alerts
        </Button>
      </Container>
    )
  }

  const alertChain = getAlertChain(alert)

  const chainIdentity = alertChain ? getChainIdentity(alertChain) : null
  const chainBadge = alertChain ? (
    <Badge
      size="sm"
      variant="light"
      styles={{
        root: {
          backgroundColor: `${chainIdentity?.color || '#64748B'}14`,
          color: chainIdentity?.color || '#64748B',
          border: `1px solid ${(chainIdentity?.color || '#64748B')}30`,
        },
      }}
    >
      {chainIdentity?.name || alertChain}
    </Badge>
  ) : null

  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Stack gap={6}>
            <Button
              variant="subtle"
              leftSection={<IconArrowLeft size={16} />}
              onClick={() => navigate(-1)}
              mb="xs"
            >
              Back
            </Button>

            <Group gap="sm" align="center" mb={4} wrap="wrap" style={{ maxWidth: '100%' }}>
              {alertChain && <ChainLogo chain={alertChain} size="sm" />}
              <Text
                fw={800}
                size="xl"
                c="#0F172A"
                style={{
                  whiteSpace: 'normal',
                  wordBreak: 'break-word',
                  overflowWrap: 'anywhere',
                  maxWidth: '100%',
                }}
              >
                {alert.name}
              </Text>
              {statusBadge}
              <AlertEventBadge
                eventType={alert.event_type}
                subEvent={alert.sub_event}
                chain={alertChain || undefined}
                size="sm"
              />
              {chainBadge}
            </Group>

            <Text
              c="#475569"
              style={{
                whiteSpace: 'normal',
                wordBreak: 'break-word',
                overflowWrap: 'anywhere',
              }}
            >
              {alert.nl_description || 'No description'}
            </Text>
          </Stack>

          <Group gap="sm" wrap="wrap">
            <Button variant="light" leftSection={<IconEdit size={16} />} onClick={editHandlers.open}>
              Edit
            </Button>
            <Button variant="light" color="red" leftSection={<IconTrash size={16} />} onClick={handleDelete}>
              Delete
            </Button>
          </Group>
        </Group>

        <AlertDetailSummaryCard
          eventType={alert.event_type}
          subEvent={alert.sub_event}
          alertType={alert.alert_type || 'wallet'}
          targetSummary={formatTargetSummary(alert)}
          processingStatus={alert.processing_status || 'unknown'}
          enabled={!!alert.enabled}
          isSaving={isSaving}
          createdAt={alert.created_at}
          updatedAt={alert.updated_at}
          onToggle={handleToggleEnabled}
        />

        {(alert.processing_error || '').trim().length > 0 && (
          <Alert icon={<IconAlertCircle size={16} />} color="red">
            {alert.processing_error}
          </Alert>
        )}
      </Stack>

      <Modal opened={editOpened} onClose={editHandlers.close} title="Edit Alert" size="lg">
        <Stack gap="md">
          <TextInput label="Name" value={editName} onChange={(e) => setEditName(e.currentTarget.value)} />
          <Textarea
            label="Description"
            minRows={3}
            value={editDescription}
            onChange={(e) => setEditDescription(e.currentTarget.value)}
          />
          <Group justify="space-between" align="center">
            <Text size="sm">Enabled</Text>
            <Switch checked={editEnabled} onChange={(e) => setEditEnabled(e.currentTarget.checked)} />
          </Group>
          <Divider />
          <Group justify="flex-end">
            <Button variant="subtle" onClick={editHandlers.close}>
              Cancel
            </Button>
            <Button onClick={handleSave} loading={isSaving} style={{ backgroundColor: '#2563EB' }}>
              Save
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  )
}
