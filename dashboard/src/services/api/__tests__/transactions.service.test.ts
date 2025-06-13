/**
 * Tests for the transactions API service.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TransactionsService, Transaction, TransactionsQuery } from '../transactions.service';
import ApiService from '../../ApiService';

// Mock ApiService
vi.mock('../../ApiService', () => ({
  default: {
    fetchData: vi.fn(),
  },
}));

// Mock app config
vi.mock('@/configs/app.config', () => ({
  default: {
    apiPrefix: '/api/v1',
  },
}));

const mockApiService = ApiService as any;

describe('TransactionsService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const mockTransaction: Transaction = {
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
    decodedCall: {
      function: 'Transfer',
      params: { to: '0x8ba1f109551bD432803012645Hac136c22C177e9', value: '2.5' }
    },
    tokenSymbol: 'AVAX',
    transactionType: 'send'
  };

  const mockTransactionsResponse = {
    transactions: [mockTransaction],
    total: 1,
    limit: 20,
    offset: 0,
    hasMore: false
  };

  describe('getTransactions', () => {
    it('should fetch transactions with default parameters', async () => {
      mockApiService.fetchData.mockResolvedValue({
        data: mockTransactionsResponse
      });

      const result = await TransactionsService.getTransactions();

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: '/transactions?',
        method: 'GET',
      });
      expect(result).toEqual(mockTransactionsResponse);
    });

    it('should fetch transactions with query parameters', async () => {
      mockApiService.fetchData.mockResolvedValue({
        data: mockTransactionsResponse
      });

      const query: TransactionsQuery = {
        walletAddresses: ['0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416'],
        networks: ['avalanche'],
        status: ['confirmed'],
        limit: 10,
        offset: 0,
        sortBy: 'timestamp',
        sortOrder: 'desc'
      };

      const result = await TransactionsService.getTransactions(query);

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: expect.stringContaining('wallet_addresses=0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416'),
        method: 'GET',
      });
      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: expect.stringContaining('networks=avalanche'),
        method: 'GET',
      });
      expect(result).toEqual(mockTransactionsResponse);
    });

    it('should handle multiple wallet addresses', async () => {
      mockApiService.fetchData.mockResolvedValue({
        data: mockTransactionsResponse
      });

      const query: TransactionsQuery = {
        walletAddresses: [
          '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416',
          '0x8ba1f109551bD432803012645Hac136c22C177e9'
        ]
      };

      await TransactionsService.getTransactions(query);

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: expect.stringContaining('wallet_addresses=0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416%2C0x8ba1f109551bD432803012645Hac136c22C177e9'),
        method: 'GET',
      });
    });

    it('should handle date range filters', async () => {
      mockApiService.fetchData.mockResolvedValue({
        data: mockTransactionsResponse
      });

      const query: TransactionsQuery = {
        fromDate: '2025-01-01T00:00:00Z',
        toDate: '2025-01-07T23:59:59Z'
      };

      await TransactionsService.getTransactions(query);

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: expect.stringContaining('from_date=2025-01-01T00%3A00%3A00Z'),
        method: 'GET',
      });
      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: expect.stringContaining('to_date=2025-01-07T23%3A59%3A59Z'),
        method: 'GET',
      });
    });

    it('should handle search parameter', async () => {
      mockApiService.fetchData.mockResolvedValue({
        data: mockTransactionsResponse
      });

      const query: TransactionsQuery = {
        search: '0x1a2b3c4d'
      };

      await TransactionsService.getTransactions(query);

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: expect.stringContaining('search=0x1a2b3c4d'),
        method: 'GET',
      });
    });

    it('should handle API errors', async () => {
      const errorMessage = 'Network error';
      mockApiService.fetchData.mockRejectedValue(new Error(errorMessage));

      await expect(TransactionsService.getTransactions()).rejects.toThrow(errorMessage);
    });
  });

  describe('getTransaction', () => {
    it('should fetch a single transaction by hash', async () => {
      mockApiService.fetchData.mockResolvedValue({
        data: mockTransaction
      });

      const hash = '0x1a2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890';
      const result = await TransactionsService.getTransaction(hash);

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: `/transactions/${hash}`,
        method: 'GET',
      });
      expect(result).toEqual(mockTransaction);
    });

    it('should handle transaction not found', async () => {
      mockApiService.fetchData.mockRejectedValue(new Error('Transaction not found'));

      const hash = '0xinvalidhash';
      await expect(TransactionsService.getTransaction(hash)).rejects.toThrow('Transaction not found');
    });
  });

  describe('getTransactionStats', () => {
    it('should fetch transaction statistics', async () => {
      const mockStats = {
        totalTransactions: 100,
        totalValue: '1000000000000000000000',
        averageGasPrice: '25000000000',
        networkBreakdown: [
          { network: 'avalanche', count: 80, percentage: 80 },
          { network: 'ethereum', count: 20, percentage: 20 }
        ],
        typeBreakdown: [
          { type: 'send', count: 50, percentage: 50 },
          { type: 'receive', count: 30, percentage: 30 }
        ],
        dailyVolume: [
          { date: '2025-01-07', count: 10, value: '100000000000000000000' }
        ]
      };

      mockApiService.fetchData.mockResolvedValue({
        data: mockStats
      });

      const result = await TransactionsService.getTransactionStats();

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: '/transactions/stats?',
        method: 'GET',
      });
      expect(result).toEqual(mockStats);
    });

    it('should fetch stats with filters', async () => {
      const mockStats = {
        totalTransactions: 50,
        totalValue: '500000000000000000000',
        averageGasPrice: '25000000000',
        networkBreakdown: [],
        typeBreakdown: [],
        dailyVolume: []
      };

      mockApiService.fetchData.mockResolvedValue({
        data: mockStats
      });

      const query = {
        walletAddresses: ['0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416'],
        networks: ['avalanche']
      };

      const result = await TransactionsService.getTransactionStats(query);

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: expect.stringContaining('wallet_addresses=0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416'),
        method: 'GET',
      });
      expect(result).toEqual(mockStats);
    });
  });

  describe('getWalletTransactions', () => {
    it('should fetch transactions for a specific wallet', async () => {
      const mockWalletTransactions = {
        transactions: [mockTransaction]
      };

      mockApiService.fetchData.mockResolvedValue({
        data: mockWalletTransactions
      });

      const walletAddress = '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416';
      const result = await TransactionsService.getWalletTransactions(walletAddress, 5);

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: `/wallets/${walletAddress}/transactions?limit=5`,
        method: 'GET',
      });
      expect(result).toEqual([mockTransaction]);
    });

    it('should use default limit when not provided', async () => {
      const mockWalletTransactions = {
        transactions: [mockTransaction]
      };

      mockApiService.fetchData.mockResolvedValue({
        data: mockWalletTransactions
      });

      const walletAddress = '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416';
      await TransactionsService.getWalletTransactions(walletAddress);

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: `/wallets/${walletAddress}/transactions?limit=10`,
        method: 'GET',
      });
    });
  });

  describe('exportTransactions', () => {
    it('should export transactions as CSV', async () => {
      const mockBlob = new Blob(['csv,data'], { type: 'text/csv' });
      
      // Mock fetch
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        blob: () => Promise.resolve(mockBlob)
      });

      // Mock localStorage
      Object.defineProperty(window, 'localStorage', {
        value: {
          getItem: vi.fn().mockReturnValue('mock-token')
        }
      });

      const query: TransactionsQuery = {
        walletAddresses: ['0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416']
      };

      const result = await TransactionsService.exportTransactions(query);

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/transactions/export'),
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'Authorization': 'Bearer mock-token'
          })
        })
      );
      expect(result).toEqual(mockBlob);
    });

    it('should handle export errors', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500
      });

      await expect(TransactionsService.exportTransactions()).rejects.toThrow('Failed to export transactions');
    });

    it('should handle network errors during export', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

      await expect(TransactionsService.exportTransactions()).rejects.toThrow('Network error');
    });
  });

  describe('URL parameter encoding', () => {
    it('should properly encode special characters in parameters', async () => {
      mockApiService.fetchData.mockResolvedValue({
        data: mockTransactionsResponse
      });

      const query: TransactionsQuery = {
        search: 'test@example.com',
        walletAddresses: ['0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416']
      };

      await TransactionsService.getTransactions(query);

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: expect.stringContaining('search=test%40example.com'),
        method: 'GET',
      });
    });

    it('should handle empty arrays in parameters', async () => {
      mockApiService.fetchData.mockResolvedValue({
        data: mockTransactionsResponse
      });

      const query: TransactionsQuery = {
        walletAddresses: [],
        networks: []
      };

      await TransactionsService.getTransactions(query);

      // Should not include empty array parameters in URL
      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: '/transactions?',
        method: 'GET',
      });
    });
  });
});
