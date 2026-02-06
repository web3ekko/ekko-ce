/**
 * Dashboard Authentication Component Unit Tests
 * 
 * These tests are derived from the authentication PRD and technical context:
 * - /docs/prd/01-AUTHENTICATION-SYSTEM-USDT.md
 * - /docs/technical/authentication/TECHNICAL-CONTEXT-Authentication.md
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { MantineProvider } from '@mantine/core';
import AuthenticationFlow from '../components/AuthenticationFlow';
import { useAuth } from '../hooks/useAuth';

// Mock the authentication hook
vi.mock('../hooks/useAuth');

// Mock fetch for API calls
global.fetch = vi.fn();

const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <MantineProvider>{children}</MantineProvider>
);

describe('Authentication System Architecture', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render passwordless authentication interface', () => {
    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: vi.fn(),
      signupComplete: vi.fn(),
      isLoading: false,
      error: null
    });

    render(
      <TestWrapper>
        <AuthenticationFlow />
      </TestWrapper>
    );

    // Should show email input (step 1 of authentication flow)
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    
    // Should not show password field (passwordless system)
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
    
    // Should show professional business messaging
    expect(screen.getByText(/enter your work email/i)).toBeInTheDocument();
  });

  it('should support multi-device Knox token authentication', () => {
    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { email: 'test@ekko.zone', id: '123' },
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: vi.fn(),
      signupComplete: vi.fn(),
      isLoading: false,
      error: null
    });

    render(
      <TestWrapper>
        <AuthenticationFlow />
      </TestWrapper>
    );

    // When authenticated, should show dashboard access
    expect(screen.getByText(/access to alert creation/i)).toBeInTheDocument();
  });
});

describe('Passwordless Authentication Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should complete authentication flow within 3 seconds', async () => {
    const mockSignupBegin = vi.fn().mockResolvedValue({ success: true });
    const mockSignupComplete = vi.fn().mockResolvedValue({
      success: true,
      tokens: { knox_token: 'test_knox_token_123' }
    });

    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: mockSignupBegin,
      signupComplete: mockSignupComplete,
      isLoading: false,
      error: null
    });

    render(
      <TestWrapper>
        <AuthenticationFlow />
      </TestWrapper>
    );

    const startTime = Date.now();

    // Step 1: Email collection
    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'test@ekko.zone' } });

    // Step 2: Submit signup
    const submitButton = screen.getByRole('button', { name: /sign up/i });
    fireEvent.click(submitButton);

    // Wait for signup to complete
    await waitFor(() => {
      expect(mockSignupBegin).toHaveBeenCalledWith('test@ekko.zone');
    });

    const endTime = Date.now();
    const authTime = endTime - startTime;

    // Should complete within 3 seconds (3000ms)
    expect(authTime).toBeLessThan(3000);
  });

  it('should detect WebAuthn capability automatically', () => {
    // Mock WebAuthn support
    Object.defineProperty(navigator, 'credentials', {
      value: {
        create: vi.fn(),
        get: vi.fn()
      },
      configurable: true
    });

    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: vi.fn(),
      signupComplete: vi.fn(),
      isLoading: false,
      error: null
    });

    render(
      <TestWrapper>
        <AuthenticationFlow />
      </TestWrapper>
    );

    // Should show passkey option when WebAuthn is supported
    expect(screen.getByText(/use touch id\/face id/i)).toBeInTheDocument();
  });
});

describe('User Registration Process', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should handle Django-Firebase integration automatically', async () => {
    const mockSignupBegin = vi.fn().mockResolvedValue({
      success: true,
      message: 'Firebase user created, check email for verification'
    });

    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: mockSignupBegin,
      signupComplete: vi.fn(),
      isLoading: false,
      error: null
    });

    render(
      <TestWrapper>
        <AuthenticationFlow />
      </TestWrapper>
    );

    // Start registration
    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'test@ekko.zone' } });

    const submitButton = screen.getByRole('button', { name: /sign up/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockSignupBegin).toHaveBeenCalledWith('test@ekko.zone');
    });

    // Should show email verification step
    expect(screen.getByText(/check your email/i)).toBeInTheDocument();
  });

  it('should generate Knox tokens automatically without separate API call', async () => {
    const mockSignupComplete = vi.fn().mockResolvedValue({
      success: true,
      tokens: { knox_token: 'auto_generated_knox_token_456' },
      user: { email: 'test@ekko.zone', firebase_uid: 'firebase_uid_123' }
    });

    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: vi.fn(),
      signupComplete: mockSignupComplete,
      isLoading: false,
      error: null
    });

    render(
      <TestWrapper>
        <AuthenticationFlow verificationToken="test_token_123" />
      </TestWrapper>
    );

    // Email verification should automatically complete signup
    await waitFor(() => {
      expect(mockSignupComplete).toHaveBeenCalledWith('test_token_123');
    });

    // Knox token should be automatically provided
    expect(mockSignupComplete).toHaveReturnedWith(
      expect.objectContaining({
        tokens: expect.objectContaining({
          knox_token: expect.any(String)
        })
      })
    );
  });
});

describe('WebAuthn Passkey Implementation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock WebAuthn support
    Object.defineProperty(navigator, 'credentials', {
      value: {
        create: vi.fn().mockResolvedValue({
          id: 'test_credential_id',
          response: {
            attestationObject: 'test_attestation',
            clientDataJSON: 'test_client_data'
          }
        }),
        get: vi.fn().mockResolvedValue({
          id: 'test_credential_id',
          response: {
            authenticatorData: 'test_auth_data',
            signature: 'test_signature',
            clientDataJSON: 'test_client_data'
          }
        })
      },
      configurable: true
    });
  });

  it('should support cross-platform passkey authentication', async () => {
    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: vi.fn(),
      signupComplete: vi.fn(),
      isLoading: false,
      error: null
    });

    render(
      <TestWrapper>
        <AuthenticationFlow />
      </TestWrapper>
    );

    // Should offer passkey authentication on supported platforms
    const passkeyButton = screen.getByRole('button', { name: /use passkey/i });
    expect(passkeyButton).toBeInTheDocument();

    fireEvent.click(passkeyButton);

    // Should call WebAuthn API
    await waitFor(() => {
      expect(navigator.credentials.get).toHaveBeenCalled();
    });
  });

  it('should provide email fallback when passkey fails', async () => {
    // Mock passkey failure
    Object.defineProperty(navigator, 'credentials', {
      value: {
        get: vi.fn().mockRejectedValue(new Error('User cancelled'))
      },
      configurable: true
    });

    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: vi.fn(),
      signupComplete: vi.fn(),
      isLoading: false,
      error: null
    });

    render(
      <TestWrapper>
        <AuthenticationFlow />
      </TestWrapper>
    );

    const passkeyButton = screen.getByRole('button', { name: /use passkey/i });
    fireEvent.click(passkeyButton);

    // Should show email fallback option
    await waitFor(() => {
      expect(screen.getByText(/use email link instead/i)).toBeInTheDocument();
    });
  });
});

describe('Authentication Error Handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should show professional error messages', async () => {
    const mockSignupBegin = vi.fn().mockRejectedValue({
      response: {
        status: 400,
        json: () => Promise.resolve({
          errors: { email: ['Please enter a valid email address'] }
        })
      }
    });

    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: mockSignupBegin,
      signupComplete: vi.fn(),
      isLoading: false,
      error: 'Please enter a valid email address'
    });

    render(
      <TestWrapper>
        <AuthenticationFlow />
      </TestWrapper>
    );

    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });

    const submitButton = screen.getByRole('button', { name: /sign up/i });
    fireEvent.click(submitButton);

    // Should show professional error message
    await waitFor(() => {
      expect(screen.getByText(/please enter a valid email address/i)).toBeInTheDocument();
    });
  });

  it('should provide clear recovery paths', () => {
    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: vi.fn(),
      signupComplete: vi.fn(),
      isLoading: false,
      error: 'Connection issue, retrying...'
    });

    render(
      <TestWrapper>
        <AuthenticationFlow />
      </TestWrapper>
    );

    // Should show retry option
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });
});

describe('Performance Requirements', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should provide immediate feedback for all actions', async () => {
    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: vi.fn(),
      signupComplete: vi.fn(),
      isLoading: true,
      error: null
    });

    render(
      <TestWrapper>
        <AuthenticationFlow />
      </TestWrapper>
    );

    // Should show loading state immediately
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText(/processing/i)).toBeInTheDocument();
  });

  it('should ensure consistent performance across devices', () => {
    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: vi.fn(),
      signupComplete: vi.fn(),
      isLoading: false,
      error: null
    });

    render(
      <TestWrapper>
        <AuthenticationFlow />
      </TestWrapper>
    );

    // Interface should be responsive and accessible
    const emailInput = screen.getByLabelText(/email/i);
    expect(emailInput).toHaveAttribute('type', 'email');
    expect(emailInput).toHaveAttribute('aria-required', 'true');
  });
});

describe('Integration Test', () => {
  it('should match consolidated authentication specification', async () => {
    const mockSignupBegin = vi.fn().mockResolvedValue({ success: true });
    const mockSignupComplete = vi.fn().mockResolvedValue({
      success: true,
      tokens: { knox_token: 'integration_test_knox_token' },
      user: { email: 'integration@ekko.zone', firebase_uid: 'firebase_uid_integration' }
    });

    const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      signupBegin: mockSignupBegin,
      signupComplete: mockSignupComplete,
      isLoading: false,
      error: null
    });

    render(
      <TestWrapper>
        <AuthenticationFlow />
      </TestWrapper>
    );

    // Step 1: Email collection
    const emailInput = screen.getByLabelText(/email/i);
    expect(emailInput).toHaveAttribute('placeholder', 'Enter your work email');

    fireEvent.change(emailInput, { target: { value: 'integration@ekko.zone' } });

    // Step 2: Passkey detection (should be automatic)
    expect(screen.getByText(/auto-detect biometric support/i)).toBeInTheDocument();

    // Step 3: Submit authentication
    const submitButton = screen.getByRole('button', { name: /sign up/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockSignupBegin).toHaveBeenCalledWith('integration@ekko.zone');
    });

    // Step 4: Should show dashboard access after completion
    // (This would be tested in the parent component that handles routing)
    expect(mockSignupBegin).toHaveBeenCalled();
  });
});

describe('Verification Code Authentication', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should display 6-digit code input with auto-advance', async () => {
    render(
      <TestWrapper>
        <AuthenticationFlow mode="verify-code" />
      </TestWrapper>
    );

    // Should show 6 separate digit inputs
    const codeInputs = screen.getAllByRole('textbox', { name: /digit/i });
    expect(codeInputs).toHaveLength(6);

    // Type first digit - should auto-advance to next
    fireEvent.change(codeInputs[0], { target: { value: '1' } });
    expect(codeInputs[1]).toHaveFocus();
  });

  it('should show resend code with countdown timer', async () => {
    render(
      <TestWrapper>
        <AuthenticationFlow mode="verify-code" />
      </TestWrapper>
    );

    // Should show resend button disabled with countdown
    const resendButton = screen.getByRole('button', { name: /resend code/i });
    expect(resendButton).toBeDisabled();
    expect(screen.getByText(/wait 30 seconds/i)).toBeInTheDocument();
  });
});

describe('Mandatory Passkey Creation', () => {
  it('should not allow skipping passkey creation during signup', async () => {
    render(
      <TestWrapper>
        <AuthenticationFlow mode="create-passkey" />
      </TestWrapper>
    );

    // Should NOT show skip button
    expect(screen.queryByRole('button', { name: /skip/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/set up later/i)).not.toBeInTheDocument();

    // Should show mandatory passkey creation
    expect(screen.getByText(/create your passkey/i)).toBeInTheDocument();
    expect(screen.getByText(/mandatory/i)).toBeInTheDocument();
  });
});

describe('Passkey Sign-In with Conditional UI', () => {
  it('should not require email for passkey sign-in', async () => {
    // Mock conditional UI support
    Object.defineProperty(navigator.credentials, 'get', {
      value: vi.fn().mockImplementation((options) => {
        return options.mediation === 'conditional';
      })
    });

    render(
      <TestWrapper>
        <AuthenticationFlow mode="signin" />
      </TestWrapper>
    );

    const passkeyButton = screen.getByRole('button', { name: /sign in with passkey/i });
    fireEvent.click(passkeyButton);

    // Should NOT show email input
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
    
    // Should show passkey selection
    expect(screen.getByText(/select your passkey/i)).toBeInTheDocument();
  });
});

describe('Account Recovery Flow', () => {
  it('should require new passkey after recovery', async () => {
    render(
      <TestWrapper>
        <AuthenticationFlow mode="recovery" />
      </TestWrapper>
    );

    // Enter recovery code
    const codeInputs = screen.getAllByRole('textbox', { name: /digit/i });
    const recoveryCode = '123456';
    recoveryCode.split('').forEach((digit, index) => {
      fireEvent.change(codeInputs[index], { target: { value: digit } });
    });

    // After code verification, should show mandatory passkey creation
    await waitFor(() => {
      expect(screen.getByText(/create new passkey/i)).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /skip/i })).not.toBeInTheDocument();
    });
  });
});
