/**
 * Alert Filters Component
 * 
 * Advanced filtering interface for alerts
 */

import { useState } from 'react'
import {
  Group,
  MultiSelect,
  Select,
  DatePickerInput,
  Button,
  Collapse,
  Stack,
  Text,
  Badge,
  CloseButton,
} from '@mantine/core'
import { DateValue } from '@mantine/dates'
import {
  IconCalendar,
  IconX,
  IconFilter,
} from '@tabler/icons-react'
import type { AlertFilters as AlertFiltersType, AlertStatus, EventType } from '../../types/alerts'

interface AlertFiltersProps {
  filters: AlertFiltersType
  onFiltersChange: (filters: Partial<AlertFiltersType>) => void
}

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'error', label: 'Error' },
  { value: 'draft', label: 'Draft' },
]

const EVENT_TYPE_OPTIONS = [
  { value: 'ACCOUNT_EVENT', label: 'Account Events' },
  { value: 'CONTRACT_EVENT', label: 'Contract Events' },
  { value: 'PROTOCOL_EVENT', label: 'Protocol Events' },
  { value: 'ANOMALY_EVENT', label: 'Anomaly Events' },
  { value: 'PERFORMANCE_EVENT', label: 'Performance Events' },
]

export function AlertFilters({ filters, onFiltersChange }: AlertFiltersProps) {
  const [dateRange, setDateRange] = useState<[DateValue, DateValue]>([
    filters.date_range?.start ? new Date(filters.date_range.start) : null,
    filters.date_range?.end ? new Date(filters.date_range.end) : null,
  ])

  const handleStatusChange = (values: string[]) => {
    onFiltersChange({
      status: values.length > 0 ? values as AlertStatus[] : undefined
    })
  }

  const handleEventTypeChange = (values: string[]) => {
    onFiltersChange({
      event_type: values.length > 0 ? values as EventType[] : undefined
    })
  }

  const handleDateRangeChange = (value: [DateValue, DateValue]) => {
    setDateRange(value)
    
    if (value[0] && value[1]) {
      onFiltersChange({
        date_range: {
          start: value[0].toISOString(),
          end: value[1].toISOString(),
        }
      })
    } else {
      onFiltersChange({
        date_range: undefined
      })
    }
  }

  const handleTagsChange = (values: string[]) => {
    onFiltersChange({
      tags: values.length > 0 ? values : undefined
    })
  }

  const clearAllFilters = () => {
    setDateRange([null, null])
    onFiltersChange({
      status: undefined,
      event_type: undefined,
      created_by: undefined,
      team_id: undefined,
      tags: undefined,
      date_range: undefined,
    })
  }

  const getActiveFilterCount = () => {
    let count = 0
    if (filters.status?.length) count++
    if (filters.event_type?.length) count++
    if (filters.created_by?.length) count++
    if (filters.team_id) count++
    if (filters.tags?.length) count++
    if (filters.date_range) count++
    return count
  }

  const activeFilterCount = getActiveFilterCount()

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Group gap="xs">
          <IconFilter size="1rem" />
          <Text size="sm" fw={500}>
            Filters
          </Text>
          {activeFilterCount > 0 && (
            <Badge size="sm" variant="light">
              {activeFilterCount} active
            </Badge>
          )}
        </Group>
        
        {activeFilterCount > 0 && (
          <Button
            variant="subtle"
            size="xs"
            leftSection={<IconX size="0.875rem" />}
            onClick={clearAllFilters}
          >
            Clear all
          </Button>
        )}
      </Group>

      <Group grow>
        <MultiSelect
          label="Status"
          placeholder="Select status"
          data={STATUS_OPTIONS}
          value={filters.status || []}
          onChange={handleStatusChange}
          clearable
          searchable
        />

        <MultiSelect
          label="Event Type"
          placeholder="Select event types"
          data={EVENT_TYPE_OPTIONS}
          value={filters.event_type || []}
          onChange={handleEventTypeChange}
          clearable
          searchable
        />
      </Group>

      <Group grow>
        <DatePickerInput
          type="range"
          label="Date Range"
          placeholder="Select date range"
          value={dateRange}
          onChange={handleDateRangeChange}
          leftSection={<IconCalendar size="1rem" />}
          clearable
        />

        <MultiSelect
          label="Tags"
          placeholder="Select tags"
          data={[
            // These would come from the API in a real implementation
            { value: 'defi', label: 'DeFi' },
            { value: 'nft', label: 'NFT' },
            { value: 'governance', label: 'Governance' },
            { value: 'security', label: 'Security' },
            { value: 'performance', label: 'Performance' },
          ]}
          value={filters.tags || []}
          onChange={handleTagsChange}
          clearable
          searchable
          creatable
          getCreateLabel={(query) => `+ Create "${query}"`}
        />
      </Group>

      {/* Active Filters Display */}
      {activeFilterCount > 0 && (
        <Group gap="xs">
          <Text size="xs" c="dimmed">
            Active filters:
          </Text>
          
          {filters.status?.map(status => (
            <Badge
              key={status}
              size="sm"
              variant="light"
              rightSection={
                <CloseButton
                  size="xs"
                  onClick={() => {
                    const newStatus = filters.status?.filter(s => s !== status)
                    handleStatusChange(newStatus || [])
                  }}
                />
              }
            >
              Status: {status}
            </Badge>
          ))}
          
          {filters.event_type?.map(eventType => (
            <Badge
              key={eventType}
              size="sm"
              variant="light"
              rightSection={
                <CloseButton
                  size="xs"
                  onClick={() => {
                    const newEventTypes = filters.event_type?.filter(et => et !== eventType)
                    handleEventTypeChange(newEventTypes || [])
                  }}
                />
              }
            >
              Type: {eventType.replace('_', ' ')}
            </Badge>
          ))}
          
          {filters.date_range && (
            <Badge
              size="sm"
              variant="light"
              rightSection={
                <CloseButton
                  size="xs"
                  onClick={() => handleDateRangeChange([null, null])}
                />
              }
            >
              Date: {new Date(filters.date_range.start).toLocaleDateString()} - {new Date(filters.date_range.end).toLocaleDateString()}
            </Badge>
          )}
          
          {filters.tags?.map(tag => (
            <Badge
              key={tag}
              size="sm"
              variant="light"
              rightSection={
                <CloseButton
                  size="xs"
                  onClick={() => {
                    const newTags = filters.tags?.filter(t => t !== tag)
                    handleTagsChange(newTags || [])
                  }}
                />
              }
            >
              Tag: {tag}
            </Badge>
          ))}
        </Group>
      )}
    </Stack>
  )
}

export default AlertFilters
