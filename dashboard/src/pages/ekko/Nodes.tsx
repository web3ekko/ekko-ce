import React, { useState } from 'react';
import { 
  Title, 
  Text, 
  Card, 
  Grid, 
  Badge, 
  Group, 
  Button, 
  TextInput,
  ActionIcon,
  Progress,
  Table,
  Tooltip,
  Tabs
} from '@mantine/core';
import { 
  IconSearch, 
  IconPlus, 
  IconRefresh, 
  IconServer, 
  IconChevronRight,
  IconCheck,
  IconX,
  IconAlertTriangle
} from '@tabler/icons-react';

// This will be replaced with actual API data
const MOCK_NODES = [
  { 
    id: '1', 
    name: 'AVAX-Mainnet-1', 
    type: 'Validator',
    network: 'Avalanche',
    endpoint: 'https://node1.example.com:9650',
    status: 'Online',
    uptime: 99.98,
    cpu: 32,
    memory: 45,
    disk: 68,
    peers: 124,
    version: '1.9.12'
  },
  { 
    id: '2', 
    name: 'AVAX-Mainnet-2', 
    type: 'API',
    network: 'Avalanche',
    endpoint: 'https://node2.example.com:9650',
    status: 'Online',
    uptime: 99.95,
    cpu: 45,
    memory: 62,
    disk: 72,
    peers: 118,
    version: '1.9.12'
  },
  { 
    id: '3', 
    name: 'ETH-Mainnet-1', 
    type: 'Full',
    network: 'Ethereum',
    endpoint: 'https://eth1.example.com:8545',
    status: 'Online',
    uptime: 99.92,
    cpu: 58,
    memory: 75,
    disk: 82,
    peers: 86,
    version: '1.12.0'
  },
  { 
    id: '4', 
    name: 'BTC-Mainnet-1', 
    type: 'Full',
    network: 'Bitcoin',
    endpoint: 'https://btc1.example.com:8332',
    status: 'Degraded',
    uptime: 98.45,
    cpu: 78,
    memory: 82,
    disk: 91,
    peers: 42,
    version: '24.0.1'
  },
  { 
    id: '5', 
    name: 'AVAX-Fuji-1', 
    type: 'API',
    network: 'Avalanche Fuji',
    endpoint: 'https://fuji1.example.com:9650',
    status: 'Offline',
    uptime: 0,
    cpu: 0,
    memory: 0,
    disk: 65,
    peers: 0,
    version: '1.9.11'
  },
];

export default function Nodes() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  
  // Filter nodes based on search query and active tab
  const filteredNodes = MOCK_NODES.filter(node => {
    const matchesSearch = 
      node.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
      node.network.toLowerCase().includes(searchQuery.toLowerCase()) ||
      node.endpoint.toLowerCase().includes(searchQuery.toLowerCase());
    
    if (activeTab === 'all') return matchesSearch;
    if (activeTab === 'online') return matchesSearch && node.status === 'Online';
    if (activeTab === 'issues') return matchesSearch && (node.status === 'Degraded' || node.status === 'Offline');
    
    return matchesSearch;
  });

  // Helper function to get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Online': return 'green';
      case 'Degraded': return 'yellow';
      case 'Offline': return 'red';
      default: return 'gray';
    }
  };

  // Helper function to get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'Online': return <IconCheck size={16} />;
      case 'Degraded': return <IconAlertTriangle size={16} />;
      case 'Offline': return <IconX size={16} />;
      default: return null;
    }
  };

  // Helper function to get resource usage color
  const getResourceColor = (usage: number) => {
    if (usage >= 90) return 'red';
    if (usage >= 75) return 'orange';
    if (usage >= 50) return 'yellow';
    return 'green';
  };

  return (
    <div>
      <Group justify="space-between" mb="lg">
        <div>
          <Title order={2}>Blockchain Nodes</Title>
          <Text c="dimmed" size="sm">Monitor and manage your blockchain nodes</Text>
        </div>
        <Button leftSection={<IconPlus size={16} />} variant="filled">Add Node</Button>
      </Group>
      
      <Card withBorder mb="md">
        <Group justify="space-between" mb="md">
          <TextInput
            placeholder="Search nodes..."
            leftSection={<IconSearch size={16} />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.currentTarget.value)}
            style={{ width: '300px' }}
          />
          <ActionIcon variant="light" color="blue" size="lg" aria-label="Refresh">
            <IconRefresh size={18} />
          </ActionIcon>
        </Group>
        
        <Tabs value={activeTab} onChange={setActiveTab} mb="md">
          <Tabs.List>
            <Tabs.Tab value="all">All Nodes</Tabs.Tab>
            <Tabs.Tab value="online">Online</Tabs.Tab>
            <Tabs.Tab value="issues">Issues</Tabs.Tab>
          </Tabs.List>
        </Tabs>
        
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Network</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Uptime</Table.Th>
              <Table.Th>Resources</Table.Th>
              <Table.Th>Version</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {filteredNodes.map(node => (
              <Table.Tr key={node.id}>
                <Table.Td>
                  <Group gap="xs">
                    <IconServer size={18} />
                    <Text fw={500}>{node.name}</Text>
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Badge>{node.network}</Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{node.type}</Text>
                </Table.Td>
                <Table.Td>
                  <Badge 
                    color={getStatusColor(node.status)}
                    leftSection={getStatusIcon(node.status)}
                  >
                    {node.status}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{node.uptime}%</Text>
                </Table.Td>
                <Table.Td style={{ width: '180px' }}>
                  {node.status !== 'Offline' ? (
                    <Group gap={5}>
                      <Tooltip label={`CPU: ${node.cpu}%`}>
                        <Progress 
                          value={node.cpu} 
                          color={getResourceColor(node.cpu)} 
                          size="sm" 
                          style={{ width: '50px' }}
                        />
                      </Tooltip>
                      <Tooltip label={`Memory: ${node.memory}%`}>
                        <Progress 
                          value={node.memory} 
                          color={getResourceColor(node.memory)} 
                          size="sm" 
                          style={{ width: '50px' }}
                        />
                      </Tooltip>
                      <Tooltip label={`Disk: ${node.disk}%`}>
                        <Progress 
                          value={node.disk} 
                          color={getResourceColor(node.disk)} 
                          size="sm" 
                          style={{ width: '50px' }}
                        />
                      </Tooltip>
                    </Group>
                  ) : (
                    <Text size="sm" c="dimmed">No data</Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{node.version}</Text>
                </Table.Td>
                <Table.Td>
                  <ActionIcon variant="subtle">
                    <IconChevronRight size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>
      
      {/* Node Details Cards */}
      <Grid>
        {filteredNodes.slice(0, 3).map(node => (
          <Grid.Col span={{ base: 12, md: 6, lg: 4 }} key={node.id}>
            <Card withBorder p="md" radius="md">
              <Group justify="space-between" mb="xs">
                <Group>
                  <IconServer size={20} />
                  <Text fw={700}>{node.name}</Text>
                </Group>
                <Badge color={getStatusColor(node.status)}>
                  {node.status}
                </Badge>
              </Group>
              <Text size="sm" c="dimmed" mb="md">{node.endpoint}</Text>
              
              <Group justify="space-between" mb="xs">
                <Text size="sm">Network:</Text>
                <Text size="sm" fw={500}>{node.network}</Text>
              </Group>
              
              <Group justify="space-between" mb="xs">
                <Text size="sm">Type:</Text>
                <Text size="sm" fw={500}>{node.type}</Text>
              </Group>
              
              <Group justify="space-between" mb="xs">
                <Text size="sm">Peers:</Text>
                <Text size="sm" fw={500}>{node.peers}</Text>
              </Group>
              
              <Group justify="space-between" mb="xs">
                <Text size="sm">Version:</Text>
                <Text size="sm" fw={500}>{node.version}</Text>
              </Group>
              
              {node.status !== 'Offline' && (
                <>
                  <Text size="sm" fw={500} mt="md" mb="xs">Resource Usage</Text>
                  <Group justify="space-between" mb="xs">
                    <Text size="sm">CPU:</Text>
                    <Group gap={5}>
                      <Progress 
                        value={node.cpu} 
                        color={getResourceColor(node.cpu)} 
                        size="sm" 
                        style={{ width: '100px' }}
                      />
                      <Text size="sm">{node.cpu}%</Text>
                    </Group>
                  </Group>
                  
                  <Group justify="space-between" mb="xs">
                    <Text size="sm">Memory:</Text>
                    <Group gap={5}>
                      <Progress 
                        value={node.memory} 
                        color={getResourceColor(node.memory)} 
                        size="sm" 
                        style={{ width: '100px' }}
                      />
                      <Text size="sm">{node.memory}%</Text>
                    </Group>
                  </Group>
                  
                  <Group justify="space-between" mb="xs">
                    <Text size="sm">Disk:</Text>
                    <Group gap={5}>
                      <Progress 
                        value={node.disk} 
                        color={getResourceColor(node.disk)} 
                        size="sm" 
                        style={{ width: '100px' }}
                      />
                      <Text size="sm">{node.disk}%</Text>
                    </Group>
                  </Group>
                </>
              )}
            </Card>
          </Grid.Col>
        ))}
      </Grid>
    </div>
  );
}
