import ApiService from "@/services/ApiService";
import type { Wallet } from "@/@types/wallet";

// Helper function to handle API errors
const handleApiError = (error: any, operation: string) => {
  console.error(`Error ${operation}:`, error);
  if (error.response) {
    // The request was made and the server responded with a status code
    // that falls out of the range of 2xx
    console.error('Response data:', error.response.data);
    console.error('Response status:', error.response.status);
    throw new Error(error.response.data?.detail || `Failed to ${operation}`);
  } else if (error.request) {
    // The request was made but no response was received
    console.error('No response received:', error.request);
    throw new Error(`No response from server while trying to ${operation}`);
  } else {
    // Something happened in setting up the request that triggered an Error
    throw new Error(`Error occurred while trying to ${operation}: ${error.message}`);
  }
};

export const WalletService = {
  async getWallets(): Promise<Wallet[]> {
    try {
      const res = await ApiService.fetchData<null, Wallet[]>({
        url: '/wallets',
        method: 'GET'
      });
      return res.data;
    } catch (error) {
      return handleApiError(error, 'fetch wallets');
    }
  },

  async getWallet(id: string): Promise<Wallet> {
    try {
      const res = await ApiService.fetchData<null, Wallet>({
        url: `/wallets/${id}`,
        method: 'GET'
      });
      return res.data;
    } catch (error) {
      return handleApiError(error, 'fetch wallet');
    }
  },

  async createWallet(walletData: Omit<Wallet, 'id' | 'created_at' | 'updated_at'>): Promise<Wallet> {
    try {
      console.log('Creating wallet with data:', walletData);
      const res = await ApiService.fetchData<Partial<Wallet>, Wallet>({
        url: '/wallets',
        method: 'POST',
        data: walletData
      });
      console.log('Wallet created successfully:', res.data);
      return res.data;
    } catch (error) {
      return handleApiError(error, 'create wallet');
    }
  },

  async updateWallet(id: string, walletData: Partial<Wallet>): Promise<Wallet> {
    try {
      const res = await ApiService.fetchData<Partial<Wallet>, Wallet>({
        url: `/wallets/${id}`,
        method: 'PUT',
        data: walletData
      });
      return res.data;
    } catch (error) {
      return handleApiError(error, 'update wallet');
    }
  },

  async deleteWallet(id: string): Promise<void> {
    try {
      await ApiService.fetchData<null, void>({
        url: `/wallets/${id}`,
        method: 'DELETE'
      });
    } catch (error) {
      handleApiError(error, 'delete wallet');
    }
  }
};
