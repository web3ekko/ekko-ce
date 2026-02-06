/**
 * Security Settings Page
 *
 * Email verification is the current sign-in method for the web dashboard.
 */

import { Container, Title, Stack, Text, Card, Tabs, LoadingOverlay } from '@mantine/core'
import { IconShield, IconDevices, IconHistory } from '@tabler/icons-react'
import { useAuthStore } from '../../store/auth'

export function SecurityPage() {
  const { isLoading } = useAuthStore()

  return (
    <Container size="lg">
      <LoadingOverlay visible={isLoading} />

      <Stack gap="xl">
        <div>
          <Title order={2} mb="xs">Security Settings</Title>
          <Text c="dimmed">
            Manage account security and authentication preferences.
          </Text>
        </div>

        <Tabs defaultValue="2fa">
          <Tabs.List>
            <Tabs.Tab value="2fa" leftSection={<IconShield size={16} />}>
              Two-Factor Auth
            </Tabs.Tab>
            <Tabs.Tab value="devices" leftSection={<IconDevices size={16} />}>
              Trusted Devices
            </Tabs.Tab>
            <Tabs.Tab value="history" leftSection={<IconHistory size={16} />}>
              Login History
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="2fa" pt="xl">
            <Card withBorder>
              <Text>Two-Factor Authentication settings coming soon...</Text>
            </Card>
          </Tabs.Panel>

          <Tabs.Panel value="devices" pt="xl">
            <Card withBorder>
              <Text>Trusted Devices management coming soon...</Text>
            </Card>
          </Tabs.Panel>

          <Tabs.Panel value="history" pt="xl">
            <Card withBorder>
              <Text>Login History coming soon...</Text>
            </Card>
          </Tabs.Panel>
        </Tabs>
      </Stack>
    </Container>
  )
}
