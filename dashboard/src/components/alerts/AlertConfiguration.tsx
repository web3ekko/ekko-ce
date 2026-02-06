/**
 * Alert Configuration Component
 * 
 * Configure alert parameters based on selected template
 */

import { useState, useEffect } from 'react'
import {
  Stack,
  Title,
  Text,
  TextInput,
  NumberInput,
  Select,
  MultiSelect,
  Switch,
  Button,
  Group,
  Card,
  Divider,
  Alert,
  Textarea,
  Badge,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import {
  IconSettings,
  IconArrowLeft,
  IconArrowRight,
  IconInfoCircle,
  IconCheck,
} from '@tabler/icons-react'
import type { AlertTemplate, TemplateParameter } from '../../types/alerts'

interface AlertConfigurationProps {
  template: AlertTemplate
  initialParams: Record<string, any>
  onComplete: (params: Record<string, any>) => void
  onBack: () => void
}

export function AlertConfiguration({ 
  template, 
  initialParams, 
  onComplete, 
  onBack 
}: AlertConfigurationProps) {
  const [isValid, setIsValid] = useState(false)

  const form = useForm({
    initialValues: {
      name: initialParams.name || template.name,
      description: initialParams.description || template.description,
      ...initialParams,
    },
    validate: (values) => {
      const errors: Record<string, string> = {}
      
      // Validate required fields
      if (!values.name?.trim()) {
        errors.name = 'Alert name is required'
      }
      
      // Validate template parameters
      template.parameters.forEach(param => {
        if (param.required && !values[param.name]) {
          errors[param.name] = `${param.name} is required`
        }
        
        // Type-specific validation
        if (values[param.name] && param.validation) {
          const value = values[param.name]
          const validation = param.validation
          
          if (param.type === 'number') {
            if (validation.min !== undefined && value < validation.min) {
              errors[param.name] = `Must be at least ${validation.min}`
            }
            if (validation.max !== undefined && value > validation.max) {
              errors[param.name] = `Must be at most ${validation.max}`
            }
          }
          
          if (param.type === 'string' && validation.pattern) {
            const regex = new RegExp(validation.pattern)
            if (!regex.test(value)) {
              errors[param.name] = `Invalid format`
            }
          }
        }
      })
      
      return errors
    },
  })

  // Check if form is valid
  useEffect(() => {
    const errors = form.validate()
    setIsValid(Object.keys(errors.errors).length === 0)
  }, [form.values])

  const handleSubmit = (values: Record<string, any>) => {
    onComplete(values)
  }

  const renderParameterInput = (param: TemplateParameter) => {
    const commonProps = {
      key: param.name,
      label: param.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      description: param.description,
      placeholder: param.placeholder,
      required: param.required,
      ...form.getInputProps(param.name),
    }

    switch (param.type) {
      case 'string':
        if (param.validation?.options) {
          return (
            <Select
              {...commonProps}
              data={param.validation.options.map(opt => ({ value: opt, label: opt }))}
            />
          )
        }
        return <TextInput {...commonProps} />

      case 'number':
        return (
          <NumberInput
            {...commonProps}
            min={param.validation?.min}
            max={param.validation?.max}
          />
        )

      case 'boolean':
        return (
          <Switch
            {...commonProps}
            label={`${commonProps.label}${param.required ? ' *' : ''}`}
            description={param.description}
          />
        )

      case 'array':
        if (param.validation?.options) {
          return (
            <MultiSelect
              {...commonProps}
              data={param.validation.options.map(opt => ({ value: opt, label: opt }))}
              searchable
              creatable={!param.validation?.options}
            />
          )
        }
        return (
          <Textarea
            {...commonProps}
            placeholder="Enter values separated by commas"
          />
        )

      case 'address':
        return (
          <TextInput
            {...commonProps}
            placeholder="0x..."
            pattern="^0x[a-fA-F0-9]{40}$"
          />
        )

      case 'token':
        return (
          <Select
            {...commonProps}
            data={[
              { value: 'ETH', label: 'Ethereum (ETH)' },
              { value: 'USDC', label: 'USD Coin (USDC)' },
              { value: 'USDT', label: 'Tether (USDT)' },
              { value: 'WBTC', label: 'Wrapped Bitcoin (WBTC)' },
              { value: 'DAI', label: 'Dai (DAI)' },
            ]}
            searchable
            creatable
            getCreateLabel={(query) => `+ Add "${query}"`}
          />
        )

      default:
        return <TextInput {...commonProps} />
    }
  }

  const getParametersByCategory = () => {
    const categories = {
      basic: template.parameters.filter(p => 
        ['name', 'description'].includes(p.name) || 
        p.name.includes('amount') || 
        p.name.includes('address')
      ),
      conditions: template.parameters.filter(p => 
        p.name.includes('condition') || 
        p.name.includes('threshold') || 
        p.name.includes('trigger')
      ),
      advanced: template.parameters.filter(p => 
        p.name.includes('window') || 
        p.name.includes('timeout') || 
        p.name.includes('retry')
      ),
    }
    
    // Add remaining parameters to advanced
    const categorized = [...categories.basic, ...categories.conditions, ...categories.advanced]
    const remaining = template.parameters.filter(p => !categorized.includes(p))
    categories.advanced.push(...remaining)
    
    return categories
  }

  const categories = getParametersByCategory()

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack gap="xl">
        {/* Header */}
        <div style={{ textAlign: 'center' }}>
          <Title order={3}>Configure Alert</Title>
          <Text c="dimmed" mt="sm">
            Customize the parameters for "{template.name}"
          </Text>
        </div>

        {/* Template Info */}
        <Alert color="blue" variant="light" icon={<IconInfoCircle size="1rem" />}>
          <Group justify="space-between" align="flex-start">
            <div>
              <Text size="sm" fw={500}>
                {template.name}
              </Text>
              <Text size="sm" mt="xs">
                {template.description}
              </Text>
            </div>
            <Badge color="blue" variant="light">
              {template.category.replace('_', ' ')}
            </Badge>
          </Group>
        </Alert>

        {/* Basic Configuration */}
        <Card shadow="sm" padding="lg" radius="md" withBorder>
          <Stack gap="md">
            <Title order={5}>Basic Settings</Title>
            
            <TextInput
              label="Alert Name"
              placeholder="Enter a descriptive name for your alert"
              required
              {...form.getInputProps('name')}
            />
            
            <Textarea
              label="Description"
              placeholder="Describe what this alert monitors"
              rows={3}
              {...form.getInputProps('description')}
            />
            
            {categories.basic.length > 0 && (
              <>
                <Divider />
                {categories.basic.map(renderParameterInput)}
              </>
            )}
          </Stack>
        </Card>

        {/* Conditions */}
        {categories.conditions.length > 0 && (
          <Card shadow="sm" padding="lg" radius="md" withBorder>
            <Stack gap="md">
              <Title order={5}>Trigger Conditions</Title>
              {categories.conditions.map(renderParameterInput)}
            </Stack>
          </Card>
        )}

        {/* Advanced Settings */}
        {categories.advanced.length > 0 && (
          <Card shadow="sm" padding="lg" radius="md" withBorder>
            <Stack gap="md">
              <Title order={5}>Advanced Settings</Title>
              {categories.advanced.map(renderParameterInput)}
            </Stack>
          </Card>
        )}

        {/* Validation Status */}
        {isValid && (
          <Alert color="green" variant="light" icon={<IconCheck size="1rem" />}>
            <Text size="sm">
              Configuration is valid and ready to proceed.
            </Text>
          </Alert>
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
          
          <Button
            type="submit"
            leftSection={<IconSettings size="1rem" />}
            rightSection={<IconArrowRight size="1rem" />}
            disabled={!isValid}
          >
            Continue to Preview
          </Button>
        </Group>
      </Stack>
    </form>
  )
}

export default AlertConfiguration
