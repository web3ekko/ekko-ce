import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Title,
  Text,
  Card,
  Stack,
  Badge,
  Group,
  Button,
  TextInput,
  Textarea,
  Switch,
  Select,
  Loader,
  Grid,
  Tabs,
  Divider,
  Alert as MantineAlert,
  Code,
  Paper,
  ActionIcon,
  NumberInput,
  Radio,
  Box,
  Center as MantineCenter,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useForm } from '@mantine/form';
import {
  IconEdit,
  IconCheck,
  IconX,
  IconArrowLeft,
  IconTrash,
  IconRefresh,
  IconChartBar,
  IconCurrencyDollar,
  IconBell,
} from '@tabler/icons-react';

import { AlertService } from '@/services/alert/alert.service';
import { WalletService } from '@/services/wallet/wallet.service';
import type { Alert, AlertFormValues } from '@/@types/alert';
import type { Wallet } from '@/@types/wallet';

export default function AlertDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [alert, setAlert] = useState<Alert | null>(null);
  const [jobspec, setJobspec] = useState<any>(null);
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [loading, setLoading] = useState(true);
  const [jobspecLoading, setJobspecLoading] = useState(true);
  const [generatingJobSpec, setGeneratingJobSpec] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<string | null>('details');

  const form = useForm<AlertFormValues>({
    initialValues: {
      type: 'Price',
      message: '',
      priority: 'Medium',
      related_wallet_id: '',
      query: '',
      threshold: 10,
      enableNotifications: true,
    },
    validate: {
      message: (value) => (value.trim().length < 1 ? 'Alert message is required' : null),
      related_wallet_id: (value, values) => {
        // Make related_wallet required only for Transaction alerts
        if (values.type === 'Transaction' && (!value || value.trim() === '')) {
          return 'A wallet is required for transaction alerts';
        }
        return null;
      },
    },
  });

  // Helper function to get alert icon based on type
  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'Price':
        return <IconChartBar size={18} />;
      case 'Transaction':
        return <IconCurrencyDollar size={18} />;
      default:
        return <IconBell size={18} />;
    }
  };

  // Helper function to get priority color
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'High':
        return 'red';
      case 'Medium':
        return 'yellow';
      case 'Low':
        return 'blue';
      default:
        return 'gray';
    }
  };

  // Fetch alert and jobspec data
  const fetchAlertData = async () => {
    if (!id) return;

    try {
      setLoading(true);
      const alertData = await AlertService.getAlert(id);
      setAlert(alertData);

      // Initialize form with alert data
      form.setValues({
        type: alertData.type || 'Price',
        message: alertData.message || '',
        priority: alertData.priority || 'Medium',
        related_wallet_id: alertData.related_wallet_id || '',
        query: alertData.query || '',
        threshold: parseFloat(alertData.query?.match(/[0-9.]+/)?.[0] || '10'),
        enableNotifications: alertData.notifications_enabled !== false,
      });

      setError(null);
    } catch (err) {
      console.error('Error fetching alert:', err);
      setError('Failed to load alert details. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Fetch jobspec data
  const fetchJobspec = async () => {
    if (!id) return;

    try {
      setJobspecLoading(true);
      const data = await AlertService.getAlertJobspec(id);
      setJobspec(data);
    } catch (err) {
      console.error('Error fetching jobspec:', err);
      // Don't set error state, just log it - jobspec isn't critical
    } finally {
      setJobspecLoading(false);
    }
  };

  // Generate job spec
  const handleGenerateJobSpec = async () => {
    if (!id) return;

    try {
      setGeneratingJobSpec(true);
      const result = await AlertService.generateJobSpec(id);

      // Update local state with the new job spec
      setJobspec(result);

      // Set the active tab to jobspec to show the result
      setActiveTab('jobspec');

      // Show success notification
      notifications.show({
        title: 'Success',
        message: 'Job specification was successfully generated',
        color: 'green',
      });
    } catch (err) {
      console.error('Error generating job spec:', err);
      setError('Failed to generate job specification. Please try again.');
    } finally {
      setGeneratingJobSpec(false);
    }
  };

  // Fetch wallets
  const fetchWallets = async () => {
    try {
      const data = await WalletService.getWallets();
      setWallets(data);
    } catch (err) {
      console.error('Error fetching wallets:', err);
    }
  };

  // Initialize data on component mount
  useEffect(() => {
    fetchAlertData();
    fetchJobspec();
    fetchWallets();
  }, [id]);

  // Handle form submission to update alert
  const handleSubmit = async (values: AlertFormValues) => {
    if (!alert || !id) return;

    try {
      setSaving(true);

      // Create alert update object
      const updatedAlert = {
        id: id,
        type: values.type,
        message: values.message,
        time: alert.time,
        status: alert.status,
        priority: values.priority,
        related_wallet_id: values.related_wallet_id,
        query: values.query,
        notifications_enabled: values.enableNotifications,
      };

      await AlertService.updateAlert(id, updatedAlert);

      // Refresh alert data and exit edit mode
      await fetchAlertData();
      await fetchJobspec(); // Refresh jobspec too as it depends on alert data
      setEditing(false);
      setError(null);
    } catch (err: any) {
      console.error('Error updating alert:', err);
      setError(err.message || 'Failed to update alert. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  // Helper function to update threshold and message when type changes
  const updateAlertMessage = (type: string, threshold: number, walletId: string) => {
    let message = '';
    let query = '';

    // Get wallet info
    const selectedWallet = wallets.find((w) => w.id === walletId);
    const walletName = selectedWallet
      ? selectedWallet.name || 'selected wallet'
      : 'selected wallet';
    const cryptoSymbol = selectedWallet ? selectedWallet.blockchain_symbol : 'AVAX';

    // Format wallet name
    let formattedWalletName = walletName;
    if (
      formattedWalletName &&
      !formattedWalletName.includes('(') &&
      !formattedWalletName.includes('Wallet')
    ) {
      formattedWalletName = `${formattedWalletName} (Wallet)`;
    }

    switch (type) {
      case 'Price':
        message = `Alert when price changes by ${threshold}%`;
        query = `price_change > ${threshold}%`;
        break;
      case 'Transaction':
        message = `Alert on transactions above ${threshold} ${cryptoSymbol} in ${formattedWalletName}`;
        query = `tx_value > ${threshold}`;
        break;
      default:
        message = 'Custom alert';
        query = '';
    }

    form.setFieldValue('message', message);
    form.setFieldValue('query', query);
  };

  // Handle delete alert
  const handleDelete = async () => {
    if (!id || !window.confirm('Are you sure you want to delete this alert?')) return;

    try {
      setLoading(true);
      await AlertService.deleteAlert(id);
      navigate('/ekko/alerts');
    } catch (err) {
      console.error('Error deleting alert:', err);
      setError('Failed to delete alert. Please try again.');
      setLoading(false);
    }
  };

  if (loading && !alert) {
    return (
      <Card withBorder p="xl">
        <MantineCenter mt="xl" mb="xl">
          <Loader size="lg" />
        </MantineCenter>
      </Card>
    );
  }

  if (error && !alert) {
    return (
      <Card withBorder p="xl">
        <MantineAlert color="red" title="Error" mb="md">
          {error}
        </MantineAlert>
        <Group justify="center">
          <Button onClick={() => navigate('/ekko/alerts')}>Back to Alerts</Button>
        </Group>
      </Card>
    );
  }

  return (
    <div>
      <Group justify="space-between" mb="md">
        <Group>
          <ActionIcon variant="light" onClick={() => navigate('/ekko/alerts')}>
            <IconArrowLeft size={16} />
          </ActionIcon>
          <Title order={3}>Alert Details</Title>
        </Group>

        <Group>
          <ActionIcon
            variant="light"
            color="blue"
            onClick={() => {
              fetchAlertData();
              fetchJobspec();
            }}
            title="Refresh"
          >
            <IconRefresh size={16} />
          </ActionIcon>

          {!editing ? (
            <Button leftSection={<IconEdit size={16} />} onClick={() => setEditing(true)}>
              Edit
            </Button>
          ) : (
            <Group>
              <Button
                variant="light"
                color="gray"
                leftSection={<IconX size={16} />}
                onClick={() => {
                  setEditing(false);
                  fetchAlertData(); // Reset form
                }}
              >
                Cancel
              </Button>
              <Button
                color="blue"
                leftSection={<IconCheck size={16} />}
                type="submit"
                form="alert-edit-form"
                loading={saving}
              >
                Save
              </Button>
            </Group>
          )}

          <Button
            color="red"
            variant="light"
            leftSection={<IconTrash size={16} />}
            onClick={handleDelete}
          >
            Delete
          </Button>
        </Group>
      </Group>

      {error && (
        <MantineAlert
          color="red"
          title="Error"
          mb="md"
          withCloseButton
          onClose={() => setError(null)}
        >
          {error}
        </MantineAlert>
      )}

      <Card withBorder mb="md">
        <Tabs value={activeTab} onChange={setActiveTab}>
          <Tabs.List>
            <Tabs.Tab value="details">Details</Tabs.Tab>
            <Tabs.Tab value="jobspec">Job Specification</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="details" pt="md">
            {editing ? (
              <form id="alert-edit-form" onSubmit={form.onSubmit(handleSubmit)}>
                <Stack gap="md">
                  <Radio.Group
                    label="Alert Type"
                    description="Select the type of alert you want to create"
                    {...form.getInputProps('type')}
                    onChange={(value) => {
                      form.setFieldValue('type', value);
                      updateAlertMessage(
                        value,
                        form.values.threshold,
                        form.values.related_wallet_id
                      );
                    }}
                  >
                    <Group mt="xs">
                      <Radio value="Price" label="Price Alert" />
                      <Radio value="Transaction" label="Transaction Alert" />
                    </Group>
                  </Radio.Group>

                  <Select
                    label="Related Wallet"
                    placeholder="Select wallet (optional)"
                    data={[
                      { value: '', label: 'None' },
                      ...wallets.map((wallet) => ({
                        value: wallet.id,
                        label: `${wallet.name || 'Wallet'} (${wallet.blockchain_symbol}) - ${wallet.address.substring(0, 6)}...${wallet.address.substring(wallet.address.length - 4)}`,
                      })),
                    ]}
                    clearable
                    error={form.errors.related_wallet_id}
                    {...form.getInputProps('related_wallet_id')}
                    onChange={(value: string | null) => {
                      form.setFieldValue('related_wallet_id', value || '');
                      updateAlertMessage(form.values.type, form.values.threshold, value || '');
                    }}
                  />

                  <div>
                    <Text size="sm" fw={500} mb="xs">
                      Threshold {form.values.type === 'Price' ? '(%)' : '(Amount)'}
                    </Text>
                    <NumberInput
                      min={1}
                      max={form.values.type === 'Price' ? 50 : 100}
                      step={form.values.type === 'Price' ? 1 : 5}
                      label={`${form.values.type === 'Price' ? 'Percent change' : 'Transaction amount'}`}
                      {...form.getInputProps('threshold')}
                      onChange={(value: string | number) => {
                        const numValue =
                          typeof value === 'string' ? parseFloat(value) || 10 : value || 10;
                        form.setFieldValue('threshold', numValue);
                        updateAlertMessage(
                          form.values.type,
                          numValue,
                          form.values.related_wallet_id
                        );
                      }}
                    />
                  </div>

                  <Radio.Group label="Priority" {...form.getInputProps('priority')}>
                    <Group mt="xs">
                      <Radio value="Low" label="Low" />
                      <Radio value="Medium" label="Medium" />
                      <Radio value="High" label="High" />
                    </Group>
                  </Radio.Group>

                  <Textarea
                    label="Alert Message"
                    placeholder="Alert description"
                    required
                    minRows={2}
                    error={form.errors.message}
                    {...form.getInputProps('message')}
                  />

                  <Textarea
                    label="Query Condition"
                    placeholder="Condition that triggers this alert"
                    required
                    minRows={2}
                    {...form.getInputProps('query')}
                  />

                  <Switch
                    label="Enable Notifications"
                    description="Receive notifications when this alert is triggered"
                    checked={form.values.enableNotifications}
                    onChange={(event) =>
                      form.setFieldValue('enableNotifications', event.currentTarget.checked)
                    }
                  />
                </Stack>
              </form>
            ) : alert ? (
              <Grid>
                <Grid.Col span={6}>
                  <Stack>
                    <Group>
                      <Text fw={700}>Type:</Text>
                      <Group>
                        {getAlertIcon(alert.type)}
                        <Text>{alert.type}</Text>
                      </Group>
                    </Group>

                    <Group>
                      <Text fw={700}>Message:</Text>
                      <Text
                        p="xs"
                        bg={
                          alert.type === 'Price'
                            ? 'rgba(25, 113, 194, 0.1)'
                            : 'rgba(255, 151, 0, 0.1)'
                        }
                        style={{
                          borderRadius: '4px',
                          fontWeight: 500,
                          color: alert.type === 'Price' ? '#1864ab' : '#d97706',
                        }}
                      >
                        {alert.message}
                      </Text>
                    </Group>

                    <Group>
                      <Text fw={700}>Status:</Text>
                      <Badge color={alert.status === 'Open' ? 'blue' : 'green'}>
                        {alert.status}
                      </Badge>
                    </Group>

                    <Group>
                      <Text fw={700}>Priority:</Text>
                      <Badge color={getPriorityColor(alert.priority || 'Medium')}>
                        {alert.priority || 'Medium'}
                      </Badge>
                    </Group>
                  </Stack>
                </Grid.Col>

                <Grid.Col span={6}>
                  <Stack>
                    <Group>
                      <Text fw={700}>Created:</Text>
                      <Text>{new Date(alert.time).toLocaleString()}</Text>
                    </Group>

                    <Group>
                      <Text fw={700}>Related Wallet:</Text>
                      <Text>
                        {(() => {
                          if (alert.related_wallet_id) {
                            const wallet = wallets.find((w) => w.id === alert.related_wallet_id);
                            if (wallet) {
                              return `${wallet.name || wallet.blockchain_symbol} (${wallet.address.substring(0, 6)}...${wallet.address.substring(wallet.address.length - 4)})`;
                            }
                            return `Wallet ID: ${alert.related_wallet_id}`;
                          }
                          return 'None';
                        })()}
                      </Text>
                    </Group>

                    <Group>
                      <Text fw={700}>Notifications:</Text>
                      <Badge color={alert.notifications_enabled !== false ? 'green' : 'gray'}>
                        {alert.notifications_enabled !== false ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </Group>

                    <Group>
                      <Text fw={700}>Query Condition:</Text>
                      <Paper p="xs" withBorder style={{ fontFamily: 'monospace' }}>
                        {alert.query || 'No condition specified'}
                      </Paper>
                    </Group>
                  </Stack>
                </Grid.Col>
              </Grid>
            ) : null}
          </Tabs.Panel>

          <Tabs.Panel value="jobspec" pt="md">
            <Group justify="space-between" mb="md">
              <Text fw={700}>Job Specification</Text>
              <Button
                leftSection={<IconRefresh size={16} />}
                color="blue"
                onClick={handleGenerateJobSpec}
                loading={generatingJobSpec}
                disabled={loading || jobspecLoading}
              >
                Generate Job Spec
              </Button>
            </Group>
            {jobspecLoading || generatingJobSpec ? (
              <Box
                p="xl"
                style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}
              >
                <Loader />
              </Box>
            ) : jobspec ? (
              <Stack>
                <Group>
                  <Text fw={700}>Job Name:</Text>
                  <Text>{jobspec.jobspec?.job_name || 'Unnamed Job'}</Text>
                </Group>

                <Group>
                  <Text fw={700}>Schedule:</Text>
                  <Text>{jobspec.jobspec?.schedule || 'Not specified'}</Text>
                </Group>

                <Divider my="sm" />

                <Text fw={700}>Job Specification:</Text>
                <Paper p="md" withBorder style={{ maxHeight: '500px', overflow: 'auto' }}>
                  <Code block>{jobspec.prettified}</Code>
                </Paper>
              </Stack>
            ) : (
              <Stack align="center" p="xl">
                <Text>No job specification available for this alert.</Text>
                <Button onClick={fetchJobspec}>Try Again</Button>
              </Stack>
            )}
          </Tabs.Panel>
        </Tabs>
      </Card>
    </div>
  );
}

// No longer needed as we're using Mantine's Center component
