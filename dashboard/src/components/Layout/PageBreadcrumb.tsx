/**
 * PageBreadcrumb Component
 *
 * Auto-generates breadcrumb navigation from React Router path segments.
 * Each segment is clickable for easy navigation back through the hierarchy.
 */

import { Breadcrumbs, Anchor, Text } from '@mantine/core'
import { useLocation, useNavigate } from 'react-router-dom'
import { IconChevronRight, IconHome } from '@tabler/icons-react'

interface BreadcrumbItem {
  label: string
  path: string
}

// Human-readable labels for path segments
const pathLabels: Record<string, string> = {
  dashboard: 'Dashboard',
  alerts: 'Alerts',
  wallets: 'Wallets',
  groups: 'Groups',
  analytics: 'Analytics',
  settings: 'Settings',
  profile: 'Profile',
  team: 'Team',
  api: 'Developer API',
  webhooks: 'Webhooks',
  marketplace: 'Marketplace',
  help: 'Help',
  security: 'Security',
  billing: 'Billing',
  notifications: 'Notifications',
}

// Get human-readable label for a path segment
function getLabel(segment: string): string {
  // Check for predefined labels
  if (pathLabels[segment]) {
    return pathLabels[segment]
  }

  // If it looks like an ID (UUID or numeric), return "Details"
  if (/^[0-9a-f-]{36}$/i.test(segment) || /^\d+$/.test(segment)) {
    return 'Details'
  }

  // Otherwise, capitalize and replace hyphens/underscores with spaces
  return segment
    .split(/[-_]/)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

interface PageBreadcrumbProps {
  /** Custom breadcrumb items to override auto-generation */
  items?: BreadcrumbItem[]
  /** Whether to show the home icon at the start */
  showHome?: boolean
  /** Override the current page label (useful for dynamic pages) */
  currentPageLabel?: string
}

export function PageBreadcrumb({
  items,
  showHome = true,
  currentPageLabel
}: PageBreadcrumbProps) {
  const location = useLocation()
  const navigate = useNavigate()

  // Generate breadcrumb items from current path if not provided
  const breadcrumbItems: BreadcrumbItem[] = items || (() => {
    const segments = location.pathname.split('/').filter(Boolean)
    const crumbs: BreadcrumbItem[] = []
    let currentPath = ''

    segments.forEach((segment, index) => {
      currentPath += `/${segment}`
      const isLast = index === segments.length - 1

      crumbs.push({
        label: isLast && currentPageLabel ? currentPageLabel : getLabel(segment),
        path: currentPath,
      })
    })

    return crumbs
  })()

  if (breadcrumbItems.length <= 1) {
    return null // Don't show breadcrumbs for root-level pages
  }

  return (
    <Breadcrumbs
      separator={<IconChevronRight size={14} color="#94A3B8" />}
      mb="md"
      styles={{
        root: {
          flexWrap: 'wrap',
        },
        separator: {
          marginLeft: 6,
          marginRight: 6,
        },
      }}
    >
      {showHome && (
        <Anchor
          onClick={() => navigate('/dashboard')}
          c="#64748B"
          size="sm"
          style={{
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <IconHome size={14} />
        </Anchor>
      )}
      {breadcrumbItems.slice(showHome ? 1 : 0).map((item, index, arr) => {
        const isLast = index === arr.length - 1

        if (isLast) {
          return (
            <Text key={item.path} size="sm" fw={500} c="#0F172A">
              {item.label}
            </Text>
          )
        }

        return (
          <Anchor
            key={item.path}
            onClick={() => navigate(item.path)}
            c="#64748B"
            size="sm"
            style={{ cursor: 'pointer' }}
          >
            {item.label}
          </Anchor>
        )
      })}
    </Breadcrumbs>
  )
}
