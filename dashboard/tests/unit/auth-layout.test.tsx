import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { AuthLayout } from '../../src/components/layout/AuthLayout'

describe('AuthLayout', () => {
  it('renders the Ekko logo and heading for auth pages', () => {
    render(
      <MantineProvider>
        <MemoryRouter initialEntries={['/auth/login']}>
          <Routes>
            <Route path="/auth" element={<AuthLayout />}>
              <Route path="login" element={<div>Login</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </MantineProvider>
    )

    expect(screen.getByRole('heading', { name: /ekko/i })).toBeInTheDocument()
    expect(screen.getByAltText(/ekko logo/i)).toBeInTheDocument()
  })
})
