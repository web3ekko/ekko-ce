/**
 * React App with Mantine UI
 */

import React from 'react'
import { MantineProvider, Button, Stack, Title, Text, Card } from '@mantine/core'
import { notifications, Notifications } from '@mantine/notifications'
import { IconCheck } from '@tabler/icons-react'

// Import Mantine styles
import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'

console.log('App-with-mantine.tsx loading...')

function AppContent() {
  console.log('AppContent component rendering...')
  
  const [count, setCount] = React.useState(0)
  
  const showNotification = () => {
    notifications.show({
      title: 'Success!',
      message: 'Mantine notifications are working!',
      color: 'green',
      icon: <IconCheck size="1rem" />,
    })
  }
  
  return (
    <Stack gap="xl" p="xl">
      <Title order={1}>🎉 React + Mantine Test</Title>
      
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          <Text>✅ React is working!</Text>
          <Text>✅ Mantine UI is working!</Text>
          <Text>✅ Icons are working!</Text>
          <Text>✅ Notifications are working!</Text>
        </Stack>
      </Card>
      
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          <Title order={3}>Interactive Test</Title>
          <Text>Counter: {count}</Text>
          
          <Stack gap="sm">
            <Button 
              onClick={() => setCount(count + 1)}
              variant="filled"
            >
              Increment Counter
            </Button>
            
            <Button 
              onClick={() => setCount(0)}
              variant="outline"
              color="red"
            >
              Reset Counter
            </Button>
            
            <Button 
              onClick={showNotification}
              variant="light"
              color="green"
              leftSection={<IconCheck size="1rem" />}
            >
              Test Notification
            </Button>
          </Stack>
        </Stack>
      </Card>
      
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          <Title order={3}>Next Steps</Title>
          <Text size="sm">
            If everything above works, we can add:
          </Text>
          <Stack gap="xs">
            <Text size="sm">• React Router for navigation</Text>
            <Text size="sm">• Authentication system</Text>
            <Text size="sm">• Dashboard layout</Text>
            <Text size="sm">• Alert management</Text>
          </Stack>
        </Stack>
      </Card>
    </Stack>
  )
}

function App() {
  console.log('App component rendering...')
  
  return (
    <MantineProvider>
      <Notifications />
      <AppContent />
    </MantineProvider>
  )
}

console.log('App-with-mantine.tsx loaded, exporting App...')

export default App
