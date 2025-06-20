import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Title,
  Text,
  Card,
  Stack,
  Badge,
  Group,
  Button,
  TextInput,
  Pagination,
  Select,
  ActionIcon,
  Tabs,
  Divider,
  Modal,
  Textarea,
  NumberInput,
  Radio,
  Slider,
  Switch,
  Center,
  Loader,
  Alert as MantineAlert,
  Grid,
  Tooltip,
  Stepper,
  Box,
  SegmentedControl,
} from '@mantine/core';
import { IOSCard, IOSPageWrapper } from '@/components/UI/IOSCard';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import {
  IconSearch,
  IconPlus,
  IconRefresh,
  IconBell,
  IconAlertCircle,
  IconChartBar,
  IconWallet,
  IconCheck,
  IconCurrencyDollar,
  IconShield,
  IconTrash,
  IconX,
  IconArrowsRightLeft,
  IconTrendingUp,
} from '@tabler/icons-react';

// Import services
import { AlertService } from '@/services/alert/alert.service';
import { WalletService } from '@/services/wallet/wallet.service';
import type { Alert as AlertType, AlertFormValues } from '@/@types/alert';
import { AlertType as AlertTypeEnum, AlertCategory } from '@/@types/alert';
import type { Wallet } from '@/@types/wallet';
import { v4 as uuidv4 } from 'uuid';

// Import new alert components
import AlertTypeSelector from '@/components/Alert/AlertTypeSelector';
import ParameterBuilder from '@/components/Alert/ParameterBuilder';
import ScheduleConfiguration from '@/components/Alert/ScheduleConfiguration';
import SmartAlertForm from '@/components/Alert/SmartAlertForm';
import { getAlertTypeConfig, generateQueryFromTemplate, determineDataSources } from '@/configs/alertTypes.config';

// AlertFormValues is now imported from @types/alert

export default function Alerts() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [activePage, setActivePage] = useState(1);
  const [pageSize, setPageSize] = useState('10');
  const [activeTab, setActiveTab] = useState('all');
  const [modalOpened, setModalOpened] = useState(false);
  const [alerts, setAlerts] = useState<AlertType[]>([]);
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingWallets, setLoadingWallets] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [updatingNotification, setUpdatingNotification] = useState<string | null>(null);

  // Stepper state for alert creation wizard
  const [activeStep, setActiveStep] = useState(0);

  // Alert creation mode state
  const [alertMode, setAlertMode] = useState<'smart' | 'advanced'>('smart');

  // Fetch alerts and wallets on component mount
  useEffect(() => {
    fetchAlerts();
    fetchWallets();
  }, []);

  // Function to fetch wallets
  const fetchWallets = async () => {
    try {
      setLoadingWallets(true);
      const data = await WalletService.getWallets();
      setWallets(data);
    } catch (err) {
      console.error('Error fetching wallets:', err);
    } finally {
      setLoadingWallets(false);
    }
  };

  // Helper function to get wallet name or address by ID
  const getWalletInfo = (walletId: string | undefined) => {
    if (!walletId) return 'N/A';

    const wallet = wallets.find((w) => w.id === walletId);
    if (wallet) {
      return wallet.name || wallet.address;
    }
    return walletId; // Return the ID if wallet not found
  };

  // Function to fetch alerts
  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const data = await AlertService.getAlerts();
      setAlerts(data || []);
      setError(null);
    } catch (err) {
      console.error('Error fetching alerts:', err);
      setError('Failed to load alerts. Please try again.');
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  };

  // Function to delete an alert
  const handleDeleteAlert = async (id: string) => {
    try {
      setDeleting(id);
      await AlertService.deleteAlert(id);
      // Refresh alerts list after deletion
      fetchAlerts();
    } catch (err) {
      console.error('Error deleting alert:', err);
      setError('Failed to delete alert. Please try again.');
    } finally {
      setDeleting(null);
    }
  };

  // Function to toggle notifications for an alert (simplified for new schema)
  const handleToggleNotifications = async (alert: AlertType) => {
    try {
      setUpdatingNotification(alert.id);

      // For now, just refresh the alerts list
      // TODO: Implement proper alert update with new schema
      console.log('Toggle notifications for alert:', alert.id);

      // Refresh alerts list
      fetchAlerts();
    } catch (err) {
      console.error('Error updating alert notification status:', err);
      setError('Failed to update notification settings. Please try again.');
    } finally {
      setUpdatingNotification(null);
    }
  };

  // Form for creating a new alert with enhanced schema
  const form = useForm<AlertFormValues>({
    initialValues: {
      type: AlertTypeEnum.WALLET,
      category: AlertCategory.BALANCE,
      name: '',
      description: '',
      query: '',
      parameters: {},
      schedule: {
        type: 'real-time',
        timezone: 'UTC'
      },
      enabled: true,
    },
    validate: {
      name: (value) => (value.trim().length < 1 ? 'Alert name is required' : null),
      query: (value) => (value.trim().length < 1 ? 'Alert condition is required' : null),
    },
  });

  // Enhanced form submission handler
  const handleSubmit = async (values: AlertFormValues) => {
    try {
      setLoading(true);

      // Get selected alert type configuration
      const selectedConfig = getAlertTypeConfig(values.type, values.category);

      if (!selectedConfig) {
        throw new Error('Invalid alert type configuration');
      }

      // Generate natural language query from template and parameters
      const query = generateQueryFromTemplate(selectedConfig.queryTemplate, values.parameters);

      // Create alert object in new format
      const newAlert = {
        id: uuidv4(),
        user_id: "default", // TODO: Get from auth context
        name: values.name,
        description: values.description,
        type: values.type,
        category: values.category,
        condition: {
          query,
          parameters: values.parameters,
          data_sources: determineDataSources(values.type, values.category),
          estimated_frequency: values.schedule.type
        },
        schedule: {
          type: values.schedule.type,
          interval_seconds: values.schedule.interval_seconds,
          cron_expression: values.schedule.cron_expression,
          timezone: values.schedule.timezone
        },
        enabled: values.enabled,
        created_at: new Date().toISOString()
      };

      console.log('Creating new alert:', newAlert);

      // Call the API to create the alert
      await AlertService.createAlert(newAlert);

      // Success handling
      setModalOpened(false);
      setActiveStep(0); // Reset stepper
      form.reset();
      fetchAlerts();
      setError(null);

      // Show success notification
      notifications.show({
        title: 'Alert Created',
        message: `${values.name} has been created successfully`,
        color: 'green',
        icon: <IconCheck size={16} />
      });

    } catch (err: any) {
      console.error('Error creating alert:', err);
      setError(err.message || 'Failed to create alert. Please try again.');

      // Show error notification
      notifications.show({
        title: 'Error',
        message: err.message || 'Failed to create alert',
        color: 'red',
        icon: <IconX size={16} />
      });
    } finally {
      setLoading(false);
    }
  };

  // Handle smart mode alert creation
  const handleSmartAlertCreation = async (inferredAlert: any) => {
    try {
      setLoading(true);

      console.log('Creating smart alert:', inferredAlert);

      // Call the API to create the alert
      await AlertService.createAlert(inferredAlert);

      // Success handling
      setModalOpened(false);
      setActiveStep(0);
      setAlertMode('smart');
      form.reset();
      fetchAlerts();
      setError(null);

      // Show success notification
      notifications.show({
        title: 'Smart Alert Created',
        message: `${inferredAlert.name} has been created successfully`,
        color: 'green',
        icon: <IconCheck size={16} />
      });

    } catch (err: any) {
      console.error('Error creating smart alert:', err);
      setError(err.message || 'Failed to create alert. Please try again.');

      // Show error notification
      notifications.show({
        title: 'Error',
        message: err.message || 'Failed to create alert',
        color: 'red',
        icon: <IconX size={16} />
      });
    } finally {
      setLoading(false);
    }
  };

  // Handle switching from smart to advanced mode
  const handleSwitchToAdvanced = (inferredAlert?: any) => {
    setAlertMode('advanced');

    if (inferredAlert) {
      // Pre-populate form with inferred values
      form.setValues({
        name: inferredAlert.name || '',
        description: inferredAlert.description || '',
        type: inferredAlert.type,
        category: inferredAlert.category,
        parameters: inferredAlert.condition?.parameters || {},
        query: inferredAlert.condition?.query || '',
        schedule: inferredAlert.schedule || {
          type: 'real-time',
          timezone: 'UTC'
        },
        enabled: inferredAlert.enabled ?? true
      });

      // Start at step 1 (parameters) since type is already set
      setActiveStep(1);
    }
  };

  // Helper functions for stepper navigation
  const nextStep = () => setActiveStep((current) => (current < 3 ? current + 1 : current));
  const prevStep = () => setActiveStep((current) => (current > 0 ? current - 1 : current));

  // Helper function to handle alert type selection
  const handleAlertTypeChange = (typeValue: string) => {
    const [type, category] = typeValue.split('-') as [AlertTypeEnum, AlertCategory];
    form.setFieldValue('type', type);
    form.setFieldValue('category', category);

    // Reset parameters when type changes
    form.setFieldValue('parameters', {});
    form.setFieldValue('query', '');

    // Auto-generate name if empty
    const config = getAlertTypeConfig(type, category);
    if (config && !form.values.name) {
      form.setFieldValue('name', config.name);
    }
  };

  // Helper function to handle parameter changes
  const handleParameterChange = (field: string, value: any) => {
    const fieldPath = field.split('.');
    if (fieldPath.length === 2 && fieldPath[0] === 'parameters') {
      form.setFieldValue(`parameters.${fieldPath[1]}`, value);
    } else {
      form.setFieldValue(field, value);
    }

    // Auto-update query when parameters change
    const config = getAlertTypeConfig(form.values.type, form.values.category);
    if (config) {
      const updatedQuery = generateQueryFromTemplate(config.queryTemplate, {
        ...form.values.parameters,
        [fieldPath[1]]: value
      });
      form.setFieldValue('query', updatedQuery);
    }
  };

  // Helper function to validate current step
  const validateStep = (step: number): boolean => {
    switch (step) {
      case 0: // Type selection
        return !!(form.values.type && form.values.category);
      case 1: // Parameters
        const config = getAlertTypeConfig(form.values.type, form.values.category);
        if (!config) return false;

        // Check required parameters
        const requiredParams = config.parameters.filter(p => p.required);
        return requiredParams.every(param => {
          const value = (form.values.parameters as any)[param.name];
          return value !== undefined && value !== null && value !== '';
        });
      case 2: // Schedule
        return !!(form.values.schedule.type && form.values.schedule.timezone);
      default:
        return true;
    }
  };



  // Filter alerts based on search query and active tab
  const filteredAlerts = alerts.filter((alert: AlertType) => {
    const matchesSearch =
      alert.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      alert.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (alert.description && alert.description.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (alert.condition?.query && alert.condition.query.toLowerCase().includes(searchQuery.toLowerCase()));

    if (activeTab === 'all') return matchesSearch;
    if (activeTab === 'open') return matchesSearch && alert.enabled;
    if (activeTab === 'resolved') return matchesSearch && !alert.enabled;

    return matchesSearch;
  });

  // Calculate pagination
  const totalPages = Math.ceil(filteredAlerts.length / parseInt(pageSize));
  const paginatedAlerts = filteredAlerts.slice(
    (activePage - 1) * parseInt(pageSize),
    activePage * parseInt(pageSize)
  );

  // Helper function to get alert icon based on type
  const getAlertIcon = (type: AlertTypeEnum, category: AlertCategory) => {
    if (type === AlertTypeEnum.PRICE) {
      return <IconChartBar size={18} />;
    } else if (type === AlertTypeEnum.WALLET && category === AlertCategory.TRANSACTION) {
      return <IconArrowsRightLeft size={18} />;
    } else if (type === AlertTypeEnum.WALLET && category === AlertCategory.BALANCE) {
      return <IconWallet size={18} />;
    } else if (type === AlertTypeEnum.TIME_BOUND) {
      return <IconTrendingUp size={18} />;
    }
    return <IconShield size={18} />;
  };

  // Helper function to get alert type display name
  const getAlertTypeName = (type: AlertTypeEnum, category: AlertCategory) => {
    const config = getAlertTypeConfig(type, category);
    return config?.name || `${type} ${category}`;
  };

  return (
    <IOSPageWrapper
      title="Alerts"
      subtitle="Monitor and manage blockchain alerts"
      action={
        <Button
          leftSection={<IconPlus size={16} />}
          variant="filled"
          onClick={() => setModalOpened(true)}
        >
          Create Alert
        </Button>
      }
    >
      {/* Enhanced Create Alert Modal with Mode Toggle */}
      <Modal
        opened={modalOpened}
        onClose={() => {
          setModalOpened(false);
          setActiveStep(0);
          setAlertMode('smart');
          form.reset();
        }}
        title="Create New Alert"
        size="lg"
      >
        <Stack gap="lg">
          {/* Mode Toggle */}
          <SegmentedControl
            value={alertMode}
            onChange={(value) => setAlertMode(value as 'smart' | 'advanced')}
            data={[
              { label: '🤖 Smart Mode', value: 'smart' },
              { label: '⚙️ Advanced Mode', value: 'advanced' }
            ]}
            fullWidth
          />

          {alertMode === 'smart' ? (
            <SmartAlertForm
              onCreateAlert={handleSmartAlertCreation}
              onSwitchToAdvanced={handleSwitchToAdvanced}
              wallets={wallets}
            />
          ) : (
            <>
              {/* Advanced Mode Stepper */}
          <Stepper active={activeStep} onStepClick={setActiveStep} allowNextStepsSelect={false}>
            <Stepper.Step label="Type" description="Choose alert type">
              <Box mt="md">
                <AlertTypeSelector
                  value={form.values.type && form.values.category ? `${form.values.type}-${form.values.category}` : undefined}
                  onChange={handleAlertTypeChange}
                />
              </Box>
            </Stepper.Step>

            <Stepper.Step label="Configure" description="Set parameters">
              <Box mt="md">
                <Stack gap="md">
                  <TextInput
                    label="Alert Name"
                    placeholder="Enter a name for your alert"
                    required
                    {...form.getInputProps('name')}
                  />

                  <Textarea
                    label="Description (Optional)"
                    placeholder="Add a description for your alert"
                    minRows={2}
                    {...form.getInputProps('description')}
                  />

                  {form.values.type && form.values.category && (
                    <ParameterBuilder
                      config={getAlertTypeConfig(form.values.type, form.values.category)!}
                      values={form.values}
                      onChange={handleParameterChange}
                      wallets={wallets}
                    />
                  )}
                </Stack>
              </Box>
            </Stepper.Step>

            <Stepper.Step label="Schedule" description="Set timing">
              <Box mt="md">
                <ScheduleConfiguration
                  value={form.values.schedule}
                  onChange={(schedule) => form.setFieldValue('schedule', schedule)}
                />
              </Box>
            </Stepper.Step>

            <Stepper.Step label="Review" description="Confirm details">
              <Box mt="md">
                <Stack gap="md">
                  <Text size="lg" fw={600}>Review Your Alert</Text>

                  <Card withBorder padding="md">
                    <Stack gap="sm">
                      <Group justify="space-between">
                        <Text fw={500}>Name:</Text>
                        <Text>{form.values.name}</Text>
                      </Group>

                      <Group justify="space-between">
                        <Text fw={500}>Type:</Text>
                        <Badge color="blue">
                          {getAlertTypeConfig(form.values.type, form.values.category)?.name}
                        </Badge>
                      </Group>

                      <Group justify="space-between">
                        <Text fw={500}>Condition:</Text>
                        <Text size="sm" style={{ fontFamily: 'monospace' }}>
                          {form.values.query || 'No condition set'}
                        </Text>
                      </Group>

                      <Group justify="space-between">
                        <Text fw={500}>Schedule:</Text>
                        <Text>{form.values.schedule.type}</Text>
                      </Group>

                      <Group justify="space-between">
                        <Text fw={500}>Status:</Text>
                        <Badge color={form.values.enabled ? 'green' : 'gray'}>
                          {form.values.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </Group>
                    </Stack>
                  </Card>

                  <Switch
                    label="Enable Alert"
                    description="Alert will be active immediately after creation"
                    checked={form.values.enabled}
                    onChange={(event) => form.setFieldValue('enabled', event.currentTarget.checked)}
                  />
                </Stack>
              </Box>
            </Stepper.Step>
          </Stepper>

          {/* Navigation Buttons */}
          <Group justify="space-between" mt="xl">
            <Button
              variant="light"
              onClick={activeStep === 0 ? () => setModalOpened(false) : prevStep}
            >
              {activeStep === 0 ? 'Cancel' : 'Back'}
            </Button>

            <Group>
              {activeStep < 3 ? (
                <Button
                  onClick={nextStep}
                  disabled={!validateStep(activeStep)}
                >
                  Next
                </Button>
              ) : (
                <Button
                  onClick={() => handleSubmit(form.values)}
                  leftSection={<IconCheck size={16} />}
                  loading={loading}
                  disabled={!validateStep(activeStep)}
                >
                  Create Alert
                </Button>
              )}
            </Group>
          </Group>
            </>
          )}
        </Stack>
      </Modal>

      <IOSCard>
        <Group justify="space-between" mb="md" p="md">
          <TextInput
            placeholder="Search alerts..."
            leftSection={<IconSearch size={16} />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.currentTarget.value)}
            style={{ width: '300px' }}
          />
          <Group>
            <Select
              label="Items per page"
              value={pageSize}
              onChange={(value) => {
                setPageSize(value || '10');
                setActivePage(1);
              }}
              data={['5', '10', '20', '50']}
              style={{ width: '100px' }}
            />
            <ActionIcon
              variant="light"
              color="blue"
              size="lg"
              aria-label="Refresh"
              onClick={() => fetchAlerts()}
              loading={loading}
            >
              <IconRefresh size={18} />
            </ActionIcon>
          </Group>
        </Group>

        <Tabs
          value={activeTab}
          onChange={(value: string | null) => setActiveTab(value || 'all')}
          mb="md"
        >
          <Tabs.List>
            <Tabs.Tab value="all">All Alerts</Tabs.Tab>
            <Tabs.Tab value="open">Open</Tabs.Tab>
            <Tabs.Tab value="resolved">Resolved</Tabs.Tab>
          </Tabs.List>
        </Tabs>

        {loading ? (
          <Center p="xl">
            <Loader size="lg" />
          </Center>
        ) : error ? (
          <MantineAlert
            color="red"
            title="Error"
            withCloseButton
            closeButtonLabel="Close alert"
            onClose={() => setError(null)}
          >
            {error}
          </MantineAlert>
        ) : filteredAlerts.length === 0 ? (
          <Card withBorder p="xl" radius="md">
            <Center>
              <Stack align="center" gap="md">
                <IconBell size={48} opacity={0.3} />
                <Text size="lg" fw={500}>
                  No alerts found
                </Text>
                <Text size="sm" c="dimmed" ta="center">
                  Create your first alert by clicking the "Create Alert" button
                </Text>
                <Button onClick={() => setModalOpened(true)} mt="md">
                  Create Alert
                </Button>
              </Stack>
            </Center>
          </Card>
        ) : (
          <>
            <Grid>
              {paginatedAlerts.map((alert: AlertType) => (
                <Grid.Col span={{ base: 12, md: 6, lg: 4 }} key={alert.id}>
                  <Card
                    withBorder
                    shadow="sm"
                    p="md"
                    radius="md"
                    style={{ height: '100%', cursor: 'pointer' }}
                    onClick={() => navigate(`/ekko/alerts/${alert.id}`)}
                  >
                    <Group justify="space-between" mb="xs">
                      <Group>
                        {getAlertIcon(alert.type, alert.category)}
                        <Text fw={700}>{getAlertTypeName(alert.type, alert.category)}</Text>
                      </Group>
                      <Badge color={alert.enabled ? 'blue' : 'gray'}>
                        {alert.enabled ? 'Active' : 'Disabled'}
                      </Badge>
                    </Group>

                    <Text fw={600} size="md" mb="xs">
                      {alert.name}
                    </Text>

                    {alert.description && (
                      <Text size="sm" c="dimmed" mb="md">
                        {alert.description}
                      </Text>
                    )}

                    <Text
                      size="sm"
                      mb="md"
                      p="xs"
                      bg="rgba(25, 113, 194, 0.1)"
                      style={{
                        borderRadius: '4px',
                        fontWeight: 500,
                        color: '#1864ab',
                        fontFamily: 'monospace'
                      }}
                    >
                      {alert.condition?.query || 'No condition set'}
                    </Text>

                    <Group justify="space-between" mt="xs">
                      <Text>Schedule:</Text>
                      <Badge variant="light">
                        {alert.schedule?.type || 'real-time'}
                      </Badge>
                    </Group>

                    {alert.condition?.parameters?.wallet_id && (
                      <Group justify="space-between" mt="xs">
                        <Text>Wallet:</Text>
                        <Text size="sm">
                          {(() => {
                            const walletId = (alert.condition.parameters as any).wallet_id;
                            const associatedWallet = wallets.find((w) => w.id === walletId);
                            if (associatedWallet) {
                              const address = associatedWallet.address;
                              const truncatedAddress = address
                                ? `${address.substring(0, 6)}...${address.substring(address.length - 6)}`
                                : '';
                              const name = associatedWallet.name || `${associatedWallet.blockchain_symbol} Wallet`;
                              return truncatedAddress ? `${name} (${truncatedAddress})` : name;
                            }
                            return `Wallet ${walletId.substring(0, 8)}...`;
                          })()}
                        </Text>
                      </Group>
                    )}

                    <Group justify="flex-end" mt="md">
                      <Text size="xs" c="dimmed">
                        {new Date(alert.created_at).toLocaleString()}
                      </Text>
                      <Tooltip label="Delete alert">
                        <ActionIcon
                          color="red"
                          radius="xl"
                          variant="subtle"
                          loading={deleting === alert.id}
                          onClick={(e) => {
                            e.stopPropagation(); // Prevent card click event
                            handleDeleteAlert(alert.id);
                          }}
                        >
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
                  </Card>
                </Grid.Col>
              ))}
            </Grid>

            {filteredAlerts.length > parseInt(pageSize) && (
              <Group justify="center" mt="xl" p="md">
                <Pagination value={activePage} onChange={setActivePage} total={totalPages} />
              </Group>
            )}
          </>
        )}
      </IOSCard>
    </IOSPageWrapper>
  );
}
