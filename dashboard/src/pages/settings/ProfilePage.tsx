/**
 * Profile Settings Page
 *
 * User profile management including personal info, preferences,
 * connected services, and data/privacy controls
 */

import { useState, useEffect } from 'react'
import {
  Container,
  Title,
  Stack,
  Card,
  Text,
  Group,
  Button,
  Avatar,
  Badge,
  TextInput,
  Textarea,
  Select,
  Switch,
  Divider,
  Grid,
  Modal,
  Alert,
  ActionIcon,
  Paper,
  Tooltip,
  LoadingOverlay,
  Tabs,
  ThemeIcon,
  FileButton,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import {
  IconUser,
  IconMail,
  IconCamera,
  IconEdit,
  IconCheck,
  IconX,
  IconBell,
  IconDevices,
  IconTrash,
  IconDownload,
  IconAlertTriangle,
  IconBrandSlack,
  IconBrandTelegram,
  IconWebhook,
  IconShield,
  IconChevronRight,
  IconGlobe,
  IconClock,
} from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/auth'
import {
  usersApiService,
  type UserProfile,
  type UserPreferences,
  type ConnectedService,
  type ActiveSession,
} from '../../services/users-api'

export function ProfilePage() {
  const navigate = useNavigate()
  const { user, isLoading: authLoading } = useAuthStore()

  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [preferences, setPreferences] = useState<UserPreferences | null>(null)
  const [connectedServices, setConnectedServices] = useState<ConnectedService[]>([])
  const [sessions, setSessions] = useState<ActiveSession[]>([])
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')

  const profileForm = useForm({
    initialValues: {
      name: '',
      display_name: '',
      bio: '',
      timezone: 'America/New_York',
      language: 'en',
    },
    validate: {
      name: (value) => (value.length < 1 ? 'Name is required' : null),
    },
  })

  const notificationForm = useForm({
    initialValues: {
      email_alerts: true,
      push_notifications: true,
      alert_digest: 'instant' as const,
      marketing_emails: false,
      security_alerts: true,
    },
  })

  // Load profile data on mount
  useEffect(() => {
    loadProfileData()
  }, [])

  const loadProfileData = async () => {
    setIsLoading(true)
    try {
      const [profileData, preferencesData, servicesData, sessionsData] = await Promise.all([
        usersApiService.getProfile(),
        usersApiService.getPreferences(),
        usersApiService.getConnectedServices(),
        usersApiService.getActiveSessions(),
      ])

      setProfile(profileData)
      setPreferences(preferencesData)
      setConnectedServices(servicesData)
      setSessions(sessionsData)

      // Initialize form values
      profileForm.setValues({
        name: profileData.name || '',
        display_name: profileData.display_name || '',
        bio: profileData.bio || '',
        timezone: profileData.timezone || 'America/New_York',
        language: profileData.language || 'en',
      })

      notificationForm.setValues({
        email_alerts: preferencesData.notification_preferences.email_alerts,
        push_notifications: preferencesData.notification_preferences.push_notifications,
        alert_digest: preferencesData.notification_preferences.alert_digest,
        marketing_emails: preferencesData.notification_preferences.marketing_emails,
        security_alerts: preferencesData.notification_preferences.security_alerts,
      })
    } catch (error: any) {
      console.error('Failed to load profile:', error)
      notifications.show({
        title: 'Error',
        message: 'Failed to load profile data',
        color: 'red',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleSaveProfile = async (values: typeof profileForm.values) => {
    setIsSaving(true)
    try {
      await usersApiService.updateProfile({
        name: values.name,
        display_name: values.display_name,
        bio: values.bio,
        timezone: values.timezone,
        language: values.language,
      })

      setProfile((prev) =>
        prev
          ? {
              ...prev,
              name: values.name,
              display_name: values.display_name,
              bio: values.bio,
              timezone: values.timezone,
              language: values.language,
            }
          : null
      )

      setIsEditing(false)
      notifications.show({
        title: 'Profile Updated',
        message: 'Your profile has been saved successfully',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
    } catch (error: any) {
      console.error('Failed to save profile:', error)
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to save profile',
        color: 'red',
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleSaveNotifications = async () => {
    setIsSaving(true)
    try {
      await usersApiService.updatePreferences({
        notification_preferences: notificationForm.values,
      })

      notifications.show({
        title: 'Preferences Updated',
        message: 'Notification settings saved',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
    } catch (error: any) {
      console.error('Failed to save preferences:', error)
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to save preferences',
        color: 'red',
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleAvatarUpload = async (file: File | null) => {
    if (!file) return

    // Validate file
    if (!file.type.startsWith('image/')) {
      notifications.show({
        title: 'Invalid File',
        message: 'Please select an image file',
        color: 'red',
      })
      return
    }

    if (file.size > 5 * 1024 * 1024) {
      notifications.show({
        title: 'File Too Large',
        message: 'Image must be less than 5MB',
        color: 'red',
      })
      return
    }

    try {
      const result = await usersApiService.uploadAvatar(file)
      setProfile((prev) => (prev ? { ...prev, avatar_url: result.avatar_url } : null))
      notifications.show({
        title: 'Avatar Updated',
        message: 'Your avatar has been uploaded',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
    } catch (error: any) {
      console.error('Failed to upload avatar:', error)
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to upload avatar',
        color: 'red',
      })
    }
  }

  const handleExportData = async () => {
    try {
      notifications.show({
        title: 'Export Started',
        message: 'Your data export is being prepared. You will receive an email when ready.',
        color: 'blue',
      })
      await usersApiService.requestDataExport()
    } catch (error: any) {
      console.error('Failed to request export:', error)
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to request data export',
        color: 'red',
      })
    }
  }

  const handleDeleteAccount = async () => {
    if (deleteConfirmation.toLowerCase() !== 'delete my account') {
      notifications.show({
        title: 'Confirmation Required',
        message: 'Please type "delete my account" to confirm',
        color: 'red',
      })
      return
    }

    try {
      await usersApiService.deleteAccount(deleteConfirmation)
      notifications.show({
        title: 'Account Deleted',
        message: 'Your account has been scheduled for deletion',
        color: 'blue',
      })
      // Redirect to login or home
      navigate('/auth/login')
    } catch (error: any) {
      console.error('Failed to delete account:', error)
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to delete account',
        color: 'red',
      })
    }
  }

  const handleRevokeSession = async (sessionId: string) => {
    try {
      await usersApiService.revokeSession(sessionId)
      setSessions((prev) => prev.filter((s) => s.id !== sessionId))
      notifications.show({
        title: 'Session Revoked',
        message: 'The session has been logged out',
        color: 'blue',
      })
    } catch (error: any) {
      console.error('Failed to revoke session:', error)
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to revoke session',
        color: 'red',
      })
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  const formatRelativeTime = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return `${diffDays}d ago`
  }

  const getServiceIcon = (type: string) => {
    switch (type) {
      case 'slack':
        return <IconBrandSlack size={16} />
      case 'telegram':
        return <IconBrandTelegram size={16} />
      default:
        return <IconWebhook size={16} />
    }
  }

  return (
    <Container size="lg" py="xl">
      <LoadingOverlay visible={isLoading || authLoading} />

      <Stack gap="xl">
        {/* Header */}
        <div>
          <Title order={2} c="#0F172A">
            Profile Settings
          </Title>
          <Text c="#64748B" mt="xs">
            Manage your personal information and preferences
          </Text>
        </div>

        <Tabs defaultValue="profile">
          <Tabs.List>
            <Tabs.Tab value="profile" leftSection={<IconUser size={16} />}>
              Profile
            </Tabs.Tab>
            <Tabs.Tab value="notifications" leftSection={<IconBell size={16} />}>
              Notifications
            </Tabs.Tab>
            <Tabs.Tab value="sessions" leftSection={<IconDevices size={16} />}>
              Sessions
            </Tabs.Tab>
            <Tabs.Tab value="privacy" leftSection={<IconShield size={16} />}>
              Privacy
            </Tabs.Tab>
          </Tabs.List>

          {/* Profile Tab */}
          <Tabs.Panel value="profile" pt="xl">
            <Grid gutter="lg">
              <Grid.Col span={{ base: 12, md: 8 }}>
                <Card withBorder p="lg">
                  <Group justify="space-between" mb="lg">
                    <Text fw={600} c="#0F172A">
                      Personal Information
                    </Text>
                    {!isEditing && (
                      <Button
                        variant="light"
                        size="xs"
                        leftSection={<IconEdit size={14} />}
                        onClick={() => setIsEditing(true)}
                      >
                        Edit
                      </Button>
                    )}
                  </Group>

                  <form onSubmit={profileForm.onSubmit(handleSaveProfile)}>
                    <Stack gap="md">
                      {/* Avatar Section */}
                      <Group gap="lg">
                        <div style={{ position: 'relative' }}>
                          <Avatar
                            size={80}
                            radius="xl"
                            src={profile?.avatar_url}
                            color="blue"
                            style={{ border: '3px solid #F1F5F9' }}
                          >
                            {profile?.name?.[0]?.toUpperCase() || 'U'}
                          </Avatar>
                          {isEditing && (
                            <FileButton onChange={handleAvatarUpload} accept="image/*">
                              {(props) => (
                                <ActionIcon
                                  {...props}
                                  size="sm"
                                  radius="xl"
                                  variant="filled"
                                  color="blue"
                                  style={{
                                    position: 'absolute',
                                    bottom: 0,
                                    right: 0,
                                    border: '2px solid white',
                                  }}
                                >
                                  <IconCamera size={12} />
                                </ActionIcon>
                              )}
                            </FileButton>
                          )}
                        </div>
                        <div>
                          <Text fw={600} c="#0F172A">
                            {profile?.name || 'User'}
                          </Text>
                          <Text size="sm" c="#64748B">
                            {profile?.email}
                          </Text>
                          <Badge size="xs" variant="light" color="blue" mt={4}>
                            {profile?.role || 'User'}
                          </Badge>
                        </div>
                      </Group>

                      <Divider my="md" />

                      {/* Form Fields */}
                      <TextInput
                        label="Full Name"
                        placeholder="Your full name"
                        disabled={!isEditing}
                        {...profileForm.getInputProps('name')}
                      />

                      <TextInput
                        label="Display Name"
                        placeholder="How others see you"
                        description="This is shown publicly"
                        disabled={!isEditing}
                        {...profileForm.getInputProps('display_name')}
                      />

                      <TextInput
                        label="Email"
                        value={profile?.email || ''}
                        disabled
                        leftSection={<IconMail size={16} />}
                        description="Contact support to change your email"
                      />

                      <Textarea
                        label="Bio"
                        placeholder="Tell us about yourself"
                        minRows={3}
                        disabled={!isEditing}
                        {...profileForm.getInputProps('bio')}
                      />

                      <Grid>
                        <Grid.Col span={6}>
                          <Select
                            label="Timezone"
                            leftSection={<IconClock size={16} />}
                            disabled={!isEditing}
                            data={[
                              { value: 'America/New_York', label: 'Eastern (ET)' },
                              { value: 'America/Chicago', label: 'Central (CT)' },
                              { value: 'America/Denver', label: 'Mountain (MT)' },
                              { value: 'America/Los_Angeles', label: 'Pacific (PT)' },
                              { value: 'Europe/London', label: 'London (GMT)' },
                              { value: 'Europe/Paris', label: 'Paris (CET)' },
                              { value: 'Asia/Tokyo', label: 'Tokyo (JST)' },
                              { value: 'Asia/Shanghai', label: 'Shanghai (CST)' },
                            ]}
                            {...profileForm.getInputProps('timezone')}
                          />
                        </Grid.Col>
                        <Grid.Col span={6}>
                          <Select
                            label="Language"
                            leftSection={<IconGlobe size={16} />}
                            disabled={!isEditing}
                            data={[
                              { value: 'en', label: 'English' },
                              { value: 'es', label: 'Spanish' },
                              { value: 'fr', label: 'French' },
                              { value: 'de', label: 'German' },
                              { value: 'ja', label: 'Japanese' },
                              { value: 'zh', label: 'Chinese' },
                            ]}
                            {...profileForm.getInputProps('language')}
                          />
                        </Grid.Col>
                      </Grid>

                      {isEditing && (
                        <Group justify="flex-end" mt="md">
                          <Button
                            variant="subtle"
                            onClick={() => {
                              setIsEditing(false)
                              profileForm.reset()
                            }}
                          >
                            Cancel
                          </Button>
                          <Button type="submit" loading={isSaving}>
                            Save Changes
                          </Button>
                        </Group>
                      )}
                    </Stack>
                  </form>
                </Card>
              </Grid.Col>

              <Grid.Col span={{ base: 12, md: 4 }}>
                <Stack gap="md">
                  {/* Security Status Card */}
                  <Card withBorder p="md">
                    <Group justify="space-between" mb="sm">
                      <Text fw={600} size="sm" c="#0F172A">
                        Security
                      </Text>
                      <ActionIcon
                        variant="subtle"
                        onClick={() => navigate('/dashboard/settings/security')}
                      >
                        <IconChevronRight size={16} />
                      </ActionIcon>
                    </Group>

                    <Stack gap="xs">
                      <Group justify="space-between">
                        <Text size="sm" c="#64748B">
                          2FA
                        </Text>
                        <Badge
                          size="xs"
                          color={profile?.two_factor_enabled ? 'green' : 'gray'}
                          variant="light"
                        >
                          {profile?.two_factor_enabled ? 'Enabled' : 'Not Set'}
                        </Badge>
                      </Group>
                    </Stack>

                    <Button
                      variant="light"
                      fullWidth
                      mt="md"
                      size="xs"
                      onClick={() => navigate('/dashboard/settings/security')}
                    >
                      Manage Security
                    </Button>
                  </Card>

                  {/* Connected Services Card */}
                  <Card withBorder p="md">
                    <Text fw={600} size="sm" c="#0F172A" mb="sm">
                      Connected Services
                    </Text>

                    {connectedServices.length === 0 ? (
                      <Text size="sm" c="#64748B" ta="center" py="md">
                        No services connected
                      </Text>
                    ) : (
                      <Stack gap="xs">
                        {connectedServices.map((service) => (
                          <Paper key={service.id} p="xs" withBorder>
                            <Group justify="space-between">
                              <Group gap="xs">
                                <ThemeIcon
                                  size="sm"
                                  variant="light"
                                  color={service.is_active ? 'green' : 'gray'}
                                >
                                  {getServiceIcon(service.service_type)}
                                </ThemeIcon>
                                <div>
                                  <Text size="xs" fw={500} tt="capitalize">
                                    {service.service_type}
                                  </Text>
                                  <Text size="xs" c="#64748B">
                                    {service.account_name}
                                  </Text>
                                </div>
                              </Group>
                              <Badge
                                size="xs"
                                color={service.is_active ? 'green' : 'gray'}
                                variant="dot"
                              >
                                {service.is_active ? 'Active' : 'Inactive'}
                              </Badge>
                            </Group>
                          </Paper>
                        ))}
                      </Stack>
                    )}

                    <Button
                      variant="light"
                      fullWidth
                      mt="md"
                      size="xs"
                      onClick={() => navigate('/dashboard/settings/notifications')}
                    >
                      Manage Channels
                    </Button>
                  </Card>

                  {/* Account Info Card */}
                  <Card withBorder p="md">
                    <Text fw={600} size="sm" c="#0F172A" mb="sm">
                      Account Info
                    </Text>
                    <Stack gap="xs">
                      <Group justify="space-between">
                        <Text size="sm" c="#64748B">
                          Member since
                        </Text>
                        <Text size="sm" fw={500}>
                          {profile?.created_at ? formatDate(profile.created_at) : '-'}
                        </Text>
                      </Group>
                      <Group justify="space-between">
                        <Text size="sm" c="#64748B">
                          Last login
                        </Text>
                        <Text size="sm" fw={500}>
                          {profile?.last_login ? formatRelativeTime(profile.last_login) : '-'}
                        </Text>
                      </Group>
                      <Group justify="space-between">
                        <Text size="sm" c="#64748B">
                          Status
                        </Text>
                        <Badge size="xs" color="green" variant="dot">
                          Active
                        </Badge>
                      </Group>
                    </Stack>
                  </Card>
                </Stack>
              </Grid.Col>
            </Grid>
          </Tabs.Panel>

          {/* Notifications Tab */}
          <Tabs.Panel value="notifications" pt="xl">
            <Card withBorder p="lg" maw={600}>
              <Text fw={600} c="#0F172A" mb="lg">
                Notification Preferences
              </Text>

              <Stack gap="lg">
                <Group justify="space-between">
                  <div>
                    <Text fw={500} c="#0F172A">
                      Email Alerts
                    </Text>
                    <Text size="sm" c="#64748B">
                      Receive alert notifications via email
                    </Text>
                  </div>
                  <Switch
                    size="md"
                    color="blue"
                    {...notificationForm.getInputProps('email_alerts', { type: 'checkbox' })}
                  />
                </Group>

                <Divider />

                <Group justify="space-between">
                  <div>
                    <Text fw={500} c="#0F172A">
                      Push Notifications
                    </Text>
                    <Text size="sm" c="#64748B">
                      Browser notifications for important alerts
                    </Text>
                  </div>
                  <Switch
                    size="md"
                    color="blue"
                    {...notificationForm.getInputProps('push_notifications', { type: 'checkbox' })}
                  />
                </Group>

                <Divider />

                <Group justify="space-between" align="flex-start">
                  <div>
                    <Text fw={500} c="#0F172A">
                      Alert Digest
                    </Text>
                    <Text size="sm" c="#64748B">
                      How often to receive alert summaries
                    </Text>
                  </div>
                  <Select
                    w={180}
                    size="sm"
                    data={[
                      { value: 'instant', label: 'Instant' },
                      { value: 'daily', label: 'Daily' },
                      { value: 'weekly', label: 'Weekly' },
                      { value: 'none', label: 'Never' },
                    ]}
                    {...notificationForm.getInputProps('alert_digest')}
                  />
                </Group>

                <Divider />

                <Group justify="space-between">
                  <div>
                    <Text fw={500} c="#0F172A">
                      Security Alerts
                    </Text>
                    <Text size="sm" c="#64748B">
                      Important security notifications
                    </Text>
                  </div>
                  <Switch
                    size="md"
                    color="blue"
                    {...notificationForm.getInputProps('security_alerts', { type: 'checkbox' })}
                  />
                </Group>

                <Divider />

                <Group justify="space-between">
                  <div>
                    <Text fw={500} c="#0F172A">
                      Marketing Emails
                    </Text>
                    <Text size="sm" c="#64748B">
                      Product updates and announcements
                    </Text>
                  </div>
                  <Switch
                    size="md"
                    color="blue"
                    {...notificationForm.getInputProps('marketing_emails', { type: 'checkbox' })}
                  />
                </Group>

                <Button onClick={handleSaveNotifications} loading={isSaving} mt="md">
                  Save Preferences
                </Button>
              </Stack>
            </Card>
          </Tabs.Panel>

          {/* Sessions Tab */}
          <Tabs.Panel value="sessions" pt="xl">
            <Card withBorder p="lg">
              <Group justify="space-between" mb="lg">
                <div>
                  <Text fw={600} c="#0F172A">
                    Active Sessions
                  </Text>
                  <Text size="sm" c="#64748B">
                    Devices where you're currently logged in
                  </Text>
                </div>
                <Button
                  variant="light"
                  color="red"
                  size="xs"
                  onClick={() => usersApiService.revokeAllOtherSessions()}
                >
                  Sign Out All Others
                </Button>
              </Group>

              <Stack gap="md">
                {sessions.map((session) => (
                  <Paper key={session.id} p="md" withBorder>
                    <Group justify="space-between">
                      <Group gap="md">
                        <ThemeIcon
                          size="lg"
                          variant="light"
                          color={session.is_current ? 'blue' : 'gray'}
                        >
                          <IconDevices size={20} />
                        </ThemeIcon>
                        <div>
                          <Group gap="xs">
                            <Text fw={500} c="#0F172A">
                              {session.device_name}
                            </Text>
                            {session.is_current && (
                              <Badge size="xs" color="blue" variant="light">
                                Current
                              </Badge>
                            )}
                          </Group>
                          <Text size="sm" c="#64748B">
                            {session.location} • {session.ip_address}
                          </Text>
                          <Text size="xs" c="#94A3B8">
                            Last active: {formatRelativeTime(session.last_active)}
                          </Text>
                        </div>
                      </Group>
                      {!session.is_current && (
                        <Tooltip label="Sign out this device">
                          <ActionIcon
                            variant="subtle"
                            color="red"
                            onClick={() => handleRevokeSession(session.id)}
                          >
                            <IconX size={16} />
                          </ActionIcon>
                        </Tooltip>
                      )}
                    </Group>
                  </Paper>
                ))}
              </Stack>
            </Card>
          </Tabs.Panel>

          {/* Privacy Tab */}
          <Tabs.Panel value="privacy" pt="xl">
            <Stack gap="lg" maw={600}>
              {/* Export Data */}
              <Card withBorder p="lg">
                <Group justify="space-between">
                  <div>
                    <Text fw={600} c="#0F172A">
                      Export Your Data
                    </Text>
                    <Text size="sm" c="#64748B" mt="xs">
                      Download a copy of all your data including alerts, wallets, and settings
                    </Text>
                  </div>
                  <Button
                    variant="light"
                    leftSection={<IconDownload size={16} />}
                    onClick={handleExportData}
                  >
                    Export Data
                  </Button>
                </Group>
              </Card>

              {/* Delete Account */}
              <Card withBorder p="lg" style={{ borderColor: '#FCA5A5' }}>
                <Text fw={600} c="#DC2626">
                  Danger Zone
                </Text>
                <Text size="sm" c="#64748B" mt="xs" mb="md">
                  Once you delete your account, all your data will be permanently removed. This
                  action cannot be undone.
                </Text>
                <Button
                  color="red"
                  variant="outline"
                  leftSection={<IconTrash size={16} />}
                  onClick={() => setDeleteModalOpen(true)}
                >
                  Delete Account
                </Button>
              </Card>
            </Stack>
          </Tabs.Panel>
        </Tabs>
      </Stack>

      {/* Delete Account Modal */}
      <Modal
        opened={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false)
          setDeleteConfirmation('')
        }}
        title={<Text fw={600}>Delete Account</Text>}
        centered
      >
        <Stack>
          <Alert color="red" icon={<IconAlertTriangle size={16} />}>
            This action is irreversible. All your data will be permanently deleted.
          </Alert>

          <Text size="sm">
            To confirm, type{' '}
            <Text span fw={600}>
              delete my account
            </Text>{' '}
            below:
          </Text>

          <TextInput
            value={deleteConfirmation}
            onChange={(e) => setDeleteConfirmation(e.target.value)}
            placeholder="delete my account"
          />

          <Group justify="flex-end" mt="md">
            <Button
              variant="subtle"
              onClick={() => {
                setDeleteModalOpen(false)
                setDeleteConfirmation('')
              }}
            >
              Cancel
            </Button>
            <Button
              color="red"
              disabled={deleteConfirmation.toLowerCase() !== 'delete my account'}
              onClick={handleDeleteAccount}
            >
              Delete Account
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  )
}
