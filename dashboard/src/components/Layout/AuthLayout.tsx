/**
 * Authentication Layout Component
 * 
 * Layout wrapper for authentication pages (login, signup, etc.)
 */

import { Outlet } from 'react-router-dom'
import { 
  Container, 
  Paper, 
  Title, 
  Text, 
  Group, 
  Stack,
  Box,
  Anchor,
} from '@mantine/core'
import EkkoLogo from '../brand/EkkoLogo'

export function AuthLayout() {
  return (
    <Box
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
    >
      <Container size="sm" style={{ width: '100%', maxWidth: '480px' }}>
        <Stack gap="xl">
          {/* Header */}
          <Stack gap="md" align="center">
            <Group gap="sm">
              <Box
                style={{
                  background: '#FFFFFF',
                  borderRadius: '999px',
                  padding: '14px',
                  border: '1px solid rgba(15, 23, 42, 0.12)',
                  boxShadow: '0 18px 32px rgba(15, 23, 42, 0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <EkkoLogo variant="icon" size={56} />
              </Box>
              <Title order={1} c="white" size="h2">
                Ekko
              </Title>
            </Group>
            <Text c="white" ta="center" size="lg">
              Blockchain monitoring and alerting platform
            </Text>
          </Stack>

          {/* Auth Form Container */}
          <Paper
            shadow="xl"
            p="xl"
            radius="lg"
            style={{
              background: '#FFFFFF',
            }}
          >
            <Outlet />
          </Paper>

          {/* Footer */}
          <Group justify="center" gap="md">
            <Anchor 
              href="/privacy" 
              c="white" 
              size="sm"
              style={{ opacity: 0.8 }}
            >
              Privacy Policy
            </Anchor>
            <Text c="white" size="sm" style={{ opacity: 0.6 }}>
              •
            </Text>
            <Anchor 
              href="/terms" 
              c="white" 
              size="sm"
              style={{ opacity: 0.8 }}
            >
              Terms of Service
            </Anchor>
          </Group>
        </Stack>
      </Container>
    </Box>
  )
}
