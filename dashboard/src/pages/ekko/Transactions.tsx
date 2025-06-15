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
  Stack,
  Center,
  Loader,
  Tooltip,
  Box,
  rem,
  Alert,
  MultiSelect,
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

import { useAppSelector } from '@/store';
import RealtimeTransactionService from '@/services/realtime/RealtimeTransactionService';
import {
  selectAllRealtimeTransactions,
  selectIsConnectingToRealtime,
  selectIsConnectedToRealtime,
  selectRealtimeConnectionError,
} from '@/store/selectors/realtimeTransactionsSelectors';
import { useTransactions } from '@/hooks/useTransactions';
import { Transaction } from '@/services/api/transactions.service';
import type { RealtimeTransaction } from '@/store/slices/realtimeTransactionsSlice';

// Note: Dummy data removed - using real API exclusively
export default function Transactions() {
  // Real-time connection state (for status display)
  const liveTransactions = useAppSelector(selectAllRealtimeTransactions);
  const isConnecting = useAppSelector(selectIsConnectingToRealtime);
  const isConnected = useAppSelector(selectIsConnectedToRealtime);
  const connectionError = useAppSelector(selectRealtimeConnectionError);

  // Local state for UI
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [networkFilter, setNetworkFilter] = useState<string[]>([]);

  // Use the new API-based transactions hook
  const {
    transactions: apiTransactions,
    loading,
    error,
    total,
    hasMore,
    query,
    updateQuery,
    refresh,
    loadMore,
    exportTransactions,
  } = useTransactions({
    autoRefresh: false, // Disabled to prevent infinite requests
    refreshInterval: 30000, // 30 seconds
    initialQuery: {
      limit: 20,
      networks: ['avalanche'], // Keep Avalanche filtering as requested
      sortBy: 'timestamp',
      sortOrder: 'desc',
    },
  });

  // Effect for WebSocket connection management (for real-time updates)
  // Disabled to prevent connection issues
  // useEffect(() => {
  //   RealtimeTransactionService.connect();
  //   return () => {
  //     RealtimeTransactionService.disconnect();
  //   };
  // }, []);

  // Handle search and filtering (disabled to prevent loops)
  // useEffect(() => {
  //   if (searchQuery) {
  //     updateQuery({
  //       search: searchQuery,
  //       offset: 0, // Reset to first page when searching
  //     });
  //   } else {
  //     updateQuery({
  //       search: undefined,
  //       offset: 0,
  //     });
  //   }
  //   // eslint-disable-next-line react-hooks/exhaustive-deps
  // }, [searchQuery]); // Removed updateQuery to prevent infinite loops

  // Handle tab filtering (disabled to prevent loops)
  // useEffect(() => {
  //   const transactionTypes: string[] = [];
  //   const statuses: string[] = [];

  //   switch (activeTab) {
  //     case 'send':
  //       transactionTypes.push('send');
  //       break;
  //     case 'receive':
  //       transactionTypes.push('receive');
  //       break;
  //     case 'contract':
  //       transactionTypes.push('contract_interaction', 'contract_creation');
  //       break;
  //     case 'pending':
  //       statuses.push('pending');
  //       break;
  //     default:
  //       // 'all' - no filters
  //       break;
  //   }

  //   updateQuery({
  //     transactionTypes: transactionTypes.length > 0 ? transactionTypes : undefined,
  //     status: statuses.length > 0 ? statuses : undefined,
  //     offset: 0, // Reset to first page when changing tabs
  //   });
  //   // eslint-disable-next-line react-hooks/exhaustive-deps
  // }, [activeTab]); // Removed updateQuery to prevent infinite loops

  // Use API transactions exclusively
  const displayTransactions = apiTransactions;

  // Handle page size changes
  const handlePageSizeChange = (newPageSize: string) => {
    updateQuery({
      limit: parseInt(newPageSize),
      offset: 0, // Reset to first page
    });
  };

  // Handle load more for API pagination
  const handleLoadMore = () => {
    if (hasMore && !loading) {
      loadMore();
    }
  };

  // Helper function to get transaction icon based on type
  const getTransactionIcon = (tx: Transaction | RealtimeTransaction) => {
    const type = 'details' in tx ? tx.details?.transaction_type : tx.transactionType;
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

  // Helper function to get transaction type
  const getTransactionType = (tx: Transaction | RealtimeTransaction) => {
    return 'details' in tx ? tx.details?.transaction_type : (tx as RealtimeTransaction).transactionType;
  };

  // Helper function to get token symbol
  const getTokenSymbol = (tx: Transaction | RealtimeTransaction) => {
    return 'details' in tx ? tx.details?.token_symbol : (tx as RealtimeTransaction).tokenSymbol;
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
      subtitle="View and analyze blockchain transactions (for tracked wallets)"
      action={
        <Group>
          <Button
            variant="light"
            leftSection={<IconDownload size={16} />}
            onClick={exportTransactions}
            disabled={loading}
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
              value={query.limit?.toString() || '20'}
              onChange={(value) => handlePageSizeChange(value || '20')}
              data={['10', '20', '50', '100']}
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

        {loading ? (
          <Center p="xl">
            <Loader size="md" />
          </Center>
        ) : error ? (
          <Center p="xl">
            <Alert color="red" title="Error loading transactions">
              {error}
              <Button variant="light" size="sm" onClick={refresh} mt="sm">
                Retry
              </Button>
            </Alert>
          </Center>
        ) : displayTransactions.length === 0 ? (
          <Center p="xl">
            <Stack align="center">
              <Text c="dimmed">No transactions found</Text>
              <Text size="sm" c="dimmed">
                {loading
                  ? 'Loading transactions...'
                  : total === 0
                    ? 'No transactions available for monitored wallets'
                    : 'Try adjusting your search criteria'
                }
              </Text>
            </Stack>
          </Center>
        ) : (
          <Stack gap="sm" p="md">
            {displayTransactions.map((tx: Transaction | RealtimeTransaction) => (
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
                      {getTransactionIcon(tx)}
                    </Box>

                    <Box>
                      <Group gap="xs" mb="xs">
                        <Text fw={600} tt="capitalize">{getTransactionType(tx) || 'Transaction'}</Text>
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
                          {tx.network || getTokenSymbol(tx) || 'Unknown'}
                        </Badge>
                      </Group>
                    </Box>
                  </Group>

                  <Box style={{ textAlign: 'right' }}>
                    <Text fw={600} size="lg">
                      {tx.value || '0'} {getTokenSymbol(tx) || 'ETH'}
                    </Text>
                    <Text size="sm" c="dimmed">
                      {('details' in tx ? tx.details?.decoded_call?.function :
                        'decoded_call' in tx ? tx.decoded_call?.function : null) || 'Transfer'}
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

        {/* Load More Button for API pagination */}
        {hasMore && (
          <Group justify="center" mt="xl" p="md">
            <Button
              variant="light"
              onClick={handleLoadMore}
              loading={loading}
              disabled={!hasMore}
            >
              Load More Transactions
            </Button>
          </Group>
        )}

        {/* Show total count */}
        {total > 0 && (
          <Group justify="center" mt="sm" p="md">
            <Text size="sm" c="dimmed">
              Showing {displayTransactions.length} of {total} transactions
            </Text>
          </Group>
        )}
      </IOSCard>
    </IOSPageWrapper>
  );
}
