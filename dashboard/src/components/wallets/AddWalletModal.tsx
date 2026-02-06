/**
 * Add Wallet Modal Component
 *
 * Modal wrapper for the AddWalletForm
 */

import { useState } from 'react'
import { Modal, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconCheck, IconAlertCircle } from '@tabler/icons-react'
import { AddWalletForm } from './AddWalletForm'
import { useWalletStore } from '../../store/wallets'
import type { AccountsAddWalletRequest } from '../../services/groups-api'

interface AddWalletModalProps {
  opened: boolean
  onClose: () => void
  onWalletAdded?: () => void
}

export function AddWalletModal({ opened, onClose, onWalletAdded }: AddWalletModalProps) {
  const [isLoading, setIsLoading] = useState(false)
  const { addAccountWallet } = useWalletStore()

  const handleSubmit = async (data: AccountsAddWalletRequest) => {
    setIsLoading(true)

    try {
      await addAccountWallet(data)

      notifications.show({
        title: 'Wallet Added',
        message: 'Wallet added to Accounts',
        color: 'green',
        icon: <IconCheck size={16} />,
      })

      onWalletAdded?.()
      onClose()
    } catch (error) {
      notifications.show({
        title: 'Failed to Add Wallet',
        message: error instanceof Error ? error.message : 'An error occurred',
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
      title={<Text fw={600} size="sm">Add New Wallet</Text>}
      size="md"
    >
      <AddWalletForm
        onSubmit={handleSubmit}
        onCancel={onClose}
        isLoading={isLoading}
      />
    </Modal>
  )
}
