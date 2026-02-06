/**
 * Signup Page Component (Verification Code Version)
 *
 * Implements the new signup flow with 6-digit verification codes
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
  Progress,
  ThemeIcon,
  Loader,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import {
  IconMail,
  IconAlertCircle,
  IconCheck,
  IconShield,
  IconRefresh,
  IconArrowLeft,
} from '@tabler/icons-react'
import { authApiService } from '../../services/auth-api'
import { useAuthStore } from '../../store/auth'

type SignupStep = 'email' | 'verify-code' | 'complete'

interface SignupFormData {
  email: string
}

export function SignupPage() {
  const [step, setStep] = useState<SignupStep>('email')
  const [isLoading, setIsLoading] = useState(false)
  const [email, setEmail] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [resendTimer, setResendTimer] = useState(0)
  const [codeAttempts, setCodeAttempts] = useState(0)

  const navigate = useNavigate()
  const { setUser, setTokens } = useAuthStore()

  const form = useForm<SignupFormData>({
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

  const handleEmailSubmit = async (values: SignupFormData) => {
    setIsLoading(true)
    setError(null)

    try {
      // Check if account already exists
      const accountCheck = await authApiService.checkAccountStatus(values.email)
      
      // Only block if account exists AND is active
      if (accountCheck.status === 'active_account') {
        setError('An active account already exists with this email. Please sign in instead.')
        setIsLoading(false)
        return
      }
      
      // For inactive accounts and new users, proceed with signup
      // This allows inactive users to complete their signup

      // Start signup process
      const response = await authApiService.signup(values.email)
      
      if (response.success) {
        setEmail(values.email)
        setStep('verify-code')
        setResendTimer(60) // 60 second cooldown
        
        notifications.show({
          title: 'Verification code sent!',
          message: `We've sent a 6-digit code to ${values.email}`,
          color: 'green',
          icon: <IconMail size={16} />,
        })
      }
    } catch (error: any) {
      console.error('Signup error:', error)
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
      const response = await authApiService.verifySignupCode(email, verificationCode)
      
      if (response.success && response.token) {
        if (response.user) {
          const user = {
            ...response.user,
            first_name: '',
            last_name: '',
            full_name: response.user.name || '',
            preferred_auth_method: 'email' as const,
            is_email_verified: true,
            has_passkey: false,
            has_2fa: false,
          }
          setUser(user)
        }

        setTokens({ access: response.token, refresh: response.token })
        setStep('complete')

        notifications.show({
          title: 'Account created successfully!',
          message: 'Your email has been verified and your account is ready.',
          color: 'green',
          icon: <IconCheck size={16} />,
        })

        localStorage.setItem('showWelcomeMessage', 'true')

        setTimeout(() => {
          navigate('/dashboard')
        }, 2000)
      } else {
        setError(response.message || 'Invalid code. Please try again.')
      }
    } catch (error: any) {
      console.error('Verify code error:', error)
      setCodeAttempts(codeAttempts + 1)
      
      if (codeAttempts >= 2) {
        setError('Too many failed attempts. Please request a new code.')
      } else {
        setError('Invalid code. Please try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleResendCode = async () => {
    if (resendTimer > 0) return

    setIsLoading(true)
    setError(null)

    try {
      const response = await authApiService.resendCode(email, 'signup')
      
      if (response.success) {
        setResendTimer(60)
        setCodeAttempts(0)
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

  const getStepProgress = () => {
    switch (step) {
      case 'email': return 0
      case 'verify-code': return 50
      case 'complete': return 100
      default: return 0
    }
  }

  // Render different steps
  const renderStep = () => {
    switch (step) {
      case 'email':
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
              />

              <Button
                type="submit"
                loading={isLoading}
                fullWidth
                leftSection={<IconShield size={16} />}
              >
                Send Verification Code
              </Button>

              <Group justify="center" gap="xs">
                <Text size="sm" c="dimmed">
                  Already have an account?
                </Text>
                <Anchor component={Link} to="/auth/login" size="sm">
                  Sign in
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
          </Stack>
        )

      case 'complete':
        return (
          <Stack gap="md" align="center">
            <ThemeIcon size="xl" radius="xl" color="green">
              <IconCheck size={24} />
            </ThemeIcon>
            <Title order={2}>Account created successfully!</Title>
            <Text c="dimmed">
              Your email has been verified and your account is ready.
            </Text>
            <Loader size="sm" />
            <Text size="sm" c="dimmed">
              Redirecting to dashboard...
            </Text>
          </Stack>
        )
    }
  }

  return (
    <Stack gap="xl">
      {/* Progress indicator */}
      <Progress value={getStepProgress()} size="sm" radius="xl" />
      
      {renderStep()}
    </Stack>
  )
}
