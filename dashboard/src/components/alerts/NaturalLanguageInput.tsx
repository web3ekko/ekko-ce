/**
 * Natural Language Input Component
 * 
 * AI-powered alert creation from natural language descriptions
 */

import { useState } from 'react'
import {
  Stack,
  Title,
  Text,
  Textarea,
  Button,
  Group,
  Alert,
  Card,
  List,
  Badge,
  Divider,
} from '@mantine/core'
import {
  IconWand,
  IconArrowLeft,
  IconArrowRight,
  IconBulb,
  IconSparkles,
  IconAlertCircle,
} from '@tabler/icons-react'

interface NaturalLanguageInputProps {
  onSubmit: (input: string) => void
  onBack: () => void
  isLoading: boolean
}

const EXAMPLE_PROMPTS = [
  "Alert me when any wallet receives more than 100 ETH in a single transaction",
  "Notify me when Uniswap V3 USDC/ETH pool has unusual volume spikes",
  "Watch for large NFT sales above 50 ETH on OpenSea",
  "Monitor when my wallet balance drops below 1 ETH",
  "Alert on new governance proposals for Compound protocol",
  "Detect when gas prices go above 100 gwei",
]

const TIPS = [
  "Be specific about amounts, tokens, and protocols",
  "Mention the blockchain network if not Ethereum",
  "Include wallet addresses if monitoring specific accounts",
  "Specify time windows for better accuracy",
  "Use common protocol names (Uniswap, Aave, etc.)",
]

export function NaturalLanguageInput({ 
  onSubmit, 
  onBack, 
  isLoading 
}: NaturalLanguageInputProps) {
  const [input, setInput] = useState('')
  const [selectedExample, setSelectedExample] = useState<string | null>(null)

  const handleSubmit = () => {
    if (!input.trim()) return
    onSubmit(input.trim())
  }

  const handleExampleClick = (example: string) => {
    setInput(example)
    setSelectedExample(example)
  }

  const isValid = input.trim().length >= 10

  return (
    <Stack gap="xl">
      {/* Header */}
      <div style={{ textAlign: 'center' }}>
        <Title order={3}>Describe Your Alert</Title>
        <Text c="dimmed" mt="sm">
          Tell us what you want to monitor in plain English. Our AI will create the alert for you.
        </Text>
      </div>

      {/* Main Input */}
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          <Group gap="xs">
            <IconSparkles size="1.25rem" color="var(--mantine-color-blue-6)" />
            <Title order={5}>What would you like to monitor?</Title>
          </Group>
          
          <Textarea
            placeholder="Example: Alert me when any wallet receives more than 100 ETH in a single transaction"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            minRows={4}
            maxRows={8}
            autosize
            disabled={isLoading}
          />
          
          <Group justify="space-between">
            <Text size="xs" c="dimmed">
              {input.length} characters (minimum 10)
            </Text>
            
            {isValid && (
              <Badge color="green" variant="light" size="sm">
                Ready to generate
              </Badge>
            )}
          </Group>
        </Stack>
      </Card>

      {/* Example Prompts */}
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          <Group gap="xs">
            <IconBulb size="1.25rem" color="var(--mantine-color-yellow-6)" />
            <Title order={5}>Example Prompts</Title>
          </Group>
          
          <Text size="sm" c="dimmed">
            Click on any example to use it as a starting point:
          </Text>
          
          <Stack gap="xs">
            {EXAMPLE_PROMPTS.map((example, index) => (
              <Card
                key={index}
                padding="sm"
                radius="sm"
                withBorder
                style={{ 
                  cursor: 'pointer',
                  backgroundColor: selectedExample === example ? 
                    'var(--mantine-color-blue-0)' : 
                    'transparent',
                  borderColor: selectedExample === example ? 
                    'var(--mantine-color-blue-3)' : 
                    'var(--mantine-color-gray-3)',
                }}
                onClick={() => handleExampleClick(example)}
              >
                <Text size="sm">
                  {example}
                </Text>
              </Card>
            ))}
          </Stack>
        </Stack>
      </Card>

      {/* Tips */}
      <Alert color="blue" variant="light" icon={<IconBulb size="1rem" />}>
        <Text size="sm" fw={500} mb="xs">
          Tips for better results:
        </Text>
        <List size="sm" spacing="xs">
          {TIPS.map((tip, index) => (
            <List.Item key={index}>
              {tip}
            </List.Item>
          ))}
        </List>
      </Alert>

      {/* AI Processing Info */}
      {isLoading && (
        <Alert color="blue" icon={<IconSparkles size="1rem" />}>
          <Text size="sm">
            Our AI is analyzing your description and generating the perfect alert configuration. 
            This process uses advanced language models to understand your intent and create 
            precise monitoring conditions.
          </Text>
        </Alert>
      )}

      {/* Actions */}
      <Group justify="space-between">
        <Button
          variant="subtle"
          leftSection={<IconArrowLeft size="1rem" />}
          onClick={onBack}
          disabled={isLoading}
        >
          Back
        </Button>
        
        <Button
          leftSection={<IconWand size="1rem" />}
          rightSection={<IconArrowRight size="1rem" />}
          onClick={handleSubmit}
          disabled={!isValid}
          loading={isLoading}
          size="md"
        >
          {isLoading ? 'Generating Alert...' : 'Generate Alert'}
        </Button>
      </Group>
    </Stack>
  )
}

export default NaturalLanguageInput
