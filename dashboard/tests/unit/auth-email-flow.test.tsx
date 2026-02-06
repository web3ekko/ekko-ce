import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { MemoryRouter } from 'react-router-dom'

import { LoginPage } from '../../src/pages/auth/LoginPage'
import { SignupPage } from '../../src/pages/auth/SignupPage'

describe('Email-only authentication pages', () => {
  it('renders the email verification login flow without passkey UI', () => {
    render(
      <MantineProvider>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </MantineProvider>
    )

    expect(screen.getByRole('heading', { name: /enter your email/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /send verification code/i }).length).toBeGreaterThan(0)
    expect(screen.queryByText(/passkey/i)).not.toBeInTheDocument()
  })

  it('renders the email verification signup flow without passkey UI', () => {
    render(
      <MantineProvider>
        <MemoryRouter>
          <SignupPage />
        </MemoryRouter>
      </MantineProvider>
    )

    expect(screen.getByRole('heading', { name: /enter your email/i })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /send verification code/i }).length).toBeGreaterThan(0)
    expect(screen.queryByText(/passkey/i)).not.toBeInTheDocument()
  })
})
