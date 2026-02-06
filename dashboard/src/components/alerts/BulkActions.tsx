/**
 * Bulk Actions Component
 * 
 * Bulk operations for selected alerts
 */

import { useState } from 'react'
import {
  Group,
  Button,
  Menu,
  Text,
  Badge,
  ActionIcon,
  Modal,
  Stack,
  Select,
  Textarea,
  Alert,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { modals } from '@mantine/modals'
import { notifications } from '@mantine/notifications'
import {
  IconX,
  IconChevronDown,
  IconPlayerPlay,
  IconPlayerPause,
  IconTrash,
  IconCopy,
  IconEdit,
  IconDownload,
  IconAlertCircle,
  IconCheck,
} from '@tabler/icons-react'
import { useAlertStore } from '../../store/alerts'

interface BulkActionsProps {
  selectedCount: number
  onClearSelection: () => void
}

export function BulkActions({ selectedCount, onClearSelection }: BulkActionsProps) {
  const [editModalOpened, { open: openEditModal, close: closeEditModal }] = useDisclosure(false)
  const [isLoading, setIsLoading] = useState(false)
  const [editField, setEditField] = useState<string>('')
  const [editValue, setEditValue] = useState<string>('')

  const { 
    selectedAlerts, 
    bulkUpdateAlerts, 
    bulkDeleteAlerts,
    alerts 
  } = useAlertStore()

  const handleBulkEnable = async () => {
    setIsLoading(true)
    try {
      const success = await bulkUpdateAlerts({ enabled: true })
      if (success) {
        notifications.show({
          title: 'Alerts enabled',
          message: `${selectedCount} alerts have been enabled`,
          color: 'green',
          icon: <IconPlayerPlay size="1rem" />,
        })
        onClearSelection()
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleBulkDisable = async () => {
    setIsLoading(true)
    try {
      const success = await bulkUpdateAlerts({ enabled: false })
      if (success) {
        notifications.show({
          title: 'Alerts disabled',
          message: `${selectedCount} alerts have been disabled`,
          color: 'orange',
          icon: <IconPlayerPause size="1rem" />,
        })
        onClearSelection()
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleBulkDelete = () => {
    modals.openConfirmModal({
      title: 'Delete Selected Alerts',
      children: (
        <Stack gap="md">
          <Text size="sm">
            Are you sure you want to delete {selectedCount} selected alerts? 
            This action cannot be undone.
          </Text>
          <Alert color="red" icon={<IconAlertCircle size="1rem" />}>
            <Text size="sm">
              This will permanently delete all selected alerts and their execution history.
            </Text>
          </Alert>
        </Stack>
      ),
      labels: { confirm: 'Delete', cancel: 'Cancel' },
      confirmProps: { color: 'red' },
      onConfirm: async () => {
        setIsLoading(true)
        try {
          const success = await bulkDeleteAlerts()
          if (success) {
            notifications.show({
              title: 'Alerts deleted',
              message: `${selectedCount} alerts have been deleted`,
              color: 'green',
              icon: <IconTrash size="1rem" />,
            })
            onClearSelection()
          }
        } finally {
          setIsLoading(false)
        }
      },
    })
  }

  const handleBulkEdit = () => {
    setEditField('')
    setEditValue('')
    openEditModal()
  }

  const handleEditSubmit = async () => {
    if (!editField || !editValue) return

    setIsLoading(true)
    try {
      const updates: any = {}
      
      if (editField === 'description') {
        updates.description = editValue
      }
      // Add more fields as needed

      const success = await bulkUpdateAlerts(updates)
      if (success) {
        notifications.show({
          title: 'Alerts updated',
          message: `${selectedCount} alerts have been updated`,
          color: 'green',
          icon: <IconCheck size="1rem" />,
        })
        onClearSelection()
        closeEditModal()
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleBulkExport = () => {
    // This would trigger the export functionality
    notifications.show({
      title: 'Export started',
      message: `Exporting ${selectedCount} selected alerts`,
      color: 'blue',
      icon: <IconDownload size="1rem" />,
    })
  }

  const getSelectedAlertNames = () => {
    return selectedAlerts
      .map(id => alerts.find(alert => alert.id === id)?.name)
      .filter(Boolean)
      .slice(0, 3) // Show first 3 names
  }

  return (
    <>
      <Group
        justify="space-between"
        p="md"
        style={{
          backgroundColor: 'var(--mantine-color-blue-0)',
          border: '1px solid var(--mantine-color-blue-3)',
          borderRadius: 'var(--mantine-radius-md)',
        }}
      >
        <Group gap="md">
          <Badge size="lg" variant="filled">
            {selectedCount} selected
          </Badge>
          
          <Text size="sm" c="dimmed">
            {getSelectedAlertNames().join(', ')}
            {selectedCount > 3 && ` and ${selectedCount - 3} more`}
          </Text>
        </Group>

        <Group gap="sm">
          <Button
            variant="light"
            size="sm"
            leftSection={<IconPlayerPlay size="1rem" />}
            onClick={handleBulkEnable}
            loading={isLoading}
          >
            Enable
          </Button>

          <Button
            variant="light"
            size="sm"
            leftSection={<IconPlayerPause size="1rem" />}
            onClick={handleBulkDisable}
            loading={isLoading}
          >
            Disable
          </Button>

          <Menu shadow="md" width={200}>
            <Menu.Target>
              <Button
                variant="light"
                size="sm"
                rightSection={<IconChevronDown size="1rem" />}
              >
                More Actions
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<IconEdit size="1rem" />}
                onClick={handleBulkEdit}
              >
                Edit Selected
              </Menu.Item>
              <Menu.Item
                leftSection={<IconDownload size="1rem" />}
                onClick={handleBulkExport}
              >
                Export Selected
              </Menu.Item>
              <Menu.Divider />
              <Menu.Item
                leftSection={<IconTrash size="1rem" />}
                color="red"
                onClick={handleBulkDelete}
              >
                Delete Selected
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>

          <ActionIcon
            variant="subtle"
            size="sm"
            onClick={onClearSelection}
          >
            <IconX size="1rem" />
          </ActionIcon>
        </Group>
      </Group>

      {/* Bulk Edit Modal */}
      <Modal
        opened={editModalOpened}
        onClose={closeEditModal}
        title="Edit Selected Alerts"
        size="md"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Edit {selectedCount} selected alerts
          </Text>

          <Select
            label="Field to Edit"
            placeholder="Select field"
            value={editField}
            onChange={(value) => setEditField(value || '')}
            data={[
              { value: 'description', label: 'Description' },
              // Add more editable fields as needed
            ]}
          />

          {editField === 'description' && (
            <Textarea
              label="New Description"
              placeholder="Enter new description"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              rows={3}
            />
          )}

          <Group justify="flex-end" gap="sm">
            <Button
              variant="subtle"
              onClick={closeEditModal}
            >
              Cancel
            </Button>
            <Button
              onClick={handleEditSubmit}
              loading={isLoading}
              disabled={!editField || !editValue}
            >
              Update Alerts
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}

export default BulkActions
