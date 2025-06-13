/**
 * Tests for the useTransactions hook.
 */

import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { useTransactions } from '../useTransactions';
import { TransactionsService } from '@/services/api/transactions.service';

// Mock the transactions service
vi.mock('@/services/api/transactions.service', () => ({
  TransactionsService: {
    getTransactions: vi.fn(),
    exportTransactions: vi.fn(),
  },
}));

// Mock the store selectors
vi.mock('@/store', () => ({
  useAppSelector: vi.fn(),
}));

// Mock the wallet selectors
vi.mock('@/store/selectors/walletsSelectors', () => ({
  selectMonitoredWallets: vi.fn(),
}));

const mockTransactionsService = TransactionsService as any;

// Mock store setup
const createMockStore = (wallets = []) => {
  return configureStore({
    reducer: {
      wallets: (state = { monitored: wallets }) => state,
    },
  });
};

// Mock wallet data
const mockWallets = [
  {
    id: '1',
    address: '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416',
    name: 'Main Wallet',
    network: 'avalanche'
  },
  {
    id: '2',
    address: '0x8ba1f109551bD432803012645Hac136c22C177e9',
    name: 'Secondary Wallet',
    network: 'avalanche'
  }
];

// Mock transaction data
const mockTransactions = [
  {
    hash: '0x1a2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890',
    from: '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416',
    to: '0x8ba1f109551bD432803012645Hac136c22C177e9',
    value: '2500000000000000000',
    gas: '21000',
    gasPrice: '20000000000',
    nonce: '42',
    input: '0x',
    blockNumber: 18500000,
    blockHash: '0xabc123def456...',
    transactionIndex: 0,
    timestamp: '2025-01-07T10:30:00Z',
    network: 'avalanche',
    subnet: 'mainnet',
    status: 'confirmed',
    tokenSymbol: 'AVAX',
    transactionType: 'send'
  }
];

const mockTransactionsResponse = {
  transactions: mockTransactions,
  total: 1,
  limit: 20,
  offset: 0,
  hasMore: false
};

describe('useTransactions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock useAppSelector to return mock wallets
    const { useAppSelector } = require('@/store');
    useAppSelector.mockReturnValue(mockWallets);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const renderHookWithProvider = (options = {}) => {
    const store = createMockStore(mockWallets);
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    
    return renderHook(() => useTransactions(options), { wrapper });
  };

  it('should initialize with default state', async () => {
    mockTransactionsService.getTransactions.mockResolvedValue(mockTransactionsResponse);

    const { result } = renderHookWithProvider();

    expect(result.current.transactions).toEqual([]);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(null);
    expect(result.current.total).toBe(0);
    expect(result.current.hasMore).toBe(false);

    // Wait for initial fetch
    await waitFor(() => {
      expect(result.current.transactions).toEqual(mockTransactions);
    });
  });

  it('should fetch transactions on mount', async () => {
    mockTransactionsService.getTransactions.mockResolvedValue(mockTransactionsResponse);

    const { result } = renderHookWithProvider();

    await waitFor(() => {
      expect(mockTransactionsService.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({
          walletAddresses: ['0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416', '0x8ba1f109551bD432803012645Hac136c22C177e9'],
          networks: ['avalanche'],
          limit: 20,
          offset: 0,
          sortBy: 'timestamp',
          sortOrder: 'desc'
        })
      );
    });

    await waitFor(() => {
      expect(result.current.transactions).toEqual(mockTransactions);
      expect(result.current.total).toBe(1);
      expect(result.current.hasMore).toBe(false);
    });
  });

  it('should handle loading state', async () => {
    let resolvePromise: (value: any) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    
    mockTransactionsService.getTransactions.mockReturnValue(promise);

    const { result } = renderHookWithProvider();

    await waitFor(() => {
      expect(result.current.loading).toBe(true);
    });

    act(() => {
      resolvePromise!(mockTransactionsResponse);
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
  });

  it('should handle API errors', async () => {
    const errorMessage = 'Failed to fetch transactions';
    mockTransactionsService.getTransactions.mockRejectedValue(new Error(errorMessage));

    const { result } = renderHookWithProvider();

    await waitFor(() => {
      expect(result.current.error).toBe(errorMessage);
      expect(result.current.loading).toBe(false);
    });
  });

  it('should update query and refetch', async () => {
    mockTransactionsService.getTransactions.mockResolvedValue(mockTransactionsResponse);

    const { result } = renderHookWithProvider();

    await waitFor(() => {
      expect(result.current.transactions).toEqual(mockTransactions);
    });

    const newQuery = {
      search: 'test',
      limit: 10,
      offset: 0
    };

    act(() => {
      result.current.updateQuery(newQuery);
    });

    await waitFor(() => {
      expect(mockTransactionsService.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({
          search: 'test',
          limit: 10,
          offset: 0
        })
      );
    });
  });

  it('should load more transactions', async () => {
    const initialResponse = {
      transactions: mockTransactions,
      total: 2,
      limit: 1,
      offset: 0,
      hasMore: true
    };

    const moreTransactions = [{
      ...mockTransactions[0],
      hash: '0x2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890ab'
    }];

    const moreResponse = {
      transactions: moreTransactions,
      total: 2,
      limit: 1,
      offset: 1,
      hasMore: false
    };

    mockTransactionsService.getTransactions
      .mockResolvedValueOnce(initialResponse)
      .mockResolvedValueOnce(moreResponse);

    const { result } = renderHookWithProvider({
      initialQuery: { limit: 1 }
    });

    await waitFor(() => {
      expect(result.current.transactions).toHaveLength(1);
      expect(result.current.hasMore).toBe(true);
    });

    act(() => {
      result.current.loadMore();
    });

    await waitFor(() => {
      expect(result.current.transactions).toHaveLength(2);
      expect(result.current.hasMore).toBe(false);
    });
  });

  it('should refresh transactions', async () => {
    mockTransactionsService.getTransactions.mockResolvedValue(mockTransactionsResponse);

    const { result } = renderHookWithProvider();

    await waitFor(() => {
      expect(result.current.transactions).toEqual(mockTransactions);
    });

    // Clear mock calls
    mockTransactionsService.getTransactions.mockClear();

    act(() => {
      result.current.refresh();
    });

    await waitFor(() => {
      expect(mockTransactionsService.getTransactions).toHaveBeenCalledTimes(1);
    });
  });

  it('should export transactions', async () => {
    const mockBlob = new Blob(['csv,data'], { type: 'text/csv' });
    mockTransactionsService.exportTransactions.mockResolvedValue(mockBlob);
    mockTransactionsService.getTransactions.mockResolvedValue(mockTransactionsResponse);

    // Mock DOM methods
    const mockCreateElement = vi.fn();
    const mockAppendChild = vi.fn();
    const mockRemoveChild = vi.fn();
    const mockClick = vi.fn();
    const mockCreateObjectURL = vi.fn().mockReturnValue('blob:url');
    const mockRevokeObjectURL = vi.fn();

    const mockLink = {
      href: '',
      download: '',
      click: mockClick
    };

    mockCreateElement.mockReturnValue(mockLink);

    Object.defineProperty(document, 'createElement', {
      value: mockCreateElement
    });
    Object.defineProperty(document.body, 'appendChild', {
      value: mockAppendChild
    });
    Object.defineProperty(document.body, 'removeChild', {
      value: mockRemoveChild
    });
    Object.defineProperty(window.URL, 'createObjectURL', {
      value: mockCreateObjectURL
    });
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      value: mockRevokeObjectURL
    });

    const { result } = renderHookWithProvider();

    await waitFor(() => {
      expect(result.current.transactions).toEqual(mockTransactions);
    });

    act(() => {
      result.current.exportTransactions();
    });

    await waitFor(() => {
      expect(mockTransactionsService.exportTransactions).toHaveBeenCalled();
      expect(mockCreateElement).toHaveBeenCalledWith('a');
      expect(mockClick).toHaveBeenCalled();
    });
  });

  it('should handle export errors', async () => {
    mockTransactionsService.getTransactions.mockResolvedValue(mockTransactionsResponse);
    mockTransactionsService.exportTransactions.mockRejectedValue(new Error('Export failed'));

    const { result } = renderHookWithProvider();

    await waitFor(() => {
      expect(result.current.transactions).toEqual(mockTransactions);
    });

    act(() => {
      result.current.exportTransactions();
    });

    await waitFor(() => {
      expect(result.current.error).toBe('Failed to export transactions');
    });
  });

  it('should auto-refresh when enabled', async () => {
    vi.useFakeTimers();
    
    mockTransactionsService.getTransactions.mockResolvedValue(mockTransactionsResponse);

    const { result } = renderHookWithProvider({
      autoRefresh: true,
      refreshInterval: 1000
    });

    await waitFor(() => {
      expect(result.current.transactions).toEqual(mockTransactions);
    });

    // Clear initial calls
    mockTransactionsService.getTransactions.mockClear();

    // Fast-forward time
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    await waitFor(() => {
      expect(mockTransactionsService.getTransactions).toHaveBeenCalledTimes(1);
    });

    vi.useRealTimers();
  });

  it('should not auto-refresh when disabled', async () => {
    vi.useFakeTimers();
    
    mockTransactionsService.getTransactions.mockResolvedValue(mockTransactionsResponse);

    const { result } = renderHookWithProvider({
      autoRefresh: false
    });

    await waitFor(() => {
      expect(result.current.transactions).toEqual(mockTransactions);
    });

    // Clear initial calls
    mockTransactionsService.getTransactions.mockClear();

    // Fast-forward time
    act(() => {
      vi.advanceTimersByTime(30000);
    });

    // Should not have been called again
    expect(mockTransactionsService.getTransactions).not.toHaveBeenCalled();

    vi.useRealTimers();
  });

  it('should handle empty wallet addresses', async () => {
    const { useAppSelector } = require('@/store');
    useAppSelector.mockReturnValue([]); // No wallets

    const { result } = renderHookWithProvider();

    await waitFor(() => {
      expect(result.current.transactions).toEqual([]);
      expect(result.current.total).toBe(0);
    });

    // Should not call API when no wallets
    expect(mockTransactionsService.getTransactions).not.toHaveBeenCalled();
  });

  it('should prevent load more when already loading', async () => {
    const initialResponse = {
      transactions: mockTransactions,
      total: 2,
      limit: 1,
      offset: 0,
      hasMore: true
    };

    let resolvePromise: (value: any) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });

    mockTransactionsService.getTransactions
      .mockResolvedValueOnce(initialResponse)
      .mockReturnValueOnce(promise);

    const { result } = renderHookWithProvider({
      initialQuery: { limit: 1 }
    });

    await waitFor(() => {
      expect(result.current.hasMore).toBe(true);
    });

    // Start loading more
    act(() => {
      result.current.loadMore();
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(true);
    });

    // Try to load more again while loading
    const callCountBefore = mockTransactionsService.getTransactions.mock.calls.length;
    
    act(() => {
      result.current.loadMore();
    });

    // Should not make additional call
    expect(mockTransactionsService.getTransactions.mock.calls.length).toBe(callCountBefore);
  });
});
