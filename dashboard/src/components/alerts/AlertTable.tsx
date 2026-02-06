/**
 * Alert Table Component
 * 
 * Data table for displaying alerts with sorting, selection, and actions
 */

import { useState } from 'react'
import {
  Table,
  Checkbox,
  Group,
  Text,
  Badge,
  ActionIcon,
  Menu,
  Switch,
  Tooltip,
  Card,
  Stack,
  Avatar,
  UnstyledButton,
} from '@mantine/core'
import { modals } from '@mantine/modals'
import {
  IconChevronUp,
  IconChevronDown,
  IconDots,
  IconEye,
  IconEdit,
  IconCopy,
  IconTrash,
  IconPlayerPlay,
  IconPlayerPause,
  IconClock,
  IconUser,
} from '@tabler/icons-react'
import { useAlertStore } from '../../store/alerts'
import type { Alert, AlertSortOptions } from '../../types/alerts'

interface AlertTableProps {
  alerts: Alert[]
  selectedAlerts: string[]
  sort: AlertSortOptions
  onSort: (sort: AlertSortOptions) => void
  onView: (alertId: string) => void
  onEdit: (alertId: string) => void
  onToggle: (alertId: string, enabled: boolean) => void
  onDuplicate: (alertId: string) => void
  onDelete: (alertId: string) => void
  getStatusColor: (status: Alert['status']) => string
  getStatusIcon: (status: Alert['status']) => React.ReactNode
}

export function AlertTable({
  alerts,
  selectedAlerts,
  sort,
  onSort,
  onView,
  onEdit,
  onToggle,
  onDuplicate,
  onDelete,
  getStatusColor,
  getStatusIcon,
}: AlertTableProps) {
  const { selectAlert, selectMultipleAlerts } = useAlertStore()

  const handleSort = (field: AlertSortOptions['field']) => {
    const direction = sort.field === field && sort.direction === 'asc' ? 'desc' : 'asc'
    onSort({ field, direction })
  }

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      selectMultipleAlerts(alerts.map(alert => alert.id))
    } else {
      selectMultipleAlerts([])
    }
  }

  const handleDeleteConfirm = (alert: Alert) => {
    modals.openConfirmModal({
      title: 'Delete Alert',
      children: (
        <Text size="sm">
          Are you sure you want to delete "{alert.name}"? This action cannot be undone.
        </Text>
      ),
      labels: { confirm: 'Delete', cancel: 'Cancel' },
      confirmProps: { color: 'red' },
      onConfirm: () => onDelete(alert.id),
    })
  }

  const SortableHeader = ({ 
    field, 
    children 
  }: { 
    field: AlertSortOptions['field']
    children: React.ReactNode 
  }) => (
    <UnstyledButton onClick={() => handleSort(field)}>
      <Group gap="xs" wrap="nowrap">
        <Text fw={500} size="sm">
          {children}
        </Text>
        {sort.field === field && (
          sort.direction === 'asc' ? 
            <IconChevronUp size="0.875rem" /> : 
            <IconChevronDown size="0.875rem" />
        )}
      </Group>
    </UnstyledButton>
  )

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / (1000 * 60))
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return formatDate(dateString)
  }

  const allSelected = alerts.length > 0 && selectedAlerts.length === alerts.length
  const someSelected = selectedAlerts.length > 0 && selectedAlerts.length < alerts.length

  return (
    <Card shadow="sm" padding={0} radius="md" withBorder>
      <Table.ScrollContainer minWidth={800}>
        <Table verticalSpacing="sm" horizontalSpacing="md">
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={40}>
                <Checkbox
                  checked={allSelected}
                  indeterminate={someSelected}
                  onChange={(e) => handleSelectAll(e.currentTarget.checked)}
                />
              </Table.Th>
              <Table.Th>
                <SortableHeader field="name">Name</SortableHeader>
              </Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Event Type</Table.Th>
              <Table.Th>
                <SortableHeader field="last_triggered">Last Triggered</SortableHeader>
              </Table.Th>
              <Table.Th>
                <SortableHeader field="trigger_count">Triggers</SortableHeader>
              </Table.Th>
              <Table.Th>
                <SortableHeader field="created_at">Created</SortableHeader>
              </Table.Th>
              <Table.Th>Author</Table.Th>
              <Table.Th w={60}>Enabled</Table.Th>
              <Table.Th w={60}>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {alerts.map((alert) => (
              <Table.Tr key={alert.id}>
                <Table.Td>
                  <Checkbox
                    checked={selectedAlerts.includes(alert.id)}
                    onChange={() => selectAlert(alert.id)}
                  />
                </Table.Td>
                
                <Table.Td>
                  <Stack gap="xs">
                    <Text 
                      fw={500} 
                      size="sm"
                      style={{ cursor: 'pointer' }}
                      onClick={() => onView(alert.id)}
                    >
                      {alert.name}
                    </Text>
                    {alert.description && (
                      <Text size="xs" c="dimmed" lineClamp={1}>
                        {alert.description}
                      </Text>
                    )}
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
                  <Badge variant="outline" size="sm">
                    {alert.spec.event_type.replace('_', ' ')}
                  </Badge>
                </Table.Td>
                
                <Table.Td>
                  {alert.last_triggered ? (
                    <Tooltip label={formatDate(alert.last_triggered)}>
                      <Text size="sm" c="dimmed">
                        {formatTimeAgo(alert.last_triggered)}
                      </Text>
                    </Tooltip>
                  ) : (
                    <Text size="sm" c="dimmed">
                      Never
                    </Text>
                  )}
                </Table.Td>
                
                <Table.Td>
                  <Text size="sm">
                    {alert.trigger_count.toLocaleString()}
                  </Text>
                </Table.Td>
                
                <Table.Td>
                  <Tooltip label={formatDate(alert.created_at)}>
                    <Text size="sm" c="dimmed">
                      {formatTimeAgo(alert.created_at)}
                    </Text>
                  </Tooltip>
                </Table.Td>
                
                <Table.Td>
                  <Group gap="xs">
                    <Avatar size="xs" radius="xl">
                      <IconUser size="0.75rem" />
                    </Avatar>
                    <Text size="sm" c="dimmed">
                      {alert.created_by}
                    </Text>
                  </Group>
                </Table.Td>
                
                <Table.Td>
                  <Switch
                    checked={alert.enabled}
                    onChange={(e) => onToggle(alert.id, e.currentTarget.checked)}
                    size="sm"
                  />
                </Table.Td>
                
                <Table.Td>
                  <Menu shadow="md" width={200}>
                    <Menu.Target>
                      <ActionIcon variant="subtle" size="sm">
                        <IconDots size="1rem" />
                      </ActionIcon>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item
                        leftSection={<IconEye size="1rem" />}
                        onClick={() => onView(alert.id)}
                      >
                        View Details
                      </Menu.Item>
                      <Menu.Item
                        leftSection={<IconEdit size="1rem" />}
                        onClick={() => onEdit(alert.id)}
                      >
                        Edit Alert
                      </Menu.Item>
                      <Menu.Item
                        leftSection={<IconCopy size="1rem" />}
                        onClick={() => onDuplicate(alert.id)}
                      >
                        Duplicate
                      </Menu.Item>
                      <Menu.Divider />
                      <Menu.Item
                        leftSection={alert.enabled ? <IconPlayerPause size="1rem" /> : <IconPlayerPlay size="1rem" />}
                        onClick={() => onToggle(alert.id, !alert.enabled)}
                      >
                        {alert.enabled ? 'Disable' : 'Enable'}
                      </Menu.Item>
                      <Menu.Divider />
                      <Menu.Item
                        leftSection={<IconTrash size="1rem" />}
                        color="red"
                        onClick={() => handleDeleteConfirm(alert)}
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
      </Table.ScrollContainer>
    </Card>
  )
}

export default AlertTable
