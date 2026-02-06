/**
 * Recovery Page Component (Verification Code Version)
 * 
 * Implements account recovery using 6-digit verification codes
 */

import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  TextInput,
  Button,
  Stack,
  Title,
  Text,
  Alert,
  Anchor,
  Group,
  PinInput,
  Paper,
  ThemeIcon,
  List,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import {
  IconMail,
  IconAlertCircle,
  IconShield,
  IconArrowLeft,
  IconRefresh,
  IconCheck,
  IconLock,
} from '@tabler/icons-react'
import { authApiService } from '../../services/auth-api'

type RecoveryStep = 'email' | 'verify-code' | 'complete'

export function RecoveryPage() {
  const [step, setStep] = useState<RecoveryStep>('email')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [resendTimer, setResendTimer] = useState(0)

  const navigate = useNavigate()

  const form = useForm({
    initialValues: {
      email: '',
    },
    validate: {
      email: (value) => {
        if (!value) return 'Email is required'
        if (!/^\S+@\S+\.\S+$/.test(value)) return 'Invalid email format'
        return null
      },
    },
  })

  // Countdown timer for resend code
  useEffect(() => {
    if (resendTimer > 0) {
      const timer = setTimeout(() => setResendTimer(resendTimer - 1), 1000)
      return () => clearTimeout(timer)
    }
  }, [resendTimer])

  const handleEmailSubmit = async (values: { email: string }) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await authApiService.requestRecovery(values.email)
      
      if (response.success) {
        setEmail(values.email)
        setStep('verify-code')
        setResendTimer(60)
        
        notifications.show({
          title: 'Recovery code sent!',
          message: 'If an account exists with this email, we\'ve sent a recovery code',
          color: 'green',
          icon: <IconMail size={16} />,
        })
      }
    } catch (error: any) {
      console.error('Recovery request error:', error)
      // Don't reveal if account exists
      setEmail(values.email)
      setStep('verify-code')
      setResendTimer(60)
      
      notifications.show({
        title: 'Recovery code sent!',
        message: 'If an account exists with this email, we\'ve sent a recovery code',
        color: 'green',
        icon: <IconMail size={16} />,
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleVerifyCode = async () => {
    if (verificationCode.length !== 6) {
      setError('Please enter the complete 6-digit code')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await authApiService.verifyRecoveryCode(email, verificationCode)
      
      if (response.success) {
        setStep('complete')

        notifications.show({
          title: 'Account verified!',
          message: 'Your account has been recovered. You can now sign in with email.',
          color: 'green',
          icon: <IconCheck size={16} />,
        })

        setTimeout(() => {
          navigate('/auth/login')
        }, 3000)
      }
    } catch (error: any) {
      console.error('Verify recovery code error:', error)
      setError('Invalid or expired code. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleResendCode = async () => {
    if (resendTimer > 0) return

    setIsLoading(true)
    setError(null)

    try {
      const response = await authApiService.resendCode(email, 'recovery')
      
      if (response.success) {
        setResendTimer(60)
        setVerificationCode('')
        
        notifications.show({
          title: 'New code sent!',
          message: 'Check your email for the new recovery code',
          color: 'green',
          icon: <IconMail size={16} />,
        })
      }
    } catch (error: any) {
      console.error('Resend code error:', error)
      setError(error.response?.data?.error || 'Failed to resend code')
    } finally {
      setIsLoading(false)
    }
  }

  const renderStep = () => {
    switch (step) {
      case 'email':
        return (
          <form onSubmit={form.onSubmit(handleEmailSubmit)}>
            <Stack gap="md">
              <div style={{ textAlign: 'center' }}>
                <ThemeIcon size="xl" radius="xl" color="orange" mb="md">
                  <IconLock size={24} />
                </ThemeIcon>
                <Title order={2}>Recover your account</Title>
                <Text c="dimmed" mt="sm">
                  Verify your email to regain access to your account
                </Text>
              </div>

              {error && (
                <Alert icon={<IconAlertCircle size={16} />} color="red">
                  {error}
                </Alert>
              )}

              <Paper withBorder p="md" radius="md">
                <Stack gap="xs">
                  <Text size="sm" fw={500}>What happens next?</Text>
                  <List size="sm" spacing="xs">
                    <List.Item>We'll send a verification code to your email</List.Item>
                    <List.Item>You'll verify your identity with the code</List.Item>
                    <List.Item>We'll confirm your account recovery</List.Item>
                    <List.Item>You can sign in again with email verification</List.Item>
                  </List>
                </Stack>
              </Paper>

              <TextInput
                label="Email address"
                placeholder="your@email.com"
                required
                {...form.getInputProps('email')}
                leftSection={<IconMail size={16} />}
                autoFocus
              />

              <Button
                type="submit"
                loading={isLoading}
                fullWidth
                leftSection={<IconShield size={16} />}
              >
                Send Recovery Code
              </Button>

              <Group justify="center" gap="xs">
                <Text size="sm" c="dimmed">
                  Remember your account?
                </Text>
                <Anchor component={Link} to="/auth/login" size="sm">
                  Back to sign in
                </Anchor>
              </Group>
            </Stack>
          </form>
        )

      case 'verify-code':
        return (
          <Stack gap="md">
            <Group justify="space-between" mb="md">
              <Button
                variant="subtle"
                leftSection={<IconArrowLeft size={16} />}
                onClick={() => {
                  setStep('email')
                  setVerificationCode('')
                  setError(null)
                  form.reset()
                }}
              >
                Back
              </Button>
            </Group>

            <div style={{ textAlign: 'center' }}>
              <Title order={2}>Enter recovery code</Title>
              <Text c="dimmed" mt="sm">
                We sent a 6-digit code to <strong>{email}</strong>
              </Text>
            </div>

            {error && (
              <Alert icon={<IconAlertCircle size={16} />} color="red">
                {error}
              </Alert>
            )}

            <PinInput
              length={6}
              type="number"
              value={verificationCode}
              onChange={setVerificationCode}
              size="lg"
              styles={{
                input: {
                  textAlign: 'center',
                  fontFamily: 'monospace',
                  fontSize: '1.5rem',
                },
              }}
              autoFocus
              onComplete={handleVerifyCode}
            />

            <Button
              onClick={handleVerifyCode}
              loading={isLoading}
              fullWidth
              disabled={verificationCode.length !== 6}
            >
              Verify Code
            </Button>

            <Stack gap="xs">
              <Text size="sm" c="dimmed" ta="center">
                Didn't receive the code?
              </Text>
              <Button
                variant="subtle"
                size="sm"
                leftSection={<IconRefresh size={16} />}
                onClick={handleResendCode}
                disabled={resendTimer > 0}
                fullWidth
              >
                {resendTimer > 0 
                  ? `Resend code in ${resendTimer}s` 
                  : 'Resend code'}
              </Button>
            </Stack>

            <Alert color="orange" variant="light">
              <Text size="sm">
                <strong>Security Note:</strong> Verifying this code will sign out all your devices for security.
              </Text>
            </Alert>
          </Stack>
        )

      case 'complete':
        return (
          <Stack gap="md" align="center">
            <ThemeIcon size="xl" radius="xl" color="green">
              <IconCheck size={24} />
            </ThemeIcon>
            <Title order={2}>Account recovered!</Title>
            <Text c="dimmed" ta="center">
              Your account is ready. You can sign in with email verification.
            </Text>
            <Text size="sm" c="dimmed" ta="center">
              Redirecting to sign in...
            </Text>
          </Stack>
        )
    }
  }

  return (
    <Stack gap="xl">
      {renderStep()}
    </Stack>
  )
}
