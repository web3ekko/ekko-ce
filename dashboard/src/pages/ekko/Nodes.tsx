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
import { nodesApi, Node, CreateNodePayload } from '@/services/api/ekko'; 

const networkSubnetOptions: Record<string, string[]> = {
  'Ethereum': ['Mainnet', 'Sepolia', 'Goerli'],
  'Avalanche': ['Mainnet', 'Fuji Testnet'],
  'Polygon': ['Mainnet', 'Mumbai Testnet'],
  'BNB Smart Chain': ['Mainnet', 'Testnet'],
  'Arbitrum': ['One', 'Goerli'],
  'Optimism': ['Mainnet', 'Goerli'],
  // Add more networks and their subnets as needed
};

const MOCK_NODES: Node[] = [
  {
    id: '1',
    name: 'AVAX-Mainnet-1',
    type: 'Validator',
    network: 'Avalanche',
    subnet: 'Mainnet',
    http_url: 'https://node1.example.com:9650',
    websocket_url: 'wss://node1.example.com:9651/ext/bc/C/ws',
    vm: 'EVM',
    status: 'Online',
    created_at: '2023-01-01T10:00:00Z', // Retaining for mock, though optional in interface
    updated_at: '2023-01-10T12:00:00Z', // Retaining for mock, though optional in interface
  },
  {
    id: '5',
    name: 'AVAX-Fuji-1',
    type: 'API',
    network: 'Avalanche',
    subnet: 'Fuji Testnet',
    http_url: 'https://fuji1.example.com:9650',
    websocket_url: 'wss://fuji1.example.com:9651/ext/bc/C/ws',
    vm: 'EVM',
    status: 'Offline',
    created_at: '2023-01-02T10:00:00Z', // Retaining for mock, though optional in interface
    updated_at: '2023-01-05T12:00:00Z', // Retaining for mock, though optional in interface
  },
];

export default function Nodes() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [modalOpened, setModalOpened] = useState(false);
  const [nodes, setNodes] = useState<Node[]>(MOCK_NODES);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Form for creating a new node
  const form = useForm({
    initialValues: {
      name: '',
      websocket_url: '',
      http_url: '',
      vm: 'EVM',
      network: '',
      subnet: '',
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
      network: (value) => (value ? null : 'Network is required'),
      subnet: (value) => (value ? null : 'Subnet is required'),
    },
  });
  
  // Function to fetch nodes from API
  const fetchNodes = async () => {
    try {
      setLoading(true);
      const response = await nodesApi.getNodes();
      console.log('Nodes.tsx: Fetched nodes API response:', JSON.stringify(response, null, 2)); // Log the whole response object
      // Assuming response is PaginatedResponse<Node> as per ekko.ts type
      if (response && response.data) {
        console.log('Nodes.tsx: Setting nodes with response.data:', JSON.stringify(response.data, null, 2));
        setNodes(response.data);
      } else {
        console.error('Nodes.tsx: API response for nodes did not have a .data property or response was null/undefined. Response:', response);
        // If the API returns a direct array, response.data would be undefined.
        // In that case, we might want to setNodes(response) if response is Node[]
        // For now, let's assume PaginatedResponse and log an error if it's not matching.
        setNodes([]); // Set to empty array to prevent crash, but indicates an issue
      }
      setError(null);
    } catch (err: any) { // Added :any for better inspection
      console.error('Nodes.tsx: Error fetching nodes RAW:', err);
      console.error('Nodes.tsx: Error fetching nodes JSON:', JSON.stringify(err, null, 2));
      if (err.response) {
        console.error('Nodes.tsx: Error response data:', JSON.stringify(err.response.data, null, 2));
        console.error('Nodes.tsx: Error response status:', err.response.status);
      }
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
      
      const nodeToCreate: CreateNodePayload = {
        name: values.name,
        network: values.network,
        subnet: values.subnet,
        http_url: values.http_url,
        websocket_url: values.websocket_url,
        vm: values.vm,
        type: 'API', // Optional: backend defaults to 'API'
      };
      
      await nodesApi.createNode(nodeToCreate);
      
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
      node.http_url.toLowerCase().includes(searchQuery.toLowerCase());
    
    if (activeTab === 'all') return matchesSearch;
    if (activeTab === 'online') return matchesSearch && node.status === 'Online';
    if (activeTab === 'issues') return matchesSearch && (node.status === 'Degraded' || node.status === 'Offline');
    
    return matchesSearch;
  });

  // Helper function to get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Online': return 'green';
      case 'Pending': return 'yellow'; 
      case 'Degraded': return 'orange'; 
      case 'Offline': return 'red';
      default: return 'gray';
    }
  };

  // Helper function to get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'Online': return <IconCheck size={14} />;
      case 'Pending': return <IconRefresh size={14} />; 
      case 'Degraded': return <IconAlertTriangle size={14} />;
      case 'Offline': return <IconX size={14} />;
      default: return <IconServer size={14} />; 
    }
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
              <Table.Th>Network / Subnet</Table.Th>
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
                  <Text size="sm">{node.network} ({node.subnet})</Text>
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
                <Text size="sm">Network / Subnet:</Text>
                <Text size="sm" fw={500}>{node.network} ({node.subnet})</Text>
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

            <Select
              label="Network"
              placeholder="Select network"
              data={Object.keys(networkSubnetOptions).map(net => ({ value: net, label: net }))}
              required
              mb="md"
              {...form.getInputProps('network')}
              onChange={(value) => {
                form.setFieldValue('network', value || '');
                form.setFieldValue('subnet', ''); // Reset subnet when network changes
              }}
            />

            <Select
              label="Subnet"
              placeholder={form.values.network ? "Select subnet" : "Select network first"}
              data={form.values.network ? networkSubnetOptions[form.values.network]?.map(sub => ({ value: sub, label: sub })) || [] : []}
              required
              mb="md"
              disabled={!form.values.network || !networkSubnetOptions[form.values.network]}
              {...form.getInputProps('subnet')}
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
