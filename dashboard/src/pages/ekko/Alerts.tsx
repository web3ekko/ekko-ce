import React, { useState } from 'react';
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
  Divider
} from '@mantine/core';
import { IconSearch, IconPlus, IconRefresh, IconBell, IconAlertCircle, IconChartBar, IconWallet } from '@tabler/icons-react';

// This will be replaced with actual API data
const MOCK_ALERTS = [
  { 
    id: '1', 
    type: 'Balance', 
    message: 'Main wallet balance below 3 AVAX', 
    time: '2025-05-08T08:30:00Z', 
    status: 'Open', 
    priority: 'High', 
    relatedWallet: '0x1234...5678' 
  },
  { 
    id: '2', 
    type: 'Price', 
    message: 'ETH price increased by 5% in last hour', 
    time: '2025-05-08T07:15:00Z', 
    status: 'Open', 
    priority: 'Medium', 
    relatedWallet: null
  },
  { 
    id: '3', 
    type: 'Transaction', 
    message: 'Large transaction detected on wallet AVAX-1', 
    time: '2025-05-08T06:45:00Z', 
    status: 'Open', 
    priority: 'Low', 
    relatedWallet: '0x8765...4321'
  },
  { 
    id: '4', 
    type: 'Security', 
    message: 'Suspicious activity detected on wallet BTC-1', 
    time: '2025-05-07T22:30:00Z', 
    status: 'Resolved', 
    priority: 'High', 
    relatedWallet: 'bc1q...wxyz'
  },
];

export default function Alerts() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activePage, setActivePage] = useState(1);
  const [pageSize, setPageSize] = useState('10');
  const [activeTab, setActiveTab] = useState('all');
  
  // Filter alerts based on search query and active tab
  const filteredAlerts = MOCK_ALERTS.filter(alert => {
    const matchesSearch = 
      alert.message.toLowerCase().includes(searchQuery.toLowerCase()) || 
      alert.type.toLowerCase().includes(searchQuery.toLowerCase());
    
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
        <Button leftSection={<IconPlus size={16} />} variant="filled">Create Alert</Button>
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
            <ActionIcon variant="light" color="blue" size="lg" aria-label="Refresh">
              <IconRefresh size={18} />
            </ActionIcon>
          </Group>
        </Group>
        
        <Tabs value={activeTab} onChange={setActiveTab} mb="md">
          <Tabs.List>
            <Tabs.Tab value="all">All Alerts</Tabs.Tab>
            <Tabs.Tab value="open">Open</Tabs.Tab>
            <Tabs.Tab value="resolved">Resolved</Tabs.Tab>
          </Tabs.List>
        </Tabs>
        
        <Stack>
          {paginatedAlerts.map(alert => (
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
                  <Badge color={getPriorityColor(alert.priority)}>
                    {alert.priority}
                  </Badge>
                </Group>
              </Group>
              <Divider my="xs" />
              <Group justify="space-between" mt="xs">
                <Text size="sm" c="dimmed">
                  {new Date(alert.time).toLocaleString()}
                </Text>
                {alert.relatedWallet && (
                  <Text size="sm" c="dimmed">
                    Wallet: {alert.relatedWallet}
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
