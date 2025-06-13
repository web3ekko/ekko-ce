/**
 * Tests for the wallet service.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { walletService } from '../wallet.service';
import ApiService from '../../ApiService';

// Mock ApiService
vi.mock('../../ApiService', () => ({
  default: {
    fetchData: vi.fn(),
  },
}));

const mockApiService = ApiService as any;

describe('WalletService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const mockWallet = {
    id: '1',
    blockchain_symbol: 'AVAX',
    address: '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416',
    name: 'Main Avalanche Wallet',
    balance: 125.5,
    status: 'active',
    subnet: 'mainnet',
    description: 'Primary wallet for Avalanche transactions',
    created_at: '2025-01-06T10:30:00Z',
    updated_at: '2025-01-07T10:30:00Z'
  };

  describe('getWallets', () => {
    it('should fetch all wallets', async () => {
      const mockWallets = [mockWallet];
      mockApiService.fetchData.mockResolvedValue({
        data: mockWallets
      });

      const result = await walletService.getWallets();

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: '/wallets',
        method: 'GET',
      });
      expect(result).toEqual(mockWallets);
    });

    it('should handle API errors', async () => {
      const errorMessage = 'Network error';
      mockApiService.fetchData.mockRejectedValue(new Error(errorMessage));

      await expect(walletService.getWallets()).rejects.toThrow(errorMessage);
    });
  });

  describe('getWallet', () => {
    it('should fetch a single wallet by ID', async () => {
      mockApiService.fetchData.mockResolvedValue({
        data: mockWallet
      });

      const result = await walletService.getWallet('1');

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: '/wallets/1',
        method: 'GET',
      });
      expect(result).toEqual(mockWallet);
    });

    it('should handle wallet not found', async () => {
      mockApiService.fetchData.mockRejectedValue(new Error('Wallet not found'));

      await expect(walletService.getWallet('invalid-id')).rejects.toThrow('Wallet not found');
    });
  });

  describe('createWallet', () => {
    it('should create a new wallet', async () => {
      const walletData = {
        blockchain_symbol: 'AVAX',
        address: '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416',
        name: 'Main Avalanche Wallet',
        balance: 0,
        status: 'active',
        subnet: 'mainnet',
        description: 'Primary wallet for Avalanche transactions'
      };

      const createdWallet = {
        ...walletData,
        id: '1',
        created_at: '2025-01-07T10:30:00Z',
        updated_at: '2025-01-07T10:30:00Z'
      };

      mockApiService.fetchData.mockResolvedValue({
        data: createdWallet
      });

      const result = await walletService.createWallet(walletData);

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: '/wallets',
        method: 'POST',
        data: walletData,
      });
      expect(result).toEqual(createdWallet);
    });

    it('should handle creation errors', async () => {
      const walletData = {
        blockchain_symbol: 'AVAX',
        address: 'invalid-address',
        name: 'Test Wallet',
        balance: 0,
        status: 'active',
        subnet: 'mainnet',
        description: 'Test wallet'
      };

      mockApiService.fetchData.mockRejectedValue(new Error('Invalid wallet address'));

      await expect(walletService.createWallet(walletData)).rejects.toThrow('Invalid wallet address');
    });
  });

  describe('updateWallet', () => {
    it('should update an existing wallet', async () => {
      const updateData = {
        name: 'Updated Wallet Name',
        description: 'Updated description'
      };

      const updatedWallet = {
        ...mockWallet,
        ...updateData,
        updated_at: '2025-01-07T11:00:00Z'
      };

      mockApiService.fetchData.mockResolvedValue({
        data: updatedWallet
      });

      const result = await walletService.updateWallet('1', updateData);

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: '/wallets/1',
        method: 'PUT',
        data: updateData,
      });
      expect(result).toEqual(updatedWallet);
    });

    it('should handle update errors', async () => {
      mockApiService.fetchData.mockRejectedValue(new Error('Wallet not found'));

      await expect(walletService.updateWallet('invalid-id', { name: 'New Name' }))
        .rejects.toThrow('Wallet not found');
    });
  });

  describe('deleteWallet', () => {
    it('should delete a wallet', async () => {
      const deleteResponse = { status: 'deleted', id: '1' };
      mockApiService.fetchData.mockResolvedValue({
        data: deleteResponse
      });

      const result = await walletService.deleteWallet('1');

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: '/wallets/1',
        method: 'DELETE',
      });
      expect(result).toEqual(deleteResponse);
    });

    it('should handle deletion errors', async () => {
      mockApiService.fetchData.mockRejectedValue(new Error('Wallet not found'));

      await expect(walletService.deleteWallet('invalid-id')).rejects.toThrow('Wallet not found');
    });
  });

  describe('validateWalletAddress', () => {
    it('should validate Avalanche addresses', () => {
      const validAvaxAddress = '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416';
      expect(walletService.validateWalletAddress(validAvaxAddress, 'AVAX')).toBe(true);
    });

    it('should validate Ethereum addresses', () => {
      const validEthAddress = '0x8ba1f109551bD432803012645aac136c22C177e9';
      expect(walletService.validateWalletAddress(validEthAddress, 'ETH')).toBe(true);
    });

    it('should reject invalid addresses', () => {
      const invalidAddress = 'invalid-address';
      expect(walletService.validateWalletAddress(invalidAddress, 'AVAX')).toBe(false);
      expect(walletService.validateWalletAddress(invalidAddress, 'ETH')).toBe(false);
    });

    it('should reject addresses that are too short', () => {
      const shortAddress = '0x123';
      expect(walletService.validateWalletAddress(shortAddress, 'AVAX')).toBe(false);
    });

    it('should reject addresses without 0x prefix', () => {
      const addressWithoutPrefix = '742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416';
      expect(walletService.validateWalletAddress(addressWithoutPrefix, 'AVAX')).toBe(false);
    });
  });

  describe('formatWalletAddress', () => {
    it('should format long addresses with ellipsis', () => {
      const longAddress = '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416';
      const formatted = walletService.formatWalletAddress(longAddress);
      expect(formatted).toBe('0x742d35...e1e416');
    });

    it('should return short addresses as-is', () => {
      const shortAddress = '0x123456';
      const formatted = walletService.formatWalletAddress(shortAddress);
      expect(formatted).toBe('0x123456');
    });

    it('should handle empty addresses', () => {
      const formatted = walletService.formatWalletAddress('');
      expect(formatted).toBe('');
    });
  });

  describe('getWalletBalance', () => {
    it('should fetch wallet balance', async () => {
      const balanceResponse = { balance: 125.5, symbol: 'AVAX' };
      mockApiService.fetchData.mockResolvedValue({
        data: balanceResponse
      });

      const result = await walletService.getWalletBalance('0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416', 'AVAX');

      expect(mockApiService.fetchData).toHaveBeenCalledWith({
        url: '/wallets/balance',
        method: 'POST',
        data: {
          address: '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416',
          blockchain_symbol: 'AVAX'
        },
      });
      expect(result).toEqual(balanceResponse);
    });

    it('should handle balance fetch errors', async () => {
      mockApiService.fetchData.mockRejectedValue(new Error('Failed to fetch balance'));

      await expect(walletService.getWalletBalance('invalid-address', 'AVAX'))
        .rejects.toThrow('Failed to fetch balance');
    });
  });
});
