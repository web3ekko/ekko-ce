import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Center,
  Checkbox,
  Group,
  Loader,
  Modal,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
  Tooltip,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import {
  IconAlertCircle,
  IconBell,
  IconCheck,
  IconPlayerPause,
  IconPlayerPlay,
  IconPlus,
  IconRefresh,
  IconSearch,
  IconTrash,
  IconWand,
} from '@tabler/icons-react'
import { AlertCard } from '../components/alerts/AlertCard'
import { CreateAlertOptimized } from '../components/alerts/CreateAlertOptimized'
import { useSimpleAlerts, type Alert as AlertType } from '../store/simple-alerts'
import { alertsApiService } from '../services/alerts-api'

const NOTIFICATION_OVERRIDE_KEY = '__notification_overrides'

export function AlertsPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { alerts, isLoading, error, loadAlerts, toggleAlert, deleteAlert, createAlert, updateAlert, setError } =
    useSimpleAlerts()

  const [createModalOpened, createModalHandlers] = useDisclosure(false)
  const [editOpened, editHandlers] = useDisclosure(false)

  const [searchQuery, setSearchQuery] = useState('')
  const [filterStatus, setFilterStatus] = useState<string | null>(null)
  const [tab, setTab] = useState<'all' | 'active' | 'paused'>('all')

  const [isSelectionMode, setIsSelectionMode] = useState(false)
  const [selectedAlerts, setSelectedAlerts] = useState<Set<string>>(new Set())

  const [editingAlert, setEditingAlert] = useState<AlertType | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editEnabled, setEditEnabled] = useState(true)
  const [initialTemplateRef, setInitialTemplateRef] = useState<{ templateId: string; templateVersion: number } | null>(null)

  useEffect(() => {
    loadAlerts()
  }, [loadAlerts])

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    if (params.get('create') === 'true') {
      const templateId = params.get('template_id')
      const templateVersionRaw = params.get('template_version')
      if (templateId && templateVersionRaw && /^\d+$/.test(templateVersionRaw)) {
        setInitialTemplateRef({ templateId, templateVersion: Number(templateVersionRaw) })
      } else {
        setInitialTemplateRef(null)
      }
      createModalHandlers.open()
      navigate('/dashboard/alerts', { replace: true })
    }
  }, [createModalHandlers, location.search, navigate])

  useEffect(() => {
    if (!isSelectionMode) setSelectedAlerts(new Set())
  }, [isSelectionMode])

  const filteredAlerts = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return alerts.filter((alert) => {
      const matchesSearch =
        !q ||
        alert.name.toLowerCase().includes(q) ||
        (alert.description || '').toLowerCase().includes(q) ||
        (alert.event_type || '').toLowerCase().includes(q)

      const matchesStatus =
        !filterStatus ||
        (filterStatus === 'active' && alert.enabled) ||
        (filterStatus === 'paused' && !alert.enabled)

      return matchesSearch && matchesStatus
    })
  }, [alerts, filterStatus, searchQuery])

  const displayAlerts = useMemo(() => {
    if (tab === 'active') return filteredAlerts.filter((a) => a.enabled)
    if (tab === 'paused') return filteredAlerts.filter((a) => !a.enabled)
    return filteredAlerts
  }, [filteredAlerts, tab])

  const totalAlerts = alerts.length
  const activeCount = alerts.filter((a) => a.enabled).length

  const toggleAlertSelection = (alertId: string) => {
    setSelectedAlerts((prev) => {
      const next = new Set(prev)
      if (next.has(alertId)) next.delete(alertId)
      else next.add(alertId)
      return next
    })
  }

  const handleSelectAll = () => {
    setSelectedAlerts((prev) => {
      if (prev.size === displayAlerts.length) return new Set()
      return new Set(displayAlerts.map((a) => a.id))
    })
  }

  const handleToggleAlert = async (alertId: string) => {
    const existing = alerts.find((a) => a.id === alertId)
    const wasEnabled = !!existing?.enabled

    await toggleAlert(alertId)
    notifications.show({
      title: wasEnabled ? 'Alert disabled' : 'Alert enabled',
      message: existing ? existing.name : 'Alert updated',
      color: wasEnabled ? 'orange' : 'green',
      icon: wasEnabled ? <IconPlayerPause size={16} /> : <IconCheck size={16} />,
    })
  }

  const handleDeleteAlert = async (alertId: string) => {
    const ok = confirm('Delete this alert? This cannot be undone.')
    if (!ok) return

    await deleteAlert(alertId)
    notifications.show({
      title: 'Alert deleted',
      message: 'The alert has been removed',
      color: 'red',
      icon: <IconAlertCircle size={16} />,
    })
  }

  const handleDuplicateAlert = async (alert: AlertType) => {
    // Always duplicate from the pinned template bundle (template_id + template_version).
    // Fetch detail to ensure we have targets + variables even if list payload is minimal.
    const detail = await alertsApiService.getAlert(alert.id)

    const splitTemplateParams = (params: Record<string, unknown>) => {
      const nextParams = { ...params }
      const rawOverrides = nextParams[NOTIFICATION_OVERRIDE_KEY]
      delete nextParams[NOTIFICATION_OVERRIDE_KEY]

      if (!rawOverrides || typeof rawOverrides !== 'object') {
        return { variableValues: nextParams, notificationOverrides: undefined }
      }

      const overrides = rawOverrides as { title_template?: unknown; body_template?: unknown }
      const title =
        typeof overrides.title_template === 'string' && overrides.title_template.trim()
          ? overrides.title_template.trim()
          : undefined
      const body =
        typeof overrides.body_template === 'string' && overrides.body_template.trim()
          ? overrides.body_template.trim()
          : undefined

      if (!title && !body) {
        return { variableValues: nextParams, notificationOverrides: undefined }
      }

      return {
        variableValues: nextParams,
        notificationOverrides: { title_template: title, body_template: body },
      }
    }

    const templateId = (detail as any)?.template || alert.template_id
    const templateVersion = (detail as any)?.template_version || alert.template_version
    if (!templateId || !templateVersion) {
      notifications.show({
        title: 'Template Missing',
        message: 'This alert is not template-based and cannot be duplicated in the template-first UI.',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    const params = ((detail as any)?.template_params as Record<string, unknown>) || {}
    const { variableValues, notificationOverrides } = splitTemplateParams(params)

    await createAlert({
      template_id: String(templateId),
      template_version: Number(templateVersion),
      name: `${alert.name} (copy)`,
      enabled: alert.enabled,
      trigger_type: ((detail as any)?.trigger_type as any) || 'event_driven',
      trigger_config: ((detail as any)?.trigger_config as any) || {},
      target_selector: (detail as any)?.target_group
        ? { mode: 'group', group_id: (detail as any).target_group }
        : { mode: 'keys', keys: Array.isArray((detail as any)?.target_keys) ? (detail as any).target_keys : [] },
      variable_values: variableValues,
      notification_overrides: notificationOverrides,
    })

    notifications.show({
      title: 'Alert duplicated',
      message: 'A new alert instance was created from the same template version',
      color: 'green',
      icon: <IconCheck size={16} />,
    })
  }

  const handleEditAlert = (alert: AlertType) => {
    setEditingAlert(alert)
    setEditName(alert.name)
    setEditDescription(alert.description || '')
    setEditEnabled(!!alert.enabled)
    editHandlers.open()
  }

  const handleSaveEdit = async () => {
    if (!editingAlert) return
    await updateAlert(editingAlert.id, {
      name: editName,
      description: editDescription,
      enabled: editEnabled,
    })
    notifications.show({
      title: 'Saved',
      message: 'Alert updated',
      color: 'green',
      icon: <IconCheck size={16} />,
    })
    editHandlers.close()
    setEditingAlert(null)
  }

  const handleBulkEnable = async () => {
    const ids = Array.from(selectedAlerts)
    for (const id of ids) {
      const alert = alerts.find((a) => a.id === id)
      if (alert && !alert.enabled) await toggleAlert(id)
    }
    notifications.show({
      title: 'Enabled',
      message: `${ids.length} alert(s) enabled`,
      color: 'green',
    })
    setSelectedAlerts(new Set())
    setIsSelectionMode(false)
  }

  const handleBulkDisable = async () => {
    const ids = Array.from(selectedAlerts)
    for (const id of ids) {
      const alert = alerts.find((a) => a.id === id)
      if (alert && alert.enabled) await toggleAlert(id)
    }
    notifications.show({
      title: 'Disabled',
      message: `${ids.length} alert(s) disabled`,
      color: 'orange',
    })
    setSelectedAlerts(new Set())
    setIsSelectionMode(false)
  }

  const handleBulkDelete = async () => {
    const ids = Array.from(selectedAlerts)
    const ok = confirm(`Delete ${ids.length} alert(s)? This cannot be undone.`)
    if (!ok) return

    for (const id of ids) {
      await deleteAlert(id)
    }
    notifications.show({
      title: 'Deleted',
      message: `${ids.length} alert(s) deleted`,
      color: 'red',
    })
    setSelectedAlerts(new Set())
    setIsSelectionMode(false)
  }

  if (isLoading && alerts.length === 0) {
    return (
      <Center h={320}>
        <Stack align="center" gap="sm">
          <Loader size="lg" color="blue" />
          <Text c="dimmed">Loading alerts…</Text>
        </Stack>
      </Center>
    )
  }

  return (
    <Stack gap="sm">
      <Group justify="space-between" align="center">
        <Group gap="sm">
          <Title order={3} c="#0F172A">
            Alerts
          </Title>
          <Group gap="xs" visibleFrom="sm">
            <Badge size="sm" variant="light" color="blue" leftSection={<IconBell size={10} />}>
              {totalAlerts} total
            </Badge>
            <Badge size="sm" variant="light" color="green" leftSection={<IconCheck size={10} />}>
              {activeCount} active
            </Badge>
          </Group>
        </Group>

        <Group gap="xs">
          <Button variant="subtle" size="xs" leftSection={<IconWand size={14} />} onClick={createModalHandlers.open}>
            AI Creator
          </Button>
          <Button
            size="xs"
            leftSection={<IconPlus size={14} />}
            style={{ backgroundColor: '#2563EB' }}
            onClick={createModalHandlers.open}
          >
            Create Alert
          </Button>
        </Group>
      </Group>

      {error && (
        <Alert icon={<IconAlertCircle size={14} />} color="red" onClose={() => setError(null)} withCloseButton py="xs">
          {error}
        </Alert>
      )}

      {isSelectionMode && selectedAlerts.size > 0 && (
        <Paper p="xs" radius="sm" withBorder bg="#EFF6FF">
          <Group justify="space-between" align="center">
            <Group gap="xs">
              <Checkbox
                checked={selectedAlerts.size === displayAlerts.length}
                indeterminate={selectedAlerts.size > 0 && selectedAlerts.size < displayAlerts.length}
                onChange={handleSelectAll}
                size="xs"
              />
              <Text size="xs" fw={500} c="#2563EB">
                {selectedAlerts.size} selected
              </Text>
            </Group>
            <Group gap="xs">
              <Tooltip label="Enable">
                <ActionIcon size="sm" variant="light" color="green" onClick={handleBulkEnable}>
                  <IconPlayerPlay size={14} />
                </ActionIcon>
              </Tooltip>
              <Tooltip label="Disable">
                <ActionIcon size="sm" variant="light" color="orange" onClick={handleBulkDisable}>
                  <IconPlayerPause size={14} />
                </ActionIcon>
              </Tooltip>
              <Tooltip label="Delete">
                <ActionIcon size="sm" variant="light" color="red" onClick={handleBulkDelete}>
                  <IconTrash size={14} />
                </ActionIcon>
              </Tooltip>
            </Group>
          </Group>
        </Paper>
      )}

      <Group justify="space-between" gap="xs">
        <Group gap="xs" style={{ flex: 1 }}>
          <TextInput
            placeholder="Search alerts…"
            leftSection={<IconSearch size={14} />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            size="xs"
            style={{ flex: 1, maxWidth: 280 }}
            styles={{
              input: {
                border: '1px solid #E6E9EE',
                '&:focus': { borderColor: '#2563EB' },
              },
            }}
          />
          <Select
            placeholder="Status"
            data={[
              { value: 'active', label: 'Active' },
              { value: 'paused', label: 'Paused' },
            ]}
            value={filterStatus}
            onChange={setFilterStatus}
            clearable
            size="xs"
            style={{ width: 120 }}
          />
        </Group>

        <Group gap={4}>
          <Tooltip label={isSelectionMode ? 'Exit selection' : 'Select multiple'}>
            <ActionIcon
              variant={isSelectionMode ? 'filled' : 'light'}
              color="blue"
              size="sm"
              onClick={() => setIsSelectionMode((v) => !v)}
            >
              <Checkbox size={10} checked={isSelectionMode} onChange={() => {}} style={{ pointerEvents: 'none' }} />
            </ActionIcon>
          </Tooltip>

          <ActionIcon variant="subtle" size="sm" onClick={() => loadAlerts()} loading={isLoading}>
            <IconRefresh size={14} />
          </ActionIcon>
        </Group>
      </Group>

      <Group gap="xs">
        <Button
          size="xs"
          variant={tab === 'all' ? 'filled' : 'light'}
          onClick={() => setTab('all')}
          style={tab === 'all' ? { backgroundColor: '#2563EB' } : undefined}
        >
          All ({filteredAlerts.length})
        </Button>
        <Button size="xs" variant={tab === 'active' ? 'filled' : 'light'} onClick={() => setTab('active')}>
          Active ({filteredAlerts.filter((a) => a.enabled).length})
        </Button>
        <Button size="xs" variant={tab === 'paused' ? 'filled' : 'light'} onClick={() => setTab('paused')}>
          Paused ({filteredAlerts.filter((a) => !a.enabled).length})
        </Button>
      </Group>

      {displayAlerts.length === 0 ? (
        <Center h={180}>
          <Stack align="center" gap="xs">
            <IconBell size={24} color="#94A3B8" />
            <Text size="sm" c="dimmed">
              No alerts found
            </Text>
            <Button size="xs" variant="light" onClick={createModalHandlers.open}>
              Create your first alert
            </Button>
          </Stack>
        </Center>
      ) : (
        <SimpleGrid cols={{ base: 2, sm: 3, lg: 4 }} spacing="xs">
          {displayAlerts.map((alert) => (
            <AlertCard
              key={alert.id}
              alert={alert}
              onToggle={handleToggleAlert}
              onEdit={handleEditAlert}
              onDelete={handleDeleteAlert}
              onDuplicate={handleDuplicateAlert}
              onClick={(a) => navigate(`/dashboard/alerts/${a.id}`)}
              selected={selectedAlerts.has(alert.id)}
              selectable={isSelectionMode}
              onSelect={() => toggleAlertSelection(alert.id)}
            />
          ))}
        </SimpleGrid>
      )}

      <Modal
        opened={createModalOpened}
        onClose={createModalHandlers.close}
        title={<Text fw={600} size="sm">Create New Alert</Text>}
        size="lg"
      >
        <CreateAlertOptimized
          initialTemplateRef={initialTemplateRef}
          onCancel={() => {
            setInitialTemplateRef(null)
            createModalHandlers.close()
          }}
          onAlertCreated={() => {
            setInitialTemplateRef(null)
            createModalHandlers.close()
            loadAlerts()
          }}
        />
      </Modal>

      <Modal opened={editOpened} onClose={editHandlers.close} title={<Text fw={600} size="sm">Edit Alert</Text>} size="lg">
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
            <Checkbox checked={editEnabled} onChange={(e) => setEditEnabled(e.currentTarget.checked)} />
          </Group>
          <Group justify="flex-end">
            <Button variant="subtle" onClick={editHandlers.close}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveEdit}
              style={{ backgroundColor: '#2563EB' }}
              disabled={!editingAlert}
            >
              Save
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}
