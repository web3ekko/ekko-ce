import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useAppSelector } from '@/store';
import { selectMonitoredWallets } from '@/store/selectors/walletsSelectors';
import { TransactionsService, Transaction, TransactionsQuery, TransactionsResponse } from '@/services/api/transactions.service';

interface UseTransactionsOptions {
  autoRefresh?: boolean;
  refreshInterval?: number; // in milliseconds
  initialQuery?: TransactionsQuery;
}

interface UseTransactionsReturn {
  transactions: Transaction[];
  loading: boolean;
  error: string | null;
  total: number;
  hasMore: boolean;
  query: TransactionsQuery;
  setQuery: (query: TransactionsQuery) => void;
  updateQuery: (partialQuery: Partial<TransactionsQuery>) => void;
  refresh: () => Promise<void>;
  loadMore: () => Promise<void>;
  exportTransactions: () => Promise<void>;
}

export const useTransactions = (options: UseTransactionsOptions = {}): UseTransactionsReturn => {
  const {
    autoRefresh = true,
    refreshInterval = 30000, // 30 seconds
    initialQuery = {}
  } = options;

  // Get monitored wallets from store
  const monitoredWallets = useAppSelector(selectMonitoredWallets);

  // State
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  // Default query with monitored wallet addresses
  const defaultQuery: TransactionsQuery = useMemo(() => ({
    limit: 20,
    offset: 0,
    sortBy: 'timestamp',
    sortOrder: 'desc',
    walletAddresses: monitoredWallets.map(w => w.address),
    networks: ['avalanche'], // Default to Avalanche as requested
    ...initialQuery,
  }), [monitoredWallets, initialQuery]);

  const [query, setQueryState] = useState<TransactionsQuery>(defaultQuery);

  // Use refs to avoid stale closures in intervals
  const queryRef = useRef(query);
  const loadingRef = useRef(loading);

  // Update refs when state changes
  useEffect(() => {
    queryRef.current = query;
  }, [query]);

  useEffect(() => {
    loadingRef.current = loading;
  }, [loading]);

  // Update query when monitored wallets change (commented out to show all transactions)
  // Note: Commented out to show all Avalanche transactions, not just monitored wallets
  // useEffect(() => {
  //   if (monitoredWallets.length > 0) {
  //     setQueryState(prev => ({
  //       ...prev,
  //       walletAddresses: monitoredWallets.map(w => w.address),
  //     }));
  //   }
  // }, [monitoredWallets]);

  // Fetch transactions
  const fetchTransactions = useCallback(async (queryParams: TransactionsQuery, append = false) => {
    // Remove wallet filtering to show all transactions
    // if (!queryParams.walletAddresses?.length) {
    //   // No wallets to monitor, clear transactions
    //   setTransactions([]);
    //   setTotal(0);
    //   setHasMore(false);
    //   return;
    // }

    setLoading(true);
    setError(null);

    try {
      const response: TransactionsResponse = await TransactionsService.getTransactions(queryParams);

      if (append) {
        setTransactions(prev => [...prev, ...response.transactions]);
      } else {
        setTransactions(response.transactions);
      }

      setTotal(response.total);
      setHasMore(response.hasMore);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch transactions';
      setError(errorMessage);
      console.error('Error fetching transactions:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Set query and fetch
  const setQuery = useCallback((newQuery: TransactionsQuery) => {
    setQueryState(newQuery);
    fetchTransactions(newQuery, false);
  }, [fetchTransactions]);

  // Update query partially
  const updateQuery = useCallback((partialQuery: Partial<TransactionsQuery>) => {
    setQueryState(prevQuery => {
      const newQuery = { ...prevQuery, ...partialQuery, offset: 0 }; // Reset offset when updating query
      fetchTransactions(newQuery, false);
      return newQuery;
    });
  }, [fetchTransactions]);

  // Refresh current query
  const refresh = useCallback(async () => {
    await fetchTransactions(query, false);
  }, [query, fetchTransactions]);

  // Load more transactions (pagination)
  const loadMore = useCallback(async () => {
    if (!hasMore || loading) return;

    const nextQuery = {
      ...query,
      offset: (query.offset || 0) + (query.limit || 20),
    };

    await fetchTransactions(nextQuery, true);
  }, [query, hasMore, loading, fetchTransactions]);

  // Export transactions
  const exportTransactions = useCallback(async () => {
    try {
      const blob = await TransactionsService.exportTransactions(query);

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `transactions_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error exporting transactions:', err);
      setError('Failed to export transactions');
    }
  }, [query]);

  // Initial fetch - run once on mount
  useEffect(() => {
    fetchTransactions(queryRef.current, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Intentionally empty - only run on mount

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      // Refresh if we're not loading (use refs to avoid stale closures)
      if (!loadingRef.current) {
        fetchTransactions(queryRef.current, false);
      }
    }, refreshInterval);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, refreshInterval]); // Intentionally limited dependencies

  return {
    transactions,
    loading,
    error,
    total,
    hasMore,
    query,
    setQuery,
    updateQuery,
    refresh,
    loadMore,
    exportTransactions,
  };
};

// Hook for transaction statistics
export const useTransactionStats = (query: Omit<TransactionsQuery, 'limit' | 'offset' | 'sortBy' | 'sortOrder'> = {}) => {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await TransactionsService.getTransactionStats(query);
      setStats(response);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch transaction stats';
      setError(errorMessage);
      console.error('Error fetching transaction stats:', err);
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return {
    stats,
    loading,
    error,
    refresh: fetchStats,
  };
};
