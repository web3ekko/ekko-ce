/**
 * Template Selection Component
 * 
 * Browse and select alert templates with categories and search
 */

import { useState } from 'react'
import {
  Stack,
  Title,
  Text,
  TextInput,
  Select,
  Group,
  Card,
  Badge,
  Button,
  Grid,
  Center,
  Loader,
} from '@mantine/core'
import {
  IconSearch,
  IconTemplate,
  IconStar,
  IconUsers,
  IconArrowLeft,
  IconArrowRight,
} from '@tabler/icons-react'
import { EmptyState } from '../common/EmptyState'
import type { AlertTemplate, TemplateCategory } from '../../types/alerts'

interface TemplateSelectionProps {
  templates: AlertTemplate[]
  onTemplateSelect: (template: AlertTemplate) => void
  onBack: () => void
}

const CATEGORY_OPTIONS = [
  { value: '', label: 'All Categories' },
  { value: 'account_monitoring', label: 'Account Monitoring' },
  { value: 'contract_events', label: 'Contract Events' },
  { value: 'defi_protocols', label: 'DeFi Protocols' },
  { value: 'nft_tracking', label: 'NFT Tracking' },
  { value: 'governance', label: 'Governance' },
  { value: 'security', label: 'Security' },
  { value: 'performance', label: 'Performance' },
  { value: 'custom', label: 'Custom' },
]

export function TemplateSelection({ 
  templates, 
  onTemplateSelect, 
  onBack 
}: TemplateSelectionProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')

  // Filter templates based on search and category
  const filteredTemplates = templates.filter(template => {
    const matchesSearch = !searchQuery || 
      template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
    
    const matchesCategory = !selectedCategory || template.category === selectedCategory
    
    return matchesSearch && matchesCategory
  })

  const getCategoryLabel = (category: TemplateCategory) => {
    const option = CATEGORY_OPTIONS.find(opt => opt.value === category)
    return option?.label || category
  }

  const getCategoryColor = (category: TemplateCategory) => {
    switch (category) {
      case 'account_monitoring': return 'blue'
      case 'contract_events': return 'green'
      case 'defi_protocols': return 'purple'
      case 'nft_tracking': return 'pink'
      case 'governance': return 'orange'
      case 'security': return 'red'
      case 'performance': return 'yellow'
      case 'custom': return 'gray'
      default: return 'gray'
    }
  }

  if (templates.length === 0) {
    return (
      <Center h={400}>
        <Stack align="center" gap="md">
          <Loader size="lg" />
          <Text>Loading templates...</Text>
        </Stack>
      </Center>
    )
  }

  return (
    <Stack gap="xl">
      {/* Header */}
      <div style={{ textAlign: 'center' }}>
        <Title order={3}>Choose an Alert Template</Title>
        <Text c="dimmed" mt="sm">
          Select a pre-built template to get started quickly
        </Text>
      </div>

      {/* Search and Filters */}
      <Group grow>
        <TextInput
          placeholder="Search templates..."
          leftSection={<IconSearch size="1rem" />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        
        <Select
          placeholder="All Categories"
          data={CATEGORY_OPTIONS}
          value={selectedCategory}
          onChange={(value) => setSelectedCategory(value || '')}
          clearable
        />
      </Group>

      {/* Templates Grid */}
      {filteredTemplates.length === 0 ? (
        <EmptyState
          title="No templates found"
          description="Try adjusting your search or category filter"
          icon={<IconTemplate size="2rem" />}
        />
      ) : (
        <Grid>
          {filteredTemplates.map((template) => (
            <Grid.Col key={template.id} span={{ base: 12, md: 6, lg: 4 }}>
              <Card
                shadow="sm"
                padding="lg"
                radius="md"
                withBorder
                style={{ 
                  cursor: 'pointer',
                  height: '100%',
                  transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                }}
                onClick={() => onTemplateSelect(template)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)'
                  e.currentTarget.style.boxShadow = 'var(--mantine-shadow-md)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)'
                  e.currentTarget.style.boxShadow = 'var(--mantine-shadow-sm)'
                }}
              >
                <Stack gap="md" h="100%">
                  {/* Header */}
                  <Group justify="space-between" align="flex-start">
                    <Badge
                      color={getCategoryColor(template.category)}
                      variant="light"
                      size="sm"
                    >
                      {getCategoryLabel(template.category)}
                    </Badge>
                    
                    {template.is_public && (
                      <Group gap="xs">
                        <IconUsers size="0.875rem" />
                        <Text size="xs" c="dimmed">Public</Text>
                      </Group>
                    )}
                  </Group>

                  {/* Content */}
                  <Stack gap="xs" style={{ flex: 1 }}>
                    <Title order={5} lineClamp={2}>
                      {template.name}
                    </Title>
                    
                    <Text size="sm" c="dimmed" lineClamp={3}>
                      {template.description}
                    </Text>
                  </Stack>

                  {/* Tags */}
                  {template.tags.length > 0 && (
                    <Group gap="xs">
                      {template.tags.slice(0, 3).map((tag) => (
                        <Badge
                          key={tag}
                          size="xs"
                          variant="outline"
                          color="gray"
                        >
                          {tag}
                        </Badge>
                      ))}
                      {template.tags.length > 3 && (
                        <Text size="xs" c="dimmed">
                          +{template.tags.length - 3} more
                        </Text>
                      )}
                    </Group>
                  )}

                  {/* Stats */}
                  <Group justify="space-between" align="center">
                    <Group gap="xs">
                      <IconStar size="0.875rem" />
                      <Text size="sm">
                        {template.rating.toFixed(1)}
                      </Text>
                      <Text size="xs" c="dimmed">
                        ({template.reviews_count})
                      </Text>
                    </Group>
                    
                    <Text size="xs" c="dimmed">
                      Used {template.usage_count} times
                    </Text>
                  </Group>
                </Stack>
              </Card>
            </Grid.Col>
          ))}
        </Grid>
      )}

      {/* Actions */}
      <Group justify="space-between">
        <Button
          variant="subtle"
          leftSection={<IconArrowLeft size="1rem" />}
          onClick={onBack}
        >
          Back
        </Button>
        
        <Text size="sm" c="dimmed">
          {filteredTemplates.length} template{filteredTemplates.length !== 1 ? 's' : ''} available
        </Text>
      </Group>
    </Stack>
  )
}

export default TemplateSelection
