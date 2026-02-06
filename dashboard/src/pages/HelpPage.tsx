/**
 * Help & Support Page - Improved Version
 * 
 * Documentation, FAQs, and support resources with premium UI
 */

import {
  Container,
  Title,
  Text,
  Card,
  Grid,
  Group,
  Stack,
  Button,
  TextInput,
  Textarea,
  Accordion,
  Badge,
  ActionIcon,
  Tabs,
  Alert,
  ThemeIcon,
  SimpleGrid,
  Avatar,
} from '@mantine/core'
import {
  IconSearch,
  IconMail,
  IconMessageCircle,
  IconBook,
  IconQuestionMark,
  IconExternalLink,
  IconAlertCircle,
  IconCheck,
  IconClock,
  IconChevronRight,
  IconLifebuoy,
  IconBrandDiscord,
  IconBrandTwitter,
} from '@tabler/icons-react'
import { useState } from 'react'

export function HelpPage() {
  const [activeTab, setActiveTab] = useState<string | null>('faq')

  const faqs = [
    {
      question: 'How do I connect my wallet?',
      answer: 'You can connect your wallet by clicking the "Connect Wallet" button in the top right corner and selecting your preferred wallet provider. We support MetaMask, WalletConnect, and Coinbase Wallet.'
    },
    {
      question: 'How do I set up alerts?',
      answer: 'Navigate to the Alerts page and click "Create Alert". You can set up various types of alerts including transaction monitoring, balance changes, and custom conditions.'
    },
    {
      question: 'What is the Pro Plan?',
      answer: 'The Pro Plan unlocks advanced features like unlimited alerts, faster refresh rates, and API access. You can upgrade from your Account Settings.'
    },
    {
      question: 'How do I manage my API keys?',
      answer: 'Go to the Developer API section to create, manage, and monitor your API keys. You can set different access levels and rate limits for each key.'
    },
    {
      question: 'Is my data secure?',
      answer: 'Yes, we use industry-standard encryption and security practices. We never store your private keys and all data is encrypted in transit and at rest.'
    }
  ]

  const supportTickets: Array<{
    id: string
    subject: string
    status: 'open' | 'in_progress' | 'resolved'
    created: string
  }> = []

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open': return 'red'
      case 'in_progress': return 'blue'
      case 'resolved': return 'green'
      default: return 'gray'
    }
  }

  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        {/* Header */}
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Title order={1} c="#0F172A" mb="md">How can we help you?</Title>
          <Text c="#475569" size="lg" mb="xl">
            Search our knowledge base or get in touch with our support team
          </Text>
          <TextInput
            placeholder="Search for answers..."
            leftSection={<IconSearch size={20} />}
            size="lg"
            radius="md"
            style={{ maxWidth: 600, margin: '0 auto' }}
          />
        </div>

        <Tabs value={activeTab} onChange={setActiveTab}>
          <Tabs.List justify="center">
            <Tabs.Tab value="faq">FAQ</Tabs.Tab>
            <Tabs.Tab value="docs">Documentation</Tabs.Tab>
            <Tabs.Tab value="support">Contact Support</Tabs.Tab>
            <Tabs.Tab value="tickets">My Tickets</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="faq" pt="xl">
            <Grid>
              <Grid.Col span={{ base: 12, lg: 8 }} offset={{ lg: 2 }}>
                <Card padding="xl" radius="md" withBorder>
                  <Title order={3} mb="xl">Frequently Asked Questions</Title>
                  <Accordion variant="separated" radius="md">
                    {faqs.map((faq, index) => (
                      <Accordion.Item key={index} value={index.toString()} mb="sm">
                        <Accordion.Control icon={<IconQuestionMark size={16} color="#2563EB" />}>
                          <Text fw={500}>{faq.question}</Text>
                        </Accordion.Control>
                        <Accordion.Panel>
                          <Text size="sm" c="#475569" lh={1.6}>{faq.answer}</Text>
                        </Accordion.Panel>
                      </Accordion.Item>
                    ))}
                  </Accordion>
                </Card>
              </Grid.Col>
            </Grid>
          </Tabs.Panel>

          <Tabs.Panel value="docs" pt="xl">
            <SimpleGrid cols={{ base: 1, md: 2, lg: 3 }} spacing="lg">
              <Card padding="lg" radius="md" withBorder>
                <ThemeIcon size={48} radius="md" variant="light" color="blue" mb="md">
                  <IconBook size={24} />
                </ThemeIcon>
                <Title order={4} mb="xs">Getting Started</Title>
                <Text size="sm" c="#64748B" mb="lg">
                  Learn the basics of setting up your account and connecting wallets.
                </Text>
                <Button variant="light" fullWidth rightSection={<IconChevronRight size={16} />}>
                  Read Guide
                </Button>
              </Card>

              <Card padding="lg" radius="md" withBorder>
                <ThemeIcon size={48} radius="md" variant="light" color="green" mb="md">
                  <IconLifebuoy size={24} />
                </ThemeIcon>
                <Title order={4} mb="xs">Troubleshooting</Title>
                <Text size="sm" c="#64748B" mb="lg">
                  Solutions to common issues and error messages.
                </Text>
                <Button variant="light" fullWidth rightSection={<IconChevronRight size={16} />}>
                  View Solutions
                </Button>
              </Card>

              <Card padding="lg" radius="md" withBorder>
                <ThemeIcon size={48} radius="md" variant="light" color="teal" mb="md">
                  <IconExternalLink size={24} />
                </ThemeIcon>
                <Title order={4} mb="xs">API Reference</Title>
                <Text size="sm" c="#64748B" mb="lg">
                  Complete documentation for developers and integrators.
                </Text>
                <Button variant="light" fullWidth rightSection={<IconChevronRight size={16} />}>
                  API Docs
                </Button>
              </Card>
            </SimpleGrid>
          </Tabs.Panel>

          <Tabs.Panel value="support" pt="xl">
            <Grid>
              <Grid.Col span={{ base: 12, lg: 8 }}>
                <Card padding="xl" radius="md" withBorder>
                  <Title order={3} mb="md">Send us a message</Title>
                  <Text c="#64748B" mb="xl">
                    We typically respond within 24 hours.
                  </Text>

                  <Stack gap="md">
                    <Group grow>
                      <TextInput label="Name" placeholder="Your name" />
                      <TextInput label="Email" placeholder="your@email.com" />
                    </Group>
                    <TextInput label="Subject" placeholder="How can we help?" />
                    <Textarea label="Message" placeholder="Describe your issue..." minRows={5} />
                    <Group justify="flex-end">
                      <Button size="md" color="blue">Send Message</Button>
                    </Group>
                  </Stack>
                </Card>
              </Grid.Col>

              <Grid.Col span={{ base: 12, lg: 4 }}>
                <Stack gap="md">
                  <Card padding="lg" radius="md" withBorder>
                    <Title order={4} mb="md">Other ways to connect</Title>
                    <Stack gap="md">
                      <Button
                        variant="default"
                        fullWidth
                        leftSection={<IconMail size={16} />}
                        justify="flex-start"
                      >
                        support@ekko.com
                      </Button>
                      <Button
                        variant="default"
                        fullWidth
                        leftSection={<IconBrandTwitter size={16} />}
                        justify="flex-start"
                      >
                        @EkkoSupport
                      </Button>
                      <Button
                        variant="default"
                        fullWidth
                        leftSection={<IconBrandDiscord size={16} />}
                        justify="flex-start"
                      >
                        Join Discord Community
                      </Button>
                    </Stack>
                  </Card>

                  <Alert icon={<IconAlertCircle size={16} />} title="System Status" color="green" variant="light">
                    All systems operational.
                  </Alert>
                </Stack>
              </Grid.Col>
            </Grid>
          </Tabs.Panel>

          <Tabs.Panel value="tickets" pt="xl">
            <Stack gap="md">
              {supportTickets.length === 0 ? (
                <Card padding="lg" radius="md" withBorder>
                  <Stack align="center" gap="xs">
                    <ThemeIcon size={48} radius="md" variant="light" color="blue">
                      <IconLifebuoy size={24} />
                    </ThemeIcon>
                    <Text fw={600}>No support tickets yet</Text>
                    <Text size="sm" c="#64748B" ta="center" maw={360}>
                      Submit a request in the Contact Support tab and your ticket will appear here.
                    </Text>
                    <Button variant="light" onClick={() => setActiveTab('support')}>
                      Contact Support
                    </Button>
                  </Stack>
                </Card>
              ) : (
                supportTickets.map((ticket) => (
                  <Card key={ticket.id} padding="lg" radius="md" withBorder>
                    <Group justify="space-between" align="flex-start">
                      <div>
                        <Group gap="sm" mb="xs">
                          <Text fw={600} c="#0F172A">{ticket.subject}</Text>
                          <Badge color={getStatusColor(ticket.status)} variant="light">
                            {ticket.status.replace('_', ' ')}
                          </Badge>
                        </Group>
                        <Text size="sm" c="#64748B">Ticket ID: {ticket.id} • Created {ticket.created}</Text>
                      </div>
                      <Button variant="subtle" size="sm">View Thread</Button>
                    </Group>
                  </Card>
                ))
              )}
            </Stack>
          </Tabs.Panel>
        </Tabs>
      </Stack>
    </Container>
  )
}
