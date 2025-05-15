import React, { useState, useEffect } from 'react';
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
  Table,
  Tabs,
  Modal,
  Select,
  Center,
  Loader
} from '@mantine/core';
import { useForm } from '@mantine/form';
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
import { nodesApi } from '@/services/api/ekko';

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
  const [modalOpened, setModalOpened] = useState(false);
  const [nodes, setNodes] = useState(MOCK_NODES);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Form for creating a new node
  const form = useForm({
    initialValues: {
      name: '',
      websocket_url: '',
      http_url: '',
      vm: 'EVM',
    },
    validate: {
      name: (value) => (value.trim().length > 0 ? null : 'Name is required'),
      websocket_url: (value) => {
        if (value.trim().length === 0) return 'WebSocket URL is required';
        if (!value.startsWith('ws://') && !value.startsWith('wss://')) return 'WebSocket URL must start with ws:// or wss://';
        return null;
      },
      http_url: (value) => {
        if (value.trim().length === 0) return 'HTTP URL is required';
        if (!value.startsWith('http://') && !value.startsWith('https://')) return 'HTTP URL must start with http:// or https://';
        return null;
      },
    },
  });
  
  // Function to fetch nodes from API
  const fetchNodes = async () => {
    try {
      setLoading(true);
      const data = await nodesApi.getNodes();
      setNodes(data.data.length > 0 ? data.data : MOCK_NODES);
      setError(null);
    } catch (err) {
      console.error('Error fetching nodes:', err);
      setError('Failed to load nodes. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  // Fetch nodes on component mount
  useEffect(() => {
    fetchNodes();
  }, []);
  
  // Handle form submission
  const handleSubmit = async (values: typeof form.values) => {
    try {
      setLoading(true);
      
      // Create new node
      const newNode = {
        name: values.name,
        websocket_url: values.websocket_url,
        http_url: values.http_url,
        vm: values.vm,
        type: 'API',
        network: values.name.includes('Fuji') ? 'Avalanche Fuji' : 'Avalanche',
        // Required properties from Node interface
        endpoint: values.http_url, // Use HTTP URL as the main endpoint
        status: 'Offline', // Initial status
        uptime: 0,
        cpu: 0,
        memory: 0,
        disk: 0,
        peers: 0,
        version: '',
      };
      
      await nodesApi.createNode(newNode);
      
      // Refresh nodes list
      await fetchNodes();
      
      // Reset form and close modal
      form.reset();
      setModalOpened(false);
    } catch (error) {
      console.error('Error creating node:', error);
      setError('Failed to create node. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  // Filter nodes based on search query and active tab
  const filteredNodes = nodes.filter(node => {
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
        <Button leftSection={<IconPlus size={16} />} variant="filled" onClick={() => setModalOpened(true)}>Add Node</Button>
      </Group>
      
      <Card withBorder mb="md">
        <Group justify="space-between" mb="md">
          <TextInput
            placeholder="Search nodes..."
            leftSection={<IconSearch size={16} />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.currentTarget.value as string)}
            style={{ width: '300px' }}
          />
          <ActionIcon variant="light" color="blue" size="lg" aria-label="Refresh">
            <IconRefresh size={18} />
          </ActionIcon>
        </Group>
        
        <Tabs value={activeTab} onChange={(value) => value && setActiveTab(value)} mb="md">
          <Tabs.List>
            <Tabs.Tab value="all">All Nodes</Tabs.Tab>
            <Tabs.Tab value="online">Online</Tabs.Tab>
            <Tabs.Tab value="issues">Issues</Tabs.Tab>
          </Tabs.List>
        </Tabs>
        
        <Table verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Network</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th></Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {filteredNodes.map(node => (
              <Table.Tr key={node.id}>
                <Table.Td>
                  <Group gap="sm">
                    <IconServer size={16} />
                    <Text size="sm">{node.name}</Text>
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{node.network}</Text>
                </Table.Td>
                <Table.Td>
                  <Badge 
                    size="sm" 
                    color={getStatusColor(node.status)}
                    leftSection={getStatusIcon(node.status)}
                  >
                    {node.status}
                  </Badge>
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
      <Grid mt="md">
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
              
              <Group justify="space-between" mt="md">
                <Text size="sm">Network:</Text>
                <Text size="sm" fw={500}>{node.network}</Text>
              </Group>
            </Card>
          </Grid.Col>
        ))}
      </Grid>
      
      {/* Add Node Modal */}
      <Modal
        opened={modalOpened}
        onClose={() => {
          setModalOpened(false);
          form.reset();
        }}
        title="Add New Node"
        size="md"
      >
        {loading && (
          <Center my="xl">
            <Loader size="md" />
          </Center>
        )}
        
        {!loading && (
          <form onSubmit={form.onSubmit(handleSubmit)}>
            <TextInput
              label="Node Name"
              placeholder="AVAX-Mainnet-3"
              required
              mb="md"
              {...form.getInputProps('name')}
            />
            
            <TextInput
              label="WebSocket URL"
              placeholder="wss://node.example.com:9650/ext/bc/ws"
              required
              mb="md"
              {...form.getInputProps('websocket_url')}
            />
            
            <TextInput
              label="HTTP URL"
              placeholder="https://node.example.com:9650/ext/bc/C/rpc"
              required
              mb="md"
              {...form.getInputProps('http_url')}
            />
            
            <Select
              label="Virtual Machine"
              placeholder="Select VM"
              data={[{ value: 'EVM', label: 'EVM' }]}
              mb="xl"
              required
              {...form.getInputProps('vm')}
            />
            
            <Group justify="flex-end">
              <Button variant="outline" onClick={() => {
                setModalOpened(false);
                form.reset();
              }}>
                Cancel
              </Button>
              <Button type="submit">
                Add Node
              </Button>
            </Group>
          </form>
        )}
      </Modal>
    </div>
  );
}
