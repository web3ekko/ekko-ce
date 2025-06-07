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
  Table,
} from '@mantine/core';
import {
  IconSearch,
  IconRefresh,
  IconExchange,
  IconArrowUp,
  IconArrowDown,
  IconFilter,
  IconWifi,
  IconWifiOff,
} from '@tabler/icons-react';

import { useAppDispatch, useAppSelector } from '@/store';
import RealtimeTransactionService from '@/services/realtime/RealtimeTransactionService';
import {
  selectAllRealtimeTransactions,
  selectIsConnectingToRealtime,
  selectIsConnectedToRealtime,
  selectRealtimeConnectionError,
} from '@/store/selectors/realtimeTransactionsSelectors';
import type { RealtimeTransaction } from '@/store/slices/realtimeTransactionsSlice';

// Mock transactions removed, will use live data
export default function Transactions() {
  const dispatch = useAppDispatch(); // if needed for any direct dispatches, though service handles most
  const liveTransactions = useAppSelector(selectAllRealtimeTransactions);
  const isConnecting = useAppSelector(selectIsConnectingToRealtime);
  const isConnected = useAppSelector(selectIsConnectedToRealtime);
  const connectionError = useAppSelector(selectRealtimeConnectionError);
  const [searchQuery, setSearchQuery] = useState('');
  const [activePage, setActivePage] = useState(1);
  const [pageSize, setPageSize] = useState('10');
  const [activeTab, setActiveTab] = useState('all');

  // Effect for WebSocket connection management
  useEffect(() => {
    RealtimeTransactionService.connect();
    return () => {
      RealtimeTransactionService.disconnect();
    };
  }, []); // Empty dependency array means this runs once on mount and cleanup on unmount

  // Filter transactions based on search query and active tab
  const filteredTransactions = liveTransactions.filter((tx) => {
    const matchesSearch =
      tx.hash.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tx.from.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (tx.to && tx.to.toLowerCase().includes(searchQuery.toLowerCase())) || // Handle null 'to'
      (tx.decoded_call?.function &&
        tx.decoded_call.function.toLowerCase().includes(searchQuery.toLowerCase()));

    if (activeTab === 'all') return matchesSearch;
    if (activeTab === 'send') return matchesSearch && tx.transactionType === 'send';
    if (activeTab === 'receive') return matchesSearch && tx.transactionType === 'receive';
    if (activeTab === 'contract')
      return (
        matchesSearch &&
        (tx.transactionType === 'contract_interaction' ||
          tx.transactionType === 'contract_creation')
      );
    if (activeTab === 'pending') return matchesSearch && tx.status === 'pending';

    return matchesSearch;
  });

  // Calculate pagination
  const totalPages = Math.ceil(filteredTransactions.length / parseInt(pageSize));
  const paginatedTransactions = filteredTransactions.slice(
    (activePage - 1) * parseInt(pageSize),
    activePage * parseInt(pageSize)
  );

  // Helper function to get transaction icon based on type
  const getTransactionIcon = (type: RealtimeTransaction['transactionType']) => {
    switch (type) {
      case 'send':
        return <IconArrowUp size={18} color="red" />;
      case 'receive':
        return <IconArrowDown size={18} color="green" />;
      case 'contract_interaction':
        return <IconExchange size={18} color="blue" />;
      case 'contract_creation':
        return <IconExchange size={18} color="purple" />; // Different color for creation
      default:
        return <IconExchange size={18} />;
    }
  };

  // Helper function to format date
  const formatDate = (dateInput: string | number | undefined) => {
    if (dateInput === undefined) return 'N/A';
    const date = typeof dateInput === 'string' ? new Date(dateInput) : new Date(dateInput * 1000); // Assuming numeric timestamp is in seconds
    return new Date(date).toLocaleString();
  };

  return (
    <div>
      <Group justify="space-between" mb="lg">
        <div>
          <Title order={2}>Transactions</Title>
          <Text c="dimmed" size="sm">
            View and analyze blockchain transactions
          </Text>
        </div>
        <Group>
          <Button leftSection={<IconFilter size={16} />} variant="light">
            Filter
          </Button>
          <Button leftSection={<IconExchange size={16} />} variant="filled">
            New Transaction
          </Button>
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
            {isConnecting && (
              <Badge color="yellow" leftSection={<IconWifi size={14} />}>
                Connecting...
              </Badge>
            )}
            {isConnected && (
              <Badge color="green" leftSection={<IconWifi size={14} />}>
                Connected
              </Badge>
            )}
            {connectionError && (
              <Badge color="red" leftSection={<IconWifiOff size={14} />}>
                {connectionError}
              </Badge>
            )}
            <ActionIcon
              variant="light"
              color="blue"
              size="lg"
              aria-label="Reconnect"
              onClick={() => {
                RealtimeTransactionService.disconnect();
                RealtimeTransactionService.connect();
              }}
              title="Reconnect"
            >
              <IconRefresh size={18} />
            </ActionIcon>
          </Group>
        </Group>

        <Tabs value={activeTab} onChange={(value) => setActiveTab(value || 'all')} mb="md">
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
              <Table.Th>Value</Table.Th>
              <Table.Th>Network/Token</Table.Th>
              <Table.Th>Time</Table.Th>
              <Table.Th>Status</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {paginatedTransactions.map((tx) => (
              <Table.Tr key={tx.hash}>
                <Table.Td>
                  <Group gap="xs">
                    {getTransactionIcon(tx.transactionType)}
                    <Text size="sm">{tx.transactionType || 'N/A'}</Text>
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" style={{ fontFamily: 'monospace' }}>
                    {tx.hash}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" style={{ fontFamily: 'monospace' }}>
                    {tx.from}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" style={{ fontFamily: 'monospace' }}>
                    {tx.to}
                  </Text>
                </Table.Td>
                <Table.Td>
                  {/* TODO: Format large numbers appropriately */}
                  <Text size="sm" c="dimmed">
                    {tx.value}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {tx.network || tx.tokenSymbol || 'N/A'}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {formatDate(tx.timestamp)}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Badge
                    color={
                      tx.status === 'Confirmed'
                        ? 'green'
                        : tx.status === 'pending'
                          ? 'yellow'
                          : 'gray'
                    }
                  >
                    {tx.status || 'N/A'}
                  </Badge>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>

        {filteredTransactions.length > parseInt(pageSize) && (
          <Group justify="center" mt="xl">
            <Pagination value={activePage} onChange={setActivePage} total={totalPages} />
          </Group>
        )}
      </Card>
    </div>
  );
}
