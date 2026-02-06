/**
 * Billing & Subscription Page
 *
 * Subscription management, usage tracking, and billing information
 * with OpenRouter-inspired light theme design
 */

import { useEffect, useState } from 'react'
import {
  Container,
  Title,
  Text,
  Button,
  Group,
  Stack,
  Card,
  Grid,
  Paper,
  Badge,
  ThemeIcon,
  Progress,
  Table,
  Tabs,
  Divider,
  Alert,
  Box,
  List,
  ActionIcon,
  Tooltip,
  Loader,
} from '@mantine/core'
import {
  IconCreditCard,
  IconReceipt,
  IconChartBar,
  IconRocket,
  IconCheck,
  IconX,
  IconAlertCircle,
  IconDownload,
  IconExternalLink,
  IconBolt,
  IconBell,
  IconWallet,
  IconClock,
  IconCalendar,
  IconArrowRight,
} from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import billingApiService, { type BillingOverview, type BillingPlan } from '../../services/billing-api'


export function BillingPage() {
  const [selectedTab, setSelectedTab] = useState<string | null>('overview')
  const [overview, setOverview] = useState<BillingOverview | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    const loadBilling = async () => {
      setIsLoading(true)
      setLoadError(null)
      try {
        const response = await billingApiService.getOverview()
        setOverview(response)
      } catch (error) {
        console.error('Failed to load billing overview:', error)
        setLoadError('Failed to load billing data')
      } finally {
        setIsLoading(false)
      }
    }

    loadBilling()
  }, [])

  const currentPlan = overview?.subscription.plan
  const usage = overview?.usage
  const invoices = overview?.invoices || []
  const plans = overview?.plans || []

  const handleUpgrade = async (plan: BillingPlan) => {
    try {
      const subscription = await billingApiService.updateSubscription(plan.id)
      setOverview((prev) => (prev ? { ...prev, subscription } : prev))
      notifications.show({
        title: 'Subscription Updated',
        message: `You are now on the ${plan.name} plan.`,
        color: 'blue',
        icon: <IconRocket size={16} />,
      })
    } catch (error) {
      console.error('Failed to update subscription:', error)
      notifications.show({
        title: 'Update failed',
        message: 'Could not update your subscription. Please try again.',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    }
  }

  const handleDownloadInvoice = (invoiceId: string) => {
    notifications.show({
      title: 'Download Started',
      message: `Downloading invoice ${invoiceId}...`,
      color: 'blue',
      icon: <IconDownload size={16} />,
    })
  }

  const getUsageColor = (percent: number, unlimited: boolean) => {
    if (unlimited) return 'blue'
    if (percent >= 90) return 'red'
    if (percent >= 75) return 'orange'
    return 'blue'
  }

  if (isLoading) {
    return (
      <Container size="xl" py="xl">
        <Center h={320}>
          <Stack align="center" gap="sm">
            <Loader size="lg" />
            <Text c="dimmed">Loading billing data...</Text>
          </Stack>
        </Center>
      </Container>
    )
  }

  if (loadError || !overview || !currentPlan || !usage) {
    return (
      <Container size="xl" py="xl">
        <Alert icon={<IconAlertCircle size={18} />} color="red" title="Billing unavailable">
          {loadError || 'Unable to load billing details.'}
        </Alert>
      </Container>
    )
  }

  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        {/* Header */}
        <Group justify="space-between">
          <div>
            <Title order={1} c="#0F172A">Billing & Subscription</Title>
            <Text c="#475569" mt="xs">
              Manage your subscription, view usage, and download invoices
            </Text>
          </div>
          <Button
            leftSection={<IconCreditCard size={16} />}
            variant="light"
            color="blue"
          >
            Update Payment Method
          </Button>
        </Group>

        {/* Current Plan Card */}
        <Paper
          p="xl"
          radius="md"
          style={{
            background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
            color: 'white',
          }}
        >
          <Grid align="center">
            <Grid.Col span={{ base: 12, md: 8 }}>
              <Group gap="md">
                <ThemeIcon size={48} radius="md" color="white" variant="light">
                  <IconRocket size={24} color="#2563EB" />
                </ThemeIcon>
                <div>
                  <Text size="sm" opacity={0.9}>Current Plan</Text>
                  <Title order={2}>{currentPlan.name}</Title>
                </div>
              </Group>
              <Group gap="xl" mt="lg">
                <div>
                  <Text size="sm" opacity={0.9}>Monthly Cost</Text>
                  <Text size="xl" fw={700}>${currentPlan.price_usd}/{currentPlan.billing_cycle === 'yearly' ? 'yr' : 'mo'}</Text>
                </div>
                <Divider orientation="vertical" color="rgba(255,255,255,0.3)" />
                <div>
                  <Text size="sm" opacity={0.9}>Next Billing Date</Text>
                  <Text size="xl" fw={700}>
                    {new Date(overview.subscription.current_period_end).toLocaleDateString()}
                  </Text>
                </div>
                <Divider orientation="vertical" color="rgba(255,255,255,0.3)" />
                <div>
                  <Text size="sm" opacity={0.9}>Status</Text>
                  <Badge color="green" variant="filled" size="lg">
                    Active
                  </Badge>
                </div>
              </Group>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 4 }}>
              <Stack gap="xs" align="flex-end">
                <Button color="white" variant="white" c="#2563EB">
                  Upgrade Plan
                </Button>
                <Button variant="subtle" color="white">
                  Cancel Subscription
                </Button>
              </Stack>
            </Grid.Col>
          </Grid>
        </Paper>

        {/* Tabs */}
        <Tabs value={selectedTab} onChange={setSelectedTab} color="blue">
          <Tabs.List>
            <Tabs.Tab value="overview" leftSection={<IconChartBar size={16} />}>
              Usage Overview
            </Tabs.Tab>
            <Tabs.Tab value="plans" leftSection={<IconRocket size={16} />}>
              Plans
            </Tabs.Tab>
            <Tabs.Tab value="invoices" leftSection={<IconReceipt size={16} />}>
              Invoices
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="overview" pt="md">
            <Grid>
              {/* Usage Cards */}
              <Grid.Col span={{ base: 12, md: 6 }}>
                <Card
                  padding="lg"
                  radius="md"
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid #E6E9EE',
                  }}
                >
                  <Group justify="space-between" mb="md">
                    <Group gap="xs">
                      <ThemeIcon size="md" radius="md" color="blue" variant="light">
                        <IconBell size={16} />
                      </ThemeIcon>
                      <Text fw={600} c="#0F172A">Alerts</Text>
                    </Group>
                    <Badge color={getUsageColor(usage.alerts.percent, usage.alerts.unlimited)} variant="light">
                      {usage.alerts.unlimited ? 'Unlimited' : `${usage.alerts.percent}% used`}
                    </Badge>
                  </Group>
                  <Progress
                    value={usage.alerts.unlimited ? 0 : usage.alerts.percent}
                    color={getUsageColor(usage.alerts.percent, usage.alerts.unlimited)}
                    size="lg"
                    radius="xl"
                    mb="xs"
                  />
                  <Text size="sm" c="#475569">
                    {usage.alerts.unlimited
                      ? `${usage.alerts.used.toLocaleString()} alerts this month`
                      : `${usage.alerts.used.toLocaleString()} / ${usage.alerts.limit.toLocaleString()} alerts this month`}
                  </Text>
                </Card>
              </Grid.Col>

              <Grid.Col span={{ base: 12, md: 6 }}>
                <Card
                  padding="lg"
                  radius="md"
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid #E6E9EE',
                  }}
                >
                  <Group justify="space-between" mb="md">
                    <Group gap="xs">
                      <ThemeIcon size="md" radius="md" color="blue" variant="light">
                        <IconWallet size={16} />
                      </ThemeIcon>
                      <Text fw={600} c="#0F172A">Wallets</Text>
                    </Group>
                    <Badge color={getUsageColor(usage.wallets.percent, usage.wallets.unlimited)} variant="light">
                      {usage.wallets.unlimited ? 'Unlimited' : `${usage.wallets.percent}% used`}
                    </Badge>
                  </Group>
                  <Progress
                    value={usage.wallets.unlimited ? 0 : usage.wallets.percent}
                    color={getUsageColor(usage.wallets.percent, usage.wallets.unlimited)}
                    size="lg"
                    radius="xl"
                    mb="xs"
                  />
                  <Text size="sm" c="#475569">
                    {usage.wallets.unlimited ? `${usage.wallets.used} wallets` : `${usage.wallets.used} / ${usage.wallets.limit} wallets`}
                  </Text>
                </Card>
              </Grid.Col>

              <Grid.Col span={{ base: 12, md: 6 }}>
                <Card
                  padding="lg"
                  radius="md"
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid #E6E9EE',
                  }}
                >
                  <Group justify="space-between" mb="md">
                    <Group gap="xs">
                      <ThemeIcon size="md" radius="md" color="blue" variant="light">
                        <IconBolt size={16} />
                      </ThemeIcon>
                      <Text fw={600} c="#0F172A">API Calls</Text>
                    </Group>
                    <Badge color={getUsageColor(usage.api_calls.percent, usage.api_calls.unlimited)} variant="light">
                      {usage.api_calls.unlimited ? 'Unlimited' : `${usage.api_calls.percent}% used`}
                    </Badge>
                  </Group>
                  <Progress
                    value={usage.api_calls.unlimited ? 0 : usage.api_calls.percent}
                    color={getUsageColor(usage.api_calls.percent, usage.api_calls.unlimited)}
                    size="lg"
                    radius="xl"
                    mb="xs"
                  />
                  <Text size="sm" c="#475569">
                    {usage.api_calls.unlimited
                      ? `${usage.api_calls.used.toLocaleString()} calls this month`
                      : `${usage.api_calls.used.toLocaleString()} / ${usage.api_calls.limit.toLocaleString()} calls this month`}
                  </Text>
                </Card>
              </Grid.Col>

              <Grid.Col span={{ base: 12, md: 6 }}>
                <Card
                  padding="lg"
                  radius="md"
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid #E6E9EE',
                  }}
                >
                  <Group justify="space-between" mb="md">
                    <Group gap="xs">
                      <ThemeIcon size="md" radius="md" color="blue" variant="light">
                        <IconClock size={16} />
                      </ThemeIcon>
                      <Text fw={600} c="#0F172A">Notifications</Text>
                    </Group>
                    <Badge color={getUsageColor(usage.notifications.percent, usage.notifications.unlimited)} variant="light">
                      {usage.notifications.unlimited ? 'Unlimited' : `${usage.notifications.percent}% used`}
                    </Badge>
                  </Group>
                  <Progress
                    value={usage.notifications.unlimited ? 0 : usage.notifications.percent}
                    color={getUsageColor(usage.notifications.percent, usage.notifications.unlimited)}
                    size="lg"
                    radius="xl"
                    mb="xs"
                  />
                  <Text size="sm" c="#475569">
                    {usage.notifications.unlimited
                      ? `${usage.notifications.used.toLocaleString()} notifications this month`
                      : `${usage.notifications.used.toLocaleString()} / ${usage.notifications.limit.toLocaleString()} notifications this month`}
                  </Text>
                </Card>
              </Grid.Col>

              {/* Usage Alert */}
              {!usage.alerts.unlimited && usage.alerts.percent >= 75 && (
                <Grid.Col span={12}>
                  <Alert
                    color="orange"
                    icon={<IconAlertCircle size={16} />}
                    title="Approaching Alert Limit"
                  >
                    You've used {usage.alerts.percent}% of your monthly alert quota.
                    Consider upgrading to avoid interruptions.
                    <Button size="xs" variant="light" color="orange" ml="md">
                      Upgrade Now
                    </Button>
                  </Alert>
                </Grid.Col>
              )}
            </Grid>
          </Tabs.Panel>

          <Tabs.Panel value="plans" pt="md">
            <Grid>
              {plans.map((plan) => {
                const isCurrent = plan.id === currentPlan.id
                const isPopular = plan.slug === 'pro'
                return (
                  <Grid.Col key={plan.id} span={{ base: 12, md: 4 }}>
                    <Card
                      padding="lg"
                      radius="md"
                      style={{
                        background: '#FFFFFF',
                        border: isCurrent ? '2px solid #2563EB' : '1px solid #E6E9EE',
                        height: '100%',
                        position: 'relative',
                      }}
                    >
                      {isPopular && (
                        <Badge
                          color="blue"
                          style={{
                            position: 'absolute',
                            top: -10,
                            right: 16,
                          }}
                        >
                          Most Popular
                        </Badge>
                      )}
                      <Stack gap="md">
                        <div>
                          <Text fw={600} size="lg" c="#0F172A">{plan.name}</Text>
                          <Group gap={4} align="baseline" mt="xs">
                            <Text size="xl" fw={700} c="#0F172A">${plan.price_usd}</Text>
                            <Text size="sm" c="#475569">/{plan.billing_cycle === 'yearly' ? 'year' : 'month'}</Text>
                          </Group>
                        </div>

                        <Divider />

                        <List
                          spacing="sm"
                          size="sm"
                          icon={
                            <ThemeIcon size={20} radius="xl" color="green" variant="light">
                              <IconCheck size={12} />
                            </ThemeIcon>
                          }
                        >
                          {plan.features.map((feature) => (
                            <List.Item key={feature}>
                              <Text size="sm" c="#374151">{feature}</Text>
                            </List.Item>
                          ))}
                        </List>

                        {plan.not_included.length > 0 && (
                          <List
                            spacing="sm"
                            size="sm"
                            icon={
                              <ThemeIcon size={20} radius="xl" color="gray" variant="light">
                                <IconX size={12} />
                              </ThemeIcon>
                            }
                          >
                            {plan.not_included.map((feature) => (
                              <List.Item key={feature}>
                                <Text size="sm" c="#9CA3AF">{feature}</Text>
                              </List.Item>
                            ))}
                          </List>
                        )}

                        <Box mt="auto">
                          {isCurrent ? (
                            <Button fullWidth disabled variant="light" color="gray">
                              Current Plan
                            </Button>
                          ) : (
                            <Button
                              fullWidth
                              color="blue"
                              variant={plan.price_usd > currentPlan.price_usd ? 'filled' : 'light'}
                              onClick={() => handleUpgrade(plan)}
                            >
                              {plan.price_usd > currentPlan.price_usd ? 'Upgrade' : 'Downgrade'}
                            </Button>
                          )}
                        </Box>
                      </Stack>
                    </Card>
                  </Grid.Col>
                )
              })}
            </Grid>
          </Tabs.Panel>

          <Tabs.Panel value="invoices" pt="md">
            <Card
              padding="lg"
              radius="md"
              style={{
                background: '#FFFFFF',
                border: '1px solid #E6E9EE',
              }}
            >
              <Title order={4} c="#0F172A" mb="md">Invoice History</Title>
              <Table verticalSpacing="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Invoice</Table.Th>
                    <Table.Th>Date</Table.Th>
                    <Table.Th>Amount</Table.Th>
                    <Table.Th>Status</Table.Th>
                    <Table.Th>Actions</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {invoices.map((invoice) => (
                    <Table.Tr key={invoice.id}>
                      <Table.Td>
                        <Text size="sm" fw={500} c="#0F172A">{invoice.id}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" c="#475569">
                          {new Date(invoice.billed_at).toLocaleDateString()}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" fw={500} c="#0F172A">
                          ${invoice.amount_usd.toFixed(2)}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Badge
                          color={invoice.status === 'paid' ? 'green' : 'orange'}
                          variant="light"
                        >
                          {invoice.status.charAt(0).toUpperCase() + invoice.status.slice(1)}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Group gap="xs">
                          <Tooltip label="Download PDF">
                            <ActionIcon
                              variant="subtle"
                              color="gray"
                              onClick={() => handleDownloadInvoice(invoice.id)}
                            >
                              <IconDownload size={16} />
                            </ActionIcon>
                          </Tooltip>
                          <Tooltip label="View Details">
                            <ActionIcon variant="subtle" color="gray">
                              <IconExternalLink size={16} />
                            </ActionIcon>
                          </Tooltip>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Card>
          </Tabs.Panel>
        </Tabs>
      </Stack>
    </Container>
  )
}
