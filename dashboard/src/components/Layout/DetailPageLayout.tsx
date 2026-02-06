/**
 * DetailPageLayout Component
 *
 * Unified layout wrapper for all detail pages (AlertDetailPage, WalletGroupDetailPage, etc.)
 * Provides consistent header, back button, breadcrumbs, and layout structure.
 */

import { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Container,
  Title,
  Text,
  Button,
  Group,
  Stack,
} from '@mantine/core'
import { IconArrowLeft } from '@tabler/icons-react'
import { PageBreadcrumb } from './PageBreadcrumb'

interface DetailPageLayoutProps {
  /** Page title displayed prominently */
  title: string
  /** Optional subtitle/description */
  subtitle?: string
  /** Optional badge or indicator to show next to the title */
  titleBadge?: ReactNode
  /** Action buttons to display in the top-right */
  actions?: ReactNode
  /** Path to navigate to when back button is clicked, or -1 for browser back */
  backPath?: string | number
  /** Label for the back button */
  backLabel?: string
  /** Override the current page label in breadcrumbs */
  breadcrumbLabel?: string
  /** Whether to show breadcrumbs */
  showBreadcrumbs?: boolean
  /** Page content */
  children: ReactNode
  /** Whether to use fluid container (full width) */
  fluid?: boolean
}

export function DetailPageLayout({
  title,
  subtitle,
  titleBadge,
  actions,
  backPath = -1,
  backLabel = 'Back',
  breadcrumbLabel,
  showBreadcrumbs = true,
  children,
  fluid = true,
}: DetailPageLayoutProps) {
  const navigate = useNavigate()

  const handleBack = () => {
    if (typeof backPath === 'number') {
      navigate(backPath)
    } else {
      navigate(backPath)
    }
  }

  return (
    <Container fluid={fluid}>
      {/* Breadcrumbs */}
      {showBreadcrumbs && (
        <PageBreadcrumb currentPageLabel={breadcrumbLabel || title} />
      )}

      {/* Back Button */}
      <Button
        variant="subtle"
        leftSection={<IconArrowLeft size={16} />}
        onClick={handleBack}
        mb="md"
        c="#64748B"
        styles={{
          root: {
            paddingLeft: 0,
            '&:hover': {
              backgroundColor: 'transparent',
              color: '#0F172A',
            },
          },
        }}
      >
        {backLabel}
      </Button>

      {/* Page Header */}
      <Group justify="space-between" align="flex-start" mb="lg">
        <Stack gap={4}>
          <Group gap="sm">
            <Title order={2} c="#0F172A">
              {title}
            </Title>
            {titleBadge}
          </Group>
          {subtitle && (
            <Text c="#64748B" size="sm">
              {subtitle}
            </Text>
          )}
        </Stack>

        {actions && <Group gap="sm">{actions}</Group>}
      </Group>

      {/* Page Content */}
      {children}
    </Container>
  )
}
