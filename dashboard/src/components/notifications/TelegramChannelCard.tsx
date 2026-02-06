import React, { useState } from 'react'
import {
  Card,
  Stack,
  Group,
  Text,
  Badge,
  Button,
  Switch,
  ActionIcon,
  Tooltip,
  Code,
  Alert,
  TextInput,
  Modal,
} from '@mantine/core'
import {
  IconBrandTelegram,
  IconTrash,
  IconSend,
  IconCheck,
  IconAlertCircle,
  IconCopy,
  IconQrcode,
} from '@tabler/icons-react'
import QRCode from 'qrcode'
import type { NotificationChannelEndpoint, DeliveryStatsResponse } from '../../services/notifications-api'

interface TelegramChannelCardProps {
  channel: NotificationChannelEndpoint
  onToggle: (channelId: string, enabled: boolean) => Promise<void>
  onDelete: (channelId: string) => Promise<void>
  onTest: (channelId: string) => Promise<void>
  onVerify?: (channelId: string, code: string) => Promise<void>
  stats?: DeliveryStatsResponse
}

interface TelegramChannelConfig {
  bot_token?: string
  chat_id?: string
  username?: string
}

export function TelegramChannelCard({
  channel,
  onToggle,
  onDelete,
  onTest,
  onVerify,
  stats,
}: TelegramChannelCardProps) {
  const [isToggling, setIsToggling] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [showVerifyModal, setShowVerifyModal] = useState(false)
  const [verificationCode, setVerificationCode] = useState('')
  const [isVerifying, setIsVerifying] = useState(false)
  const [showQRModal, setShowQRModal] = useState(false)
  const [qrCodeUrl, setQrCodeUrl] = useState<string>('')

  const config = channel.config as TelegramChannelConfig

  const handleToggle = async (checked: boolean) => {
    setIsToggling(true)
    try {
      await onToggle(channel.id, checked)
    } finally {
      setIsToggling(false)
    }
  }

  const handleDelete = async () => {
    if (window.confirm('Are you sure you want to delete this Telegram channel?')) {
      await onDelete(channel.id)
    }
  }

  const handleTest = async () => {
    setIsTesting(true)
    try {
      await onTest(channel.id)
    } finally {
      setIsTesting(false)
    }
  }

  const handleVerify = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      return
    }

    if (onVerify) {
      setIsVerifying(true)
      try {
        await onVerify(channel.id, verificationCode)
        setShowVerifyModal(false)
        setVerificationCode('')
      } finally {
        setIsVerifying(false)
      }
    }
  }

  const handleCopyChatId = () => {
    if (config.chat_id) {
      navigator.clipboard.writeText(config.chat_id)
    }
  }

  const handleShowQR = async () => {
    // Generate bot link
    const botUsername = config.bot_token?.split(':')[0] || 'ekko_alerts_bot'
    const botLink = `https://t.me/${botUsername}`

    try {
      const qrUrl = await QRCode.toDataURL(botLink, {
        width: 256,
        margin: 2,
        color: {
          dark: '#000000',
          light: '#FFFFFF',
        },
      })
      setQrCodeUrl(qrUrl)
      setShowQRModal(true)
    } catch (err) {
      console.error('Failed to generate QR code:', err)
    }
  }

  return (
    <>
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          {/* Header */}
          <Group justify="space-between">
            <Group gap="sm">
              <IconBrandTelegram size={24} color="#0088cc" />
              <div>
                <Text fw={500} size="sm">
                  {channel.label}
                </Text>
                <Text size="xs" c="dimmed">
                  {config.username ? `@${config.username}` : 'Telegram Bot'}
                </Text>
              </div>
            </Group>
            <Group gap="xs">
              <Badge color={channel.enabled ? 'green' : 'gray'}>
                {channel.enabled ? 'Active' : 'Disabled'}
              </Badge>
              {channel.verified ? (
                <Badge color="blue" leftSection={<IconCheck size={12} />}>
                  Verified
                </Badge>
              ) : (
                <Badge color="yellow">Pending Verification</Badge>
              )}
            </Group>
          </Group>

          {/* Chat ID Display */}
          {config.chat_id && (
            <Group gap="xs">
              <Text size="xs" c="dimmed">
                Chat ID:
              </Text>
              <Code>{config.chat_id}</Code>
              <Tooltip label="Copy Chat ID">
                <ActionIcon size="sm" variant="subtle" onClick={handleCopyChatId}>
                  <IconCopy size={14} />
                </ActionIcon>
              </Tooltip>
            </Group>
          )}

          {/* Verification Alert */}
          {!channel.verified && (
            <Alert
              icon={<IconAlertCircle size={16} />}
              title="Verification Required"
              color="yellow"
            >
              <Stack gap="xs">
                <Text size="xs">
                  Please verify this Telegram channel by sending <Code>/subscribe</Code> to the bot and
                  entering the verification code.
                </Text>
                <Group gap="xs">
                  <Button
                    size="xs"
                    variant="light"
                    onClick={() => setShowVerifyModal(true)}
                  >
                    Enter Verification Code
                  </Button>
                  <Button
                    size="xs"
                    variant="light"
                    leftSection={<IconQrcode size={14} />}
                    onClick={handleShowQR}
                  >
                    Show QR Code
                  </Button>
                </Group>
              </Stack>
            </Alert>
          )}

          {/* Stats */}
          {stats && (
            <Card withBorder padding="sm" radius="sm" bg="gray.0">
              <Group justify="space-around">
                <div>
                  <Text size="xs" c="dimmed" ta="center">
                    Delivered
                  </Text>
                  <Text size="lg" fw={700} c="green" ta="center">
                    {stats.success_count}
                  </Text>
                </div>
                <div>
                  <Text size="xs" c="dimmed" ta="center">
                    Failed
                  </Text>
                  <Text size="lg" fw={700} c="red" ta="center">
                    {stats.failure_count}
                  </Text>
                </div>
                {stats.total_count > 0 && (
                  <div>
                    <Text size="xs" c="dimmed" ta="center">
                      Success Rate
                    </Text>
                    <Text size="lg" fw={700} c="blue" ta="center">
                      {stats.success_rate.toFixed(1)}%
                    </Text>
                  </div>
                )}
              </Group>
            </Card>
          )}

          {/* Actions */}
          <Group justify="space-between">
            <Group gap="xs">
              <Switch
                checked={channel.enabled}
                onChange={(e) => handleToggle(e.currentTarget.checked)}
                disabled={isToggling || !channel.verified}
                label={channel.enabled ? 'Enabled' : 'Disabled'}
              />
            </Group>
            <Group gap="xs">
              <Button
                size="sm"
                variant="light"
                leftSection={<IconSend size={16} />}
                onClick={handleTest}
                loading={isTesting}
                disabled={!channel.enabled || !channel.verified}
              >
                Test
              </Button>
              <Tooltip label="Delete channel">
                <ActionIcon
                  color="red"
                  variant="subtle"
                  size="lg"
                  onClick={handleDelete}
                >
                  <IconTrash size={18} />
                </ActionIcon>
              </Tooltip>
            </Group>
          </Group>
        </Stack>
      </Card>

      {/* Verification Code Modal */}
      <Modal
        opened={showVerifyModal}
        onClose={() => {
          setShowVerifyModal(false)
          setVerificationCode('')
        }}
        title="Enter Verification Code"
        size="sm"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Enter the 6-digit verification code sent to your Telegram chat.
          </Text>
          <TextInput
            placeholder="000000"
            maxLength={6}
            value={verificationCode}
            onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ''))}
            autoFocus
          />
          <Group justify="flex-end">
            <Button variant="subtle" onClick={() => setShowVerifyModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleVerify}
              loading={isVerifying}
              disabled={verificationCode.length !== 6}
            >
              Verify
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* QR Code Modal */}
      <Modal
        opened={showQRModal}
        onClose={() => setShowQRModal(false)}
        title="Scan QR Code with Telegram"
        size="sm"
        centered
      >
        <Stack gap="md" align="center">
          <Text size="sm" c="dimmed" ta="center">
            Scan this QR code with your Telegram app to open the bot
          </Text>
          {qrCodeUrl && (
            <img src={qrCodeUrl} alt="Telegram Bot QR Code" style={{ maxWidth: '100%' }} />
          )}
          <Text size="xs" c="dimmed" ta="center">
            After opening the bot, send <Code>/subscribe</Code> to get your verification code
          </Text>
        </Stack>
      </Modal>
    </>
  )
}
