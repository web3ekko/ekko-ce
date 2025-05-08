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
  Divider,
  Table
} from '@mantine/core';
import { 
  IconSearch, 
  IconRefresh, 
  IconExchange, 
  IconArrowUp, 
  IconArrowDown,
  IconFilter
} from '@tabler/icons-react';

// This will be replaced with actual API data
const MOCK_TRANSACTIONS = [
  { 
    id: '1', 
    hash: '0x1a2b3c4d5e6f...', 
    from: '0x1234...5678', 
    to: '0x8765...4321', 
    amount: 1.25, 
    token: 'AVAX', 
    timestamp: '2025-05-08T09:30:00Z', 
    status: 'Confirmed',
    type: 'Send'
  },
  { 
    id: '2', 
    hash: '0xabcdef1234...', 
    from: '0x9876...5432', 
    to: '0x1234...5678', 
    amount: 0.5, 
    token: 'ETH', 
    timestamp: '2025-05-08T08:15:00Z', 
    status: 'Confirmed',
    type: 'Receive'
  },
  { 
    id: '3', 
    hash: '0x7890abcdef...', 
    from: '0x1234...5678', 
    to: '0xContract...', 
    amount: 100, 
    token: 'USDC', 
    timestamp: '2025-05-08T07:45:00Z', 
    status: 'Confirmed',
    type: 'Contract'
  },
  { 
    id: '4', 
    hash: '0x2468acef...', 
    from: '0x1234...5678', 
    to: '0xdead...beef', 
    amount: 0.75, 
    token: 'AVAX', 
    timestamp: '2025-05-08T06:30:00Z', 
    status: 'Pending',
    type: 'Send'
  },
  { 
    id: '5', 
    hash: '0x13579bdf...', 
    from: '0xdead...beef', 
    to: '0x1234...5678', 
    amount: 2.5, 
    token: 'MATIC', 
    timestamp: '2025-05-07T23:15:00Z', 
    status: 'Confirmed',
    type: 'Receive'
  },
];

export default function Transactions() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activePage, setActivePage] = useState(1);
  const [pageSize, setPageSize] = useState('10');
  const [activeTab, setActiveTab] = useState('all');
  
  // Filter transactions based on search query and active tab
  const filteredTransactions = MOCK_TRANSACTIONS.filter(tx => {
    const matchesSearch = 
      tx.hash.toLowerCase().includes(searchQuery.toLowerCase()) || 
      tx.from.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tx.to.toLowerCase().includes(searchQuery.toLowerCase());
    
    if (activeTab === 'all') return matchesSearch;
    if (activeTab === 'send') return matchesSearch && tx.type === 'Send';
    if (activeTab === 'receive') return matchesSearch && tx.type === 'Receive';
    if (activeTab === 'contract') return matchesSearch && tx.type === 'Contract';
    if (activeTab === 'pending') return matchesSearch && tx.status === 'Pending';
    
    return matchesSearch;
  });
  
  // Calculate pagination
  const totalPages = Math.ceil(filteredTransactions.length / parseInt(pageSize));
  const paginatedTransactions = filteredTransactions.slice(
    (activePage - 1) * parseInt(pageSize),
    activePage * parseInt(pageSize)
  );

  // Helper function to get transaction icon based on type
  const getTransactionIcon = (type: string) => {
    switch (type) {
      case 'Send': return <IconArrowUp size={18} color="red" />;
      case 'Receive': return <IconArrowDown size={18} color="green" />;
      case 'Contract': return <IconExchange size={18} color="blue" />;
      default: return <IconExchange size={18} />;
    }
  };

  // Helper function to format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <div>
      <Group justify="space-between" mb="lg">
        <div>
          <Title order={2}>Transactions</Title>
          <Text c="dimmed" size="sm">View and analyze blockchain transactions</Text>
        </div>
        <Group>
          <Button leftSection={<IconFilter size={16} />} variant="light">Filter</Button>
          <Button leftSection={<IconExchange size={16} />} variant="filled">New Transaction</Button>
        </Group>
      </Group>
      
      <Card withBorder mb="md">
        <Group justify="space-between" mb="md">
          <TextInput
            placeholder="Search transactions..."
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
            <Tabs.Tab value="all">All</Tabs.Tab>
            <Tabs.Tab value="send">Sent</Tabs.Tab>
            <Tabs.Tab value="receive">Received</Tabs.Tab>
            <Tabs.Tab value="contract">Contract</Tabs.Tab>
            <Tabs.Tab value="pending">Pending</Tabs.Tab>
          </Tabs.List>
        </Tabs>
        
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Type</Table.Th>
              <Table.Th>Hash</Table.Th>
              <Table.Th>From</Table.Th>
              <Table.Th>To</Table.Th>
              <Table.Th>Amount</Table.Th>
              <Table.Th>Time</Table.Th>
              <Table.Th>Status</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {paginatedTransactions.map(tx => (
              <Table.Tr key={tx.id}>
                <Table.Td>
                  <Group gap="xs">
                    {getTransactionIcon(tx.type)}
                    <Text size="sm">{tx.type}</Text>
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" style={{ fontFamily: 'monospace' }}>{tx.hash}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" style={{ fontFamily: 'monospace' }}>{tx.from}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" style={{ fontFamily: 'monospace' }}>{tx.to}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" fw={500}>{tx.amount} {tx.token}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{formatDate(tx.timestamp)}</Text>
                </Table.Td>
                <Table.Td>
                  <Badge color={tx.status === 'Confirmed' ? 'green' : 'yellow'}>
                    {tx.status}
                  </Badge>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        
        {filteredTransactions.length > parseInt(pageSize) && (
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
