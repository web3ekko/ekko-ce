import React, { useState, useEffect } from 'react';
import {
  Text,
  Badge,
  Group,
  Button,
  TextInput,
  Pagination,
  Select,
  ActionIcon,
  Tabs,
  Table,
  Stack,
  Center,
  Loader,
  Tooltip,
  Box,
  rem,
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
  IconDownload,
  IconCopy,
  IconExternalLink,
} from '@tabler/icons-react';
import { IOSCard, IOSPageWrapper } from '@/components/UI/IOSCard';

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

  // Helper functions
  const truncateHash = (hash: string) => {
    return `${hash.substring(0, 6)}...${hash.substring(hash.length - 4)}`;
  };

  const truncateAddress = (address: string) => {
    return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    // You could add a notification here
  };

  return (
    <IOSPageWrapper
      title="Transactions"
      subtitle="View and analyze blockchain transactions"
      action={
        <Group>
          <Button
            variant="light"
            leftSection={<IconDownload size={16} />}
          >
            Export
          </Button>
          <Button leftSection={<IconExchange size={16} />} variant="filled">
            New Transaction
          </Button>
        </Group>
      }
    >

      <IOSCard>
        <Group justify="space-between" mb="md" p="md">
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

        {paginatedTransactions.length === 0 ? (
          <Center p="xl">
            <Stack align="center">
              <Text c="dimmed">No transactions found</Text>
              <Text size="sm" c="dimmed">
                {isConnected ? 'Waiting for new transactions...' : 'Connect to see live transactions'}
              </Text>
            </Stack>
          </Center>
        ) : (
          <Stack gap="sm" p="md">
            {paginatedTransactions.map((tx) => (
              <IOSCard key={tx.hash} interactive>
                <Group justify="space-between" p="md">
                  <Group>
                    <Box
                      style={{
                        padding: rem(8),
                        borderRadius: rem(8),
                        backgroundColor: '#f2f2f7',
                      }}
                    >
                      {getTransactionIcon(tx.transactionType)}
                    </Box>

                    <Box>
                      <Group gap="xs" mb="xs">
                        <Text fw={600} tt="capitalize">{tx.transactionType || 'Transaction'}</Text>
                        <Badge
                          color={
                            tx.status === 'Confirmed'
                              ? 'green'
                              : tx.status === 'pending'
                                ? 'orange'
                                : 'gray'
                          }
                          variant="light"
                        >
                          {tx.status || 'Unknown'}
                        </Badge>
                      </Group>

                      <Group gap="sm">
                        <Tooltip label="Copy hash">
                          <Button
                            variant="subtle"
                            size="xs"
                            leftSection={<IconCopy size={12} />}
                            onClick={() => copyToClipboard(tx.hash)}
                          >
                            {truncateHash(tx.hash)}
                          </Button>
                        </Tooltip>

                        <Text size="sm" c="dimmed">
                          {formatDate(tx.timestamp)}
                        </Text>

                        <Badge variant="outline" size="sm">
                          {tx.network || tx.tokenSymbol || 'Unknown'}
                        </Badge>
                      </Group>
                    </Box>
                  </Group>

                  <Box style={{ textAlign: 'right' }}>
                    <Text fw={600} size="lg">
                      {tx.value || '0'} {tx.tokenSymbol || 'ETH'}
                    </Text>
                    <Text size="sm" c="dimmed">
                      {tx.decoded_call?.function || 'Transfer'}
                    </Text>
                  </Box>

                  <ActionIcon variant="subtle" size="sm">
                    <IconExternalLink size={16} />
                  </ActionIcon>
                </Group>

                <Group justify="space-between" p="md" pt={0}>
                  <Group gap="sm">
                    <Text size="sm" c="dimmed">From:</Text>
                    <Tooltip label="Copy address">
                      <Button
                        variant="subtle"
                        size="xs"
                        onClick={() => copyToClipboard(tx.from)}
                      >
                        {truncateAddress(tx.from)}
                      </Button>
                    </Tooltip>
                  </Group>

                  {tx.to && (
                    <Group gap="sm">
                      <Text size="sm" c="dimmed">To:</Text>
                      <Tooltip label="Copy address">
                        <Button
                          variant="subtle"
                          size="xs"
                          onClick={() => copyToClipboard(tx.to!)}
                        >
                          {truncateAddress(tx.to)}
                        </Button>
                      </Tooltip>
                    </Group>
                  )}
                </Group>
              </IOSCard>
            ))}
          </Stack>
        )}

        {filteredTransactions.length > parseInt(pageSize) && (
          <Group justify="center" mt="xl" p="md">
            <Pagination value={activePage} onChange={setActivePage} total={totalPages} />
          </Group>
        )}
      </IOSCard>
    </IOSPageWrapper>
  );
}
