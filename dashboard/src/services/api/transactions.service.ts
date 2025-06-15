import ApiService from '../ApiService';
import appConfig from '@/configs/app.config';

// Transaction interface matching the pipeline output format
export interface Transaction {
  hash: string;
  from: string;
  to: string | null;
  value: string;
  gas: string;
  gasPrice: string;
  nonce: string;
  input: string;
  blockNumber: number;
  blockHash: string;
  transactionIndex: number;
  timestamp: string; // ISO timestamp
  network: string; // e.g., 'avalanche', 'ethereum'
  subnet: string; // e.g., 'mainnet', 'fuji'
  status: 'confirmed' | 'pending' | 'failed';
  details?: {
    token_symbol?: string;
    transaction_type?: 'send' | 'receive' | 'contract_interaction' | 'contract_creation';
    decoded_call?: {
      function: string;
      params: { [key: string]: any };
    };
  };
}

// API request/response interfaces
export interface TransactionsQuery {
  walletAddresses?: string[]; // Filter by specific wallet addresses
  networks?: string[]; // Filter by networks (e.g., ['avalanche', 'ethereum'])
  subnets?: string[]; // Filter by subnets (e.g., ['mainnet', 'fuji'])
  transactionTypes?: string[]; // Filter by transaction types
  status?: string[]; // Filter by status
  fromDate?: string; // ISO date string
  toDate?: string; // ISO date string
  search?: string; // Search in hash, addresses, or function names
  limit?: number; // Pagination limit (default: 50)
  offset?: number; // Pagination offset (default: 0)
  sortBy?: 'timestamp' | 'blockNumber' | 'value'; // Sort field
  sortOrder?: 'asc' | 'desc'; // Sort order (default: desc)
}

export interface TransactionsResponse {
  transactions: Transaction[];
  total: number;
  limit: number;
  offset: number;
  hasMore: boolean;
}

export interface TransactionStatsResponse {
  totalTransactions: number;
  totalValue: string;
  averageGasPrice: string;
  networkBreakdown: {
    network: string;
    count: number;
    percentage: number;
  }[];
  typeBreakdown: {
    type: string;
    count: number;
    percentage: number;
  }[];
  dailyVolume: {
    date: string;
    count: number;
    value: string;
  }[];
}

export const TransactionsService = {
  /**
   * Fetch transactions with filtering and pagination
   */
  async getTransactions(query: TransactionsQuery = {}): Promise<TransactionsResponse> {
    const params = new URLSearchParams();
    
    // Add query parameters
    if (query.walletAddresses?.length) {
      params.append('wallet_addresses', query.walletAddresses.join(','));
    }
    if (query.networks?.length) {
      params.append('networks', query.networks.join(','));
    }
    if (query.subnets?.length) {
      params.append('subnets', query.subnets.join(','));
    }
    if (query.transactionTypes?.length) {
      params.append('transaction_types', query.transactionTypes.join(','));
    }
    if (query.status?.length) {
      params.append('status', query.status.join(','));
    }
    if (query.fromDate) {
      params.append('from_date', query.fromDate);
    }
    if (query.toDate) {
      params.append('to_date', query.toDate);
    }
    if (query.search) {
      params.append('search', query.search);
    }
    if (query.limit) {
      params.append('limit', query.limit.toString());
    }
    if (query.offset) {
      params.append('offset', query.offset.toString());
    }
    if (query.sortBy) {
      params.append('sort_by', query.sortBy);
    }
    if (query.sortOrder) {
      params.append('sort_order', query.sortOrder);
    }

    const response = await ApiService.fetchData<null, TransactionsResponse>({
      url: `/api/transactions?${params.toString()}`,
      method: 'GET',
    });

    return response.data;
  },

  /**
   * Get a specific transaction by hash
   */
  async getTransaction(hash: string): Promise<Transaction> {
    const response = await ApiService.fetchData<null, Transaction>({
      url: `/api/transactions/${hash}`,
      method: 'GET',
    });

    return response.data;
  },

  /**
   * Get transaction statistics
   */
  async getTransactionStats(query: Omit<TransactionsQuery, 'limit' | 'offset' | 'sortBy' | 'sortOrder'> = {}): Promise<TransactionStatsResponse> {
    const params = new URLSearchParams();
    
    if (query.walletAddresses?.length) {
      params.append('wallet_addresses', query.walletAddresses.join(','));
    }
    if (query.networks?.length) {
      params.append('networks', query.networks.join(','));
    }
    if (query.subnets?.length) {
      params.append('subnets', query.subnets.join(','));
    }
    if (query.fromDate) {
      params.append('from_date', query.fromDate);
    }
    if (query.toDate) {
      params.append('to_date', query.toDate);
    }

    const response = await ApiService.fetchData<null, TransactionStatsResponse>({
      url: `/api/transactions/stats?${params.toString()}`,
      method: 'GET',
    });

    return response.data;
  },

  /**
   * Get recent transactions for a specific wallet
   */
  async getWalletTransactions(walletAddress: string, limit: number = 10): Promise<Transaction[]> {
    const response = await ApiService.fetchData<null, { transactions: Transaction[] }>({
      url: `/wallets/${walletAddress}/transactions?limit=${limit}`,
      method: 'GET',
    });

    return response.data.transactions;
  },

  /**
   * Export transactions to CSV
   */
  async exportTransactions(query: TransactionsQuery = {}): Promise<Blob> {
    const params = new URLSearchParams();
    
    // Add query parameters (same as getTransactions)
    if (query.walletAddresses?.length) {
      params.append('wallet_addresses', query.walletAddresses.join(','));
    }
    if (query.networks?.length) {
      params.append('networks', query.networks.join(','));
    }
    if (query.fromDate) {
      params.append('from_date', query.fromDate);
    }
    if (query.toDate) {
      params.append('to_date', query.toDate);
    }

    const response = await fetch(`${appConfig.apiPrefix}/api/transactions/export?${params.toString()}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to export transactions');
    }

    return response.blob();
  },
};
