/**
 * Simple Test Page
 * 
 * Basic page to test if React is working
 */

import { Stack, Title, Text, Button, Card } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconCheck } from '@tabler/icons-react'

export function TestPage() {
  const handleClick = () => {
    notifications.show({
      title: 'Success!',
      message: 'React and Mantine are working correctly',
      color: 'green',
      icon: <IconCheck size="1rem" />,
    })
  }

  return (
    <Stack gap="xl" p="xl">
      <Title order={1}>🎉 Test Page</Title>
      
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          <Title order={3}>React App Status</Title>
          <Text>✅ React is rendering</Text>
          <Text>✅ Mantine UI is working</Text>
          <Text>✅ Icons are loading</Text>
          <Text>✅ TypeScript is compiling</Text>
          
          <Button onClick={handleClick} leftSection={<IconCheck size="1rem" />}>
            Test Notifications
          </Button>
        </Stack>
      </Card>

      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          <Title order={3}>Navigation Links</Title>
          <Text>Try these links:</Text>
          <Stack gap="xs">
            <Text>• <a href="/dashboard">Dashboard</a></Text>
            <Text>• <a href="/dashboard/alerts">Alerts</a></Text>
            <Text>• <a href="/auth/login">Login</a></Text>
            <Text>• <a href="/auth/signup">Signup</a></Text>
          </Stack>
        </Stack>
      </Card>
    </Stack>
  )
}
