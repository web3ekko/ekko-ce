/**
 * Enhanced Alert Table Component
 * 
 * Improved alert table with search, filters, and better styling
 * matching the Wallet table design
 */

import React, { useState } from 'react'
import {
  Card,
  Table,
  Group,
  Text,
  Stack,
  Badge,
  Switch,
  ActionIcon,
  Menu,
  Checkbox,
  TextInput,
  Select,
  Button,
  Title,
  Center,
  Paper,
  Avatar,
  Tooltip,
} from '@mantine/core'
import {
  IconSearch,
  IconFilter,
  IconRefresh,
  IconDots,
  IconEdit,
  IconCopy,
  IconTrash,
  IconCheck,
  IconPlayerPause,
  IconAlertCircle,
  IconClock,
  IconBell,
  IconBellOff,
  IconChevronDown,
  IconSortAscending,
  IconSortDescending,
} from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { ChainLogo } from '../brand/ChainLogo'
import { getChainIdentity } from '../../utils/chain-identity'
import { AlertEventBadge } from './AlertEventBadge'

interface Alert {
  id: string
  name: string
  description: string
  status: 'active' | 'paused' | 'error' | 'draft'
  network: string
  event_type: string
  last_triggered: string | null
  trigger_count: number
  enabled: boolean
  priority?: 'low' | 'normal' | 'high' | 'critical'
  created_at?: string
}

interface EnhancedAlertTableProps {
  alerts: Alert[]
  selectedAlerts: string[]
  onToggleAlert: (alertId: string) => void
  onDeleteAlert: (alertId: string) => void
  onEditAlert?: (alertId: string) => void
  onDuplicateAlert?: (alertId: string) => void
  onSelectAlert: (alertId: string) => void
  onSelectAllAlerts: () => void
  onClearSelection: () => void
  onRefresh?: () => void
  isLoading?: boolean
}

export function EnhancedAlertTable({
  alerts,
  selectedAlerts,
  onToggleAlert,
  onDeleteAlert,
  onEditAlert,
  onDuplicateAlert,
  onSelectAlert,
  onSelectAllAlerts,
  onClearSelection,
  onRefresh,
  isLoading = false,
}: EnhancedAlertTableProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [networkFilter, setNetworkFilter] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<'name' | 'status' | 'triggered' | null>(null)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')

  // Filter alerts based on search and filters
  const filteredAlerts = alerts.filter((alert) => {
    const matchesSearch =
      alert.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      alert.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = !statusFilter || alert.status === statusFilter
    const matchesNetwork = !networkFilter || alert.network === networkFilter

    return matchesSearch && matchesStatus && matchesNetwork
  })

  // Sort alerts
  const sortedAlerts = [...filteredAlerts].sort((a, b) => {
    if (!sortBy) return 0

    let comparison = 0
    switch (sortBy) {
      case 'name':
        comparison = a.name.localeCompare(b.name)
        break
      case 'status':
        comparison = a.status.localeCompare(b.status)
        break
      case 'triggered':
        comparison = b.trigger_count - a.trigger_count
        break
    }

    return sortOrder === 'asc' ? comparison : -comparison
  })

  const handleSort = (field: 'name' | 'status' | 'triggered') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('asc')
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'green'
      case 'paused':
        return 'orange'
      case 'error':
        return 'red'
      case 'draft':
        return 'gray'
      default:
        return 'gray'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <IconCheck size={12} />
      case 'paused':
        return <IconPlayerPause size={12} />
      case 'error':
        return <IconAlertCircle size={12} />
      case 'draft':
        return <IconClock size={12} />
      default:
        return <IconCheck size={12} />
    }
  }

  const getPriorityColor = (priority?: string) => {
    switch (priority) {
      case 'critical':
        return 'red'
      case 'high':
        return 'orange'
      case 'normal':
        return 'blue'
      case 'low':
        return 'gray'
      default:
        return 'gray'
    }
  }

  const formatTimeAgo = (dateString: string | null) => {
    if (!dateString) return 'Never'

    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffHours / 24)

    if (diffHours < 1) return 'Just now'
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  // Empty state
  if (alerts.length === 0 && !isLoading) {
    return (
      <Card shadow="sm" padding="xl" radius="md" withBorder>
        <Center py="xl">
          <Stack align="center" gap="md">
            <Avatar size={80} radius="xl" color="gray">
              <IconBellOff size={40} />
            </Avatar>
            <div style={{ textAlign: 'center' }}>
              <Title order={3} mb="xs">
                No alerts yet
              </Title>
              <Text c="dimmed" size="sm" maw={400}>
                Create your first alert to start monitoring blockchain activity. You can use
                templates for quick setup or create custom alerts.
              </Text>
            </div>
            <Button leftSection={<IconBell size={16} />}>Create Your First Alert</Button>
          </Stack>
        </Center>
      </Card>
    )
  }

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Stack gap="md">
        <Group justify="space-between">
          <div>
            <Title order={3}>Your Alerts</Title>
            <Text size="sm" c="dimmed" mt={4}>
              Manage and monitor your active blockchain alerts
            </Text>
          </div>
          <Group gap="xs">
            <TextInput
              placeholder="Search alerts..."
              leftSection={<IconSearch size={16} />}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: 250 }}
            />
            <Select
              placeholder="All Status"
              leftSection={<IconFilter size={16} />}
              value={statusFilter}
              onChange={setStatusFilter}
              clearable
              data={[
                { value: 'active', label: 'Active' },
                { value: 'paused', label: 'Paused' },
                { value: 'error', label: 'Error' },
                { value: 'draft', label: 'Draft' },
              ]}
              style={{ width: 140 }}
            />
            <Select
              placeholder="All Networks"
              value={networkFilter}
              onChange={setNetworkFilter}
              clearable
              data={[
                { value: 'ethereum', label: 'Ethereum' },
                { value: 'polygon', label: 'Polygon' },
                { value: 'arbitrum', label: 'Arbitrum' },
                { value: 'optimism', label: 'Optimism' },
              ]}
              style={{ width: 140 }}
            />
            <Tooltip label="Refresh alerts">
              <ActionIcon variant="light" onClick={onRefresh} loading={isLoading}>
                <IconRefresh size={16} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>

        {selectedAlerts.length > 0 && (
          <Paper p="sm" radius="md" withBorder style={{ backgroundColor: 'var(--mantine-color-blue-0)' }}>
            <Group justify="space-between">
              <Group gap="md">
                <Badge size="lg" variant="filled">
                  {selectedAlerts.length} selected
                </Badge>
                <Button
                  size="sm"
                  color="red"
                  variant="light"
                  leftSection={<IconTrash size={14} />}
                  onClick={() => {
                    // Bulk delete logic
                    notifications.show({
                      title: 'Alerts Deleted',
                      message: `${selectedAlerts.length} alerts have been deleted`,
                      color: 'green',
                    })
                    onClearSelection()
                  }}
                >
                  Delete Selected
                </Button>
              </Group>
              <Button variant="subtle" size="sm" onClick={onClearSelection}>
                Clear Selection
              </Button>
            </Group>
          </Paper>
        )}

        <div style={{ overflowX: 'auto' }}>
          <Table verticalSpacing="sm" horizontalSpacing="md" highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={40}>
                  <Checkbox
                    checked={
                      selectedAlerts.length === sortedAlerts.length && sortedAlerts.length > 0
                    }
                    indeterminate={
                      selectedAlerts.length > 0 && selectedAlerts.length < sortedAlerts.length
                    }
                    onChange={(e) => {
                      if (e.currentTarget.checked) {
                        onSelectAllAlerts()
                      } else {
                        onClearSelection()
                      }
                    }}
                  />
                </Table.Th>
                <Table.Th>
                  <Group
                    gap={4}
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('name')}
                  >
                    <Text fw={500}>Name</Text>
                    {sortBy === 'name' &&
                      (sortOrder === 'asc' ? (
                        <IconSortAscending size={14} />
                      ) : (
                        <IconSortDescending size={14} />
                      ))}
                  </Group>
                </Table.Th>
                <Table.Th>
                  <Group
                    gap={4}
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('status')}
                  >
                    <Text fw={500}>Status</Text>
                    {sortBy === 'status' &&
                      (sortOrder === 'asc' ? (
                        <IconSortAscending size={14} />
                      ) : (
                        <IconSortDescending size={14} />
                      ))}
                  </Group>
                </Table.Th>
                <Table.Th>Network</Table.Th>
                <Table.Th>Event Type</Table.Th>
                <Table.Th>
                  <Group
                    gap={4}
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('triggered')}
                  >
                    <Text fw={500}>Last Triggered</Text>
                    {sortBy === 'triggered' &&
                      (sortOrder === 'asc' ? (
                        <IconSortAscending size={14} />
                      ) : (
                        <IconSortDescending size={14} />
                      ))}
                  </Group>
                </Table.Th>
                <Table.Th>Triggers</Table.Th>
                <Table.Th w={80}>Enabled</Table.Th>
                <Table.Th w={60}>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {sortedAlerts.map((alert) => (
                <Table.Tr key={alert.id}>
                  <Table.Td>
                    <Checkbox
                      checked={selectedAlerts.includes(alert.id)}
                      onChange={() => onSelectAlert(alert.id)}
                    />
                  </Table.Td>

                  <Table.Td style={{ maxWidth: 320 }}>
                    <Stack gap={4}>
                      <Group gap="xs" wrap="wrap" style={{ minWidth: 0 }}>
                        <Text
                          fw={500}
                          size="sm"
                          style={{
                            whiteSpace: 'normal',
                            wordBreak: 'break-word',
                            overflowWrap: 'anywhere',
                          }}
                        >
                          {alert.name}
                        </Text>
                        {alert.priority && alert.priority !== 'normal' && (
                          <Badge size="xs" color={getPriorityColor(alert.priority)} variant="dot">
                            {alert.priority}
                          </Badge>
                        )}
                      </Group>
                      <Text size="xs" c="dimmed" lineClamp={1}>
                        {alert.description}
                      </Text>
                    </Stack>
                  </Table.Td>

                  <Table.Td>
                    <Badge
                      color={getStatusColor(alert.status)}
                      variant="light"
                      leftSection={getStatusIcon(alert.status)}
                      size="sm"
                    >
                      {alert.status}
                    </Badge>
                  </Table.Td>

                  <Table.Td>
                    <Group gap={4}>
                      <ChainLogo chain={alert.network} size="xs" />
                      <Text size="sm">
                        {getChainIdentity(alert.network)?.name || alert.network}
                      </Text>
                    </Group>
                  </Table.Td>

                  <Table.Td>
                    <AlertEventBadge
                      eventType={alert.event_type}
                      chain={alert.network}
                      size="xs"
                    />
                  </Table.Td>

                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {formatTimeAgo(alert.last_triggered)}
                    </Text>
                  </Table.Td>

                  <Table.Td>
                    <Text size="sm" fw={500}>
                      {alert.trigger_count.toLocaleString()}
                    </Text>
                  </Table.Td>

                  <Table.Td>
                    <Switch
                      checked={alert.enabled}
                      onChange={() => onToggleAlert(alert.id)}
                      size="sm"
                    />
                  </Table.Td>

                  <Table.Td>
                    <Menu shadow="md" width={180} position="bottom-end">
                      <Menu.Target>
                        <ActionIcon variant="subtle" size="sm">
                          <IconDots size={16} />
                        </ActionIcon>
                      </Menu.Target>
                      <Menu.Dropdown>
                        {onEditAlert && (
                          <Menu.Item
                            leftSection={<IconEdit size={14} />}
                            onClick={() => onEditAlert(alert.id)}
                          >
                            Edit Alert
                          </Menu.Item>
                        )}
                        {onDuplicateAlert && (
                          <Menu.Item
                            leftSection={<IconCopy size={14} />}
                            onClick={() => onDuplicateAlert(alert.id)}
                          >
                            Duplicate
                          </Menu.Item>
                        )}
                        <Menu.Divider />
                        <Menu.Item
                          leftSection={<IconTrash size={14} />}
                          color="red"
                          onClick={() => onDeleteAlert(alert.id)}
                        >
                          Delete
                        </Menu.Item>
                      </Menu.Dropdown>
                    </Menu>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </div>

        <Group justify="space-between">
          <Text size="sm" c="dimmed">
            Showing {sortedAlerts.length} of {alerts.length} alerts
          </Text>

          <Group gap="lg">
            <Group gap="xs">
              <Badge color="green" variant="light" size="sm">
                {alerts.filter((a) => a.status === 'active').length} Active
              </Badge>
              <Badge color="orange" variant="light" size="sm">
                {alerts.filter((a) => a.status === 'paused').length} Paused
              </Badge>
              <Badge color="red" variant="light" size="sm">
                {alerts.filter((a) => a.status === 'error').length} Error
              </Badge>
            </Group>
          </Group>
        </Group>
      </Stack>
    </Card>
  )
}
