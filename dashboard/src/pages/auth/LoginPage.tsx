/**
 * Login Page Component (Email Verification)
 *
 * Email-only sign-in using verification codes.
 */

import { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
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
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import {
  IconMail,
  IconAlertCircle,
  IconArrowLeft,
  IconRefresh,
  IconCheck,
} from '@tabler/icons-react'
import { authApiService } from '../../services/auth-api'
import { useAuthStore } from '../../store/auth'

type EmailStep = 'enter-email' | 'verify-code'

export function LoginPage() {
  const [emailStep, setEmailStep] = useState<EmailStep>('enter-email')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [resendTimer, setResendTimer] = useState(0)

  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/dashboard'

  const { setUser, setTokens } = useAuthStore()

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
      const accountCheck = await authApiService.checkAccountStatus(values.email)
      if (!accountCheck.exists) {
        setError('No account found with this email. Please sign up first.')
        setIsLoading(false)
        return
      }

      const response = await authApiService.sendSigninCode(values.email)
      if (response.success) {
        setEmail(values.email)
        setEmailStep('verify-code')
        setResendTimer(60)

        notifications.show({
          title: 'Verification code sent!',
          message: `We've sent a 6-digit code to ${values.email}`,
          color: 'green',
          icon: <IconMail size={16} />,
        })
      }
    } catch (error: any) {
      console.error('Send code error:', error)
      setError(error.response?.data?.error || 'Failed to send verification code')
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
      const response = await authApiService.verifySigninCode(email, verificationCode)

      if (response.success && response.token) {
        if (response.user) {
          setUser(response.user)
        }
        setTokens({
          access: response.token,
          refresh: response.token,
        })

        notifications.show({
          title: 'Welcome back!',
          message: 'Successfully signed in',
          color: 'green',
          icon: <IconCheck size={16} />,
        })

        navigate(from, { replace: true })
      } else {
        setError(response.message || 'Invalid code')
      }
    } catch (error: any) {
      console.error('Verify code error:', error)
      setError(error.response?.data?.error || 'Invalid code')
    } finally {
      setIsLoading(false)
    }
  }

  const handleResendCode = async () => {
    if (resendTimer > 0) return

    setIsLoading(true)
    setError(null)

    try {
      const response = await authApiService.resendCode(email, 'signin')
      if (response.success) {
        setResendTimer(60)
        setVerificationCode('')

        notifications.show({
          title: 'New code sent!',
          message: 'Check your email for the new verification code',
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

  if (emailStep === 'enter-email') {
    return (
      <form onSubmit={form.onSubmit(handleEmailSubmit)}>
        <Stack gap="md">
          <div style={{ textAlign: 'center' }}>
            <Title order={2}>Enter your email</Title>
            <Text c="dimmed" mt="sm">
              We'll send you a verification code
            </Text>
          </div>

          {error && (
            <Alert icon={<IconAlertCircle size={16} />} color="red">
              {error}
            </Alert>
          )}

          <TextInput
            label="Email address"
            placeholder="your@email.com"
            required
            {...form.getInputProps('email')}
            leftSection={<IconMail size={16} />}
            autoFocus
          />

          <Button type="submit" loading={isLoading} fullWidth>
            Send Verification Code
          </Button>

          <Group justify="center" gap="xs">
            <Text size="sm" c="dimmed">
              Need help?
            </Text>
            <Anchor component={Link} to="/auth/recovery" size="sm">
              Recover account
            </Anchor>
          </Group>

          <Group justify="center" gap="xs">
            <Text size="sm" c="dimmed">
              Don&apos;t have an account?
            </Text>
            <Anchor component={Link} to="/auth/signup" size="sm">
              Sign up
            </Anchor>
          </Group>
        </Stack>
      </form>
    )
  }

  return (
    <Stack gap="md">
      <Group justify="space-between" mb="md">
        <Button
          variant="subtle"
          leftSection={<IconArrowLeft size={16} />}
          onClick={() => {
            setEmailStep('enter-email')
            setVerificationCode('')
            setError(null)
          }}
        >
          Back
        </Button>
      </Group>

      <div style={{ textAlign: 'center' }}>
        <Title order={2}>Enter verification code</Title>
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
        Verify & Sign In
      </Button>

      <Stack gap="xs">
        <Text size="sm" c="dimmed" ta="center">
          Didn&apos;t receive the code?
        </Text>
        <Button
          variant="subtle"
          size="sm"
          leftSection={<IconRefresh size={16} />}
          onClick={handleResendCode}
          disabled={resendTimer > 0}
          fullWidth
        >
          {resendTimer > 0 ? `Resend code in ${resendTimer}s` : 'Resend code'}
        </Button>
      </Stack>
    </Stack>
  )
}
