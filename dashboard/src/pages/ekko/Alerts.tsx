import React, { useState, useEffect } from 'react';
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
  Alert as MantineAlert
} from '@mantine/core';
import { useForm } from '@mantine/form';
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
  IconShield 
} from '@tabler/icons-react';

// Import the alert service
import { AlertService } from '@/services/alert/alert.service';
import type { Alert as AlertType, AlertFormValues } from '@/@types/alert';
import { v4 as uuidv4 } from 'uuid';

// Sample alerts for empty state - will be replaced with API data
const EMPTY_ALERTS: AlertType[] = [
  { 
    id: '1', 
    type: 'Balance', 
    message: 'Main wallet balance below 3 AVAX', 
    time: '2025-05-08T08:30:00Z', 
    status: 'Open', 
    priority: 'High', 
    related_wallet: '0x1234...5678',
    query: 'balance < 3'
  },
  { 
    id: '2', 
    type: 'Price', 
    message: 'ETH price increased by 5% in last hour', 
    time: '2025-05-08T07:15:00Z', 
    status: 'Open', 
    priority: 'Medium', 
    related_wallet: '',
    query: 'price_change > 5%'
  },
  { 
    id: '3', 
    type: 'Transaction', 
    message: 'Large transaction detected on wallet AVAX-1', 
    time: '2025-05-08T06:45:00Z', 
    status: 'Open', 
    priority: 'Low', 
    related_wallet: '0x8765...4321',
    query: 'tx_value > 1000'
  },
  { 
    id: '4', 
    type: 'Security', 
    message: 'Suspicious activity detected on wallet BTC-1', 
    time: '2025-05-07T22:30:00Z', 
    status: 'Resolved', 
    priority: 'High', 
    related_wallet: 'bc1q...wxyz',
    query: 'suspicious_activity = true'
  },
];

// AlertFormValues is now imported from @types/alert

export default function Alerts() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activePage, setActivePage] = useState(1);
  const [pageSize, setPageSize] = useState('10');
  const [activeTab, setActiveTab] = useState('all');
  const [modalOpened, setModalOpened] = useState(false);
  const [alerts, setAlerts] = useState<AlertType[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Fetch alerts on component mount
  useEffect(() => {
    fetchAlerts();
  }, []);

  // Function to fetch alerts
  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const data = await AlertService.getAlerts();
      setAlerts(data.length > 0 ? data : []);
      setError(null);
    } catch (err) {
      console.error('Error fetching alerts:', err);
      setError('Failed to load alerts. Please try again.');
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  };

  // Form for creating a new alert
  const form = useForm<AlertFormValues>({
    initialValues: {
      type: 'Price',
      message: '',
      priority: 'Medium',
      related_wallet: '',
      query: '',
      threshold: 5,
      enableNotifications: true,
    },
    validate: {
      message: (value) => (value.trim().length < 1 ? 'Alert message is required' : null),
    },
  });
  
  // Handle form submission
  const handleSubmit = async (values: AlertFormValues) => {
    try {
      setLoading(true);
      
      // Create alert object from form values
      const newAlert = {
        id: uuidv4(), // Generate a UUID for the new alert
        type: values.type,
        message: values.message,
        time: new Date().toISOString(),
        status: 'Open',
        priority: values.priority,
        related_wallet: values.related_wallet,
        query: values.query,
        icon: values.type === 'Security' ? 'shield' : 
              values.type === 'Balance' ? 'wallet' : 
              values.type === 'Price' ? 'chart' : 'bell'
      };
      
      console.log('Creating new alert:', newAlert);
      
      // Call the API to create the alert
      await AlertService.createAlert(newAlert);
      
      // Close the modal after successful submission
      setModalOpened(false);
      
      // Reset form
      form.reset();
      
      // Refresh the alert list
      fetchAlerts();
      
      setError(null);
    } catch (err: any) {
      console.error('Error creating alert:', err);
      setError(err.message || 'Failed to create alert. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  // Update message based on alert type and threshold
  const updateAlertMessage = (type: string, threshold: number, wallet: string) => {
    let message = '';
    let query = '';
    const walletName = wallet ? wallet : 'selected wallet';
    
    switch (type) {
      case 'Price':
        message = `Alert when price changes by ${threshold}%`;
        query = `price_change > ${threshold}%`;
        break;
      case 'Balance':
        message = `Alert when ${walletName} balance falls below ${threshold}`;
        query = `balance < ${threshold}`;
        break;
      case 'Transaction':
        message = `Alert on transactions above ${threshold} in ${walletName}`;
        query = `tx_value > ${threshold}`;
        break;
      case 'Security':
        message = `Security monitoring for ${walletName}`;
        query = 'suspicious_activity = true';
        break;
      default:
        message = 'Custom alert';
        query = '';
    }
    
    form.setFieldValue('message', message);
    form.setFieldValue('query', query);
  };
  
  // Filter alerts based on search query and active tab
  const filteredAlerts = alerts.filter((alert: AlertType) => {
    const matchesSearch = 
      alert.message.toLowerCase().includes(searchQuery.toLowerCase()) || 
      alert.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (alert.related_wallet && alert.related_wallet.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (alert.query && alert.query.toLowerCase().includes(searchQuery.toLowerCase()));
    
    if (activeTab === 'all') return matchesSearch;
    if (activeTab === 'open') return matchesSearch && alert.status === 'Open';
    if (activeTab === 'resolved') return matchesSearch && alert.status === 'Resolved';
    
    return matchesSearch;
  });
  
  // Calculate pagination
  const totalPages = Math.ceil(filteredAlerts.length / parseInt(pageSize));
  const paginatedAlerts = filteredAlerts.slice(
    (activePage - 1) * parseInt(pageSize),
    activePage * parseInt(pageSize)
  );

  // Helper function to get alert icon based on type
  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'Balance': return <IconWallet size={18} />;
      case 'Price': return <IconChartBar size={18} />;
      case 'Security': return <IconAlertCircle size={18} />;
      default: return <IconBell size={18} />;
    }
  };

  // Helper function to get priority color
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'High': return 'red';
      case 'Medium': return 'orange';
      case 'Low': return 'blue';
      default: return 'gray';
    }
  };

  return (
    <div>
      <Group justify="space-between" mb="lg">
        <div>
          <Title order={2}>Alerts</Title>
          <Text c="dimmed" size="sm">Monitor and manage blockchain alerts</Text>
        </div>
        <Button 
          leftSection={<IconPlus size={16} />} 
          variant="filled"
          onClick={() => setModalOpened(true)}
        >
          Create Alert
        </Button>
        
        {/* Create Alert Modal */}
        <Modal
          opened={modalOpened}
          onClose={() => setModalOpened(false)}
          title="Create New Alert"
          size="md"
        >
          <form onSubmit={form.onSubmit(handleSubmit)}>
            <Stack gap="md">
              <Radio.Group
                label="Alert Type"
                description="Select the type of alert you want to create"
                {...form.getInputProps('type')}
                onChange={(value) => {
                  form.setFieldValue('type', value);
                  updateAlertMessage(value, form.values.threshold, form.values.related_wallet);
                }}
              >
                <Group mt="xs">
                  <Radio value="Price" label="Price Alert" />
                  <Radio value="Balance" label="Balance Alert" />
                  <Radio value="Transaction" label="Transaction Alert" />
                  <Radio value="Security" label="Security Alert" />
                </Group>
              </Radio.Group>
              
              <Select
                label="Related Wallet"
                placeholder="Select wallet (optional)"
                data={[
                  { value: '', label: 'None' },
                  { value: '0x1234...5678', label: 'Main Wallet (AVAX)' },
                  { value: '0x8765...4321', label: 'Trading Wallet (ETH)' },
                  { value: 'bc1q...wxyz', label: 'Cold Storage (BTC)' },
                ]}
                clearable
                {...form.getInputProps('related_wallet')}
                onChange={(value: string | null) => {
                  form.setFieldValue('related_wallet', value || '');
                  updateAlertMessage(form.values.type, form.values.threshold, value || '');
                }}
              />
              
              <div>
                <Text size="sm" fw={500} mb="xs">Threshold</Text>
                <Slider
                  min={1}
                  max={50}
                  label={(value) => `${value}${form.values.type === 'Price' ? '%' : ''}`}
                  marks={[
                    { value: 1, label: '1' },
                    { value: 10, label: '10' },
                    { value: 25, label: '25' },
                    { value: 50, label: '50' },
                  ]}
                  {...form.getInputProps('threshold')}
                  onChange={(value) => {
                    form.setFieldValue('threshold', value);
                    updateAlertMessage(form.values.type, value, form.values.related_wallet);
                  }}
                />
              </div>
              
              <Radio.Group
                label="Priority"
                {...form.getInputProps('priority')}
              >
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
                onChange={(event) => form.setFieldValue('enableNotifications', event.currentTarget.checked)}
              />
              
              <Divider />
              
              <Group justify="flex-end">
                <Button variant="light" onClick={() => setModalOpened(false)}>Cancel</Button>
                <Button type="submit" leftSection={<IconCheck size={16} />}>Create Alert</Button>
              </Group>
            </Stack>
          </form>
        </Modal>
      </Group>
      
      <Card withBorder mb="md">
        <Group justify="space-between" mb="md">
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
        
        <Tabs value={activeTab} onChange={(value: string | null) => setActiveTab(value || 'all')} mb="md">
          <Tabs.List>
            <Tabs.Tab value="all">All Alerts</Tabs.Tab>
            <Tabs.Tab value="open">Open</Tabs.Tab>
            <Tabs.Tab value="resolved">Resolved</Tabs.Tab>
          </Tabs.List>
        </Tabs>
        
        <Stack>
          {loading ? (
            <Card withBorder p="xl" radius="md">
              <Center>
                <Stack align="center" gap="md">
                  <Loader size="md" />
                  <Text>Loading alerts...</Text>
                </Stack>
              </Center>
            </Card>
          ) : error ? (
            <Card withBorder p="xl" radius="md">
              <MantineAlert color="red" title="Error loading alerts">
                {error}
                <Button variant="light" onClick={fetchAlerts} mt="md">Try Again</Button>
              </MantineAlert>
            </Card>
          ) : paginatedAlerts.length === 0 ? (
            <Card withBorder p="xl" radius="md">
              <Center>
                <Stack align="center" gap="md">
                  <IconBell size={48} opacity={0.3} />
                  <Text size="lg" fw={500}>No alerts found</Text>
                  <Text size="sm" c="dimmed" ta="center">Create your first alert by clicking the "Create Alert" button</Text>
                  <Button onClick={() => setModalOpened(true)} mt="md">Create Alert</Button>
                </Stack>
              </Center>
            </Card>
          ) : paginatedAlerts.map((alert: AlertType) => (
            <Card key={alert.id} withBorder p="md" radius="md">
              <Group justify="space-between" mb="xs">
                <Group>
                  {getAlertIcon(alert.type)}
                  <Badge size="lg">{alert.type}</Badge>
                  <Text>{alert.message}</Text>
                </Group>
                <Group>
                  <Badge color={alert.status === 'Open' ? 'blue' : 'green'}>
                    {alert.status}
                  </Badge>
                  <Badge color={getPriorityColor(alert.priority || 'Medium')}>
                    {alert.priority || 'Medium'}
                  </Badge>
                </Group>
              </Group>
              <Divider my="xs" />
              <Group justify="space-between" mt="xs">
                <Text size="sm" c="dimmed">
                  {new Date(alert.time).toLocaleString()}
                </Text>
                {alert.related_wallet && alert.related_wallet.length > 0 && (
                  <Text size="sm" c="dimmed">
                    Wallet: {alert.related_wallet}
                  </Text>
                )}
              </Group>
            </Card>
          ))}
        </Stack>
        
        {filteredAlerts.length > parseInt(pageSize) && (
          <Group justify="center" mt="xl">
            <Pagination 
              value={activePage} 
              onChange={setActivePage} 
              total={totalPages} 
            />
          </Group>
        )}
      </Card>
    </div>
  );
}
