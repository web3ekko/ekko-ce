import axios from 'axios';

// Create an axios instance with the API URL
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000, // 10 second timeout for requests
});

// Add request interceptor for authentication
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle specific error cases
    if (error.response) {
      // Server responded with an error status
      console.error('API Error Response:', error.response.status, error.response.data);
      
      // Handle authentication errors
      if (error.response.status === 401) {
        localStorage.removeItem('auth_token');
        // Redirect to login page or dispatch auth error action
      }
    } else if (error.request) {
      // Request was made but no response received
      console.error('API No Response:', error.request);
    } else {
      // Error in setting up the request
      console.error('API Request Error:', error.message);
    }
    
    return Promise.reject(error);
  }
);

// Types for our API responses
export interface Wallet {
  id: string;
  name: string;
  address: string;
  balance: number;
  blockchain: string;
  blockchain_symbol: string;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface Alert {
  id: string;
  type: string;
  message: string;
  time: string;
  status: string;
  priority: string;
  relatedWallet?: string;
}

export interface Transaction {
  id: string;
  hash: string;
  from: string;
  to: string;
  amount: number;
  token: string;
  timestamp: string;
  status: string;
  type: string;
}

export interface Node {
  id: string;
  name: string;
  type: string;
  network: string;
  endpoint: string;
  status: string;
  uptime: number;
  cpu: number;
  memory: number;
  disk: number;
  peers: number;
  version: string;
  websocket_url?: string;
  http_url?: string;
  vm?: string;
}

// Pagination parameters
export interface PaginationParams {
  page?: number;
  limit?: number;
  sort?: string;
  order?: 'asc' | 'desc';
}

// Pagination response
export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

// Wallet API functions
export const walletsApi = {
  getWallets: async (params?: PaginationParams): Promise<PaginatedResponse<Wallet>> => {
    try {
      const response = await api.get('/wallets', { params });
      return response.data;
    } catch (error) {
      console.error('Error fetching wallets:', error);
      // Return mock data for development
      const mockWallets = [
        { id: '1', name: 'Main Wallet', address: '0x1234...5678', balance: 2.345, blockchain: 'Avalanche', blockchain_symbol: 'AVAX', status: 'active' },
        { id: '2', name: 'Trading Wallet', address: '0x8765...4321', balance: 0.897, blockchain: 'Ethereum', blockchain_symbol: 'ETH', status: 'active' },
        { id: '3', name: 'Cold Storage', address: 'bc1q...wxyz', balance: 0.123, blockchain: 'Bitcoin', blockchain_symbol: 'BTC', status: 'inactive' },
        { id: '4', name: 'DeFi Wallet', address: '0xabcd...efgh', balance: 45.67, blockchain: 'Polygon', blockchain_symbol: 'MATIC', status: 'active' },
      ];
      
      return {
        data: mockWallets,
        total: mockWallets.length,
        page: params?.page || 1,
        limit: params?.limit || 10,
        totalPages: 1
      };
    }
  },
  
  getWallet: async (id: string): Promise<Wallet> => {
    try {
      const response = await api.get(`/wallets/${id}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching wallet ${id}:`, error);
      throw error;
    }
  },
  
  createWallet: async (wallet: Omit<Wallet, 'id'>): Promise<Wallet> => {
    try {
      const response = await api.post('/wallets', wallet);
      return response.data;
    } catch (error) {
      console.error('Error creating wallet:', error);
      throw error;
    }
  },
  
  updateWallet: async (wallet: Wallet): Promise<Wallet> => {
    try {
      const response = await api.put(`/wallets/${wallet.id}`, wallet);
      return response.data;
    } catch (error) {
      console.error(`Error updating wallet ${wallet.id}:`, error);
      throw error;
    }
  },
  
  deleteWallet: async (id: string): Promise<void> => {
    try {
      await api.delete(`/wallets/${id}`);
    } catch (error) {
      console.error(`Error deleting wallet ${id}:`, error);
      throw error;
    }
  }
};

// Alert API functions
export const alertsApi = {
  getAlerts: async (params?: PaginationParams): Promise<PaginatedResponse<Alert>> => {
    try {
      const response = await api.get('/alerts', { params });
      return response.data;
    } catch (error) {
      console.error('Error fetching alerts:', error);
      // Return mock data for development - will be replaced with actual API data
      const mockAlerts = [
        // Using empty related_wallet_id field to ensure it's clearly a mock alert
        // In a real API response, this would be a proper UUID referencing a wallet
        { id: '1', type: 'Balance', message: 'Main wallet balance below 3 AVAX', time: '2025-05-08T08:30:00Z', status: 'Open', priority: 'High', related_wallet_id: '' },
        { id: '2', type: 'Price', message: 'ETH price increased by 5% in last hour', time: '2025-05-08T07:15:00Z', status: 'Open', priority: 'Medium', related_wallet_id: '' },
        { id: '3', type: 'Transaction', message: 'Large transaction detected on wallet AVAX-1', time: '2025-05-08T06:45:00Z', status: 'Open', priority: 'Low', related_wallet_id: '' },
        { id: '4', type: 'Security', message: 'Suspicious activity detected on wallet BTC-1', time: '2025-05-07T22:30:00Z', status: 'Resolved', priority: 'High', related_wallet_id: '' },
      ];
      
      return {
        data: mockAlerts,
        total: mockAlerts.length,
        page: params?.page || 1,
        limit: params?.limit || 10,
        totalPages: 1
      };
    }
  },
  
  getAlert: async (id: string): Promise<Alert> => {
    try {
      const response = await api.get(`/alerts/${id}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching alert ${id}:`, error);
      throw error;
    }
  },
  
  createAlert: async (alert: Omit<Alert, 'id'>): Promise<Alert> => {
    try {
      const response = await api.post('/alerts', alert);
      return response.data;
    } catch (error) {
      console.error('Error creating alert:', error);
      throw error;
    }
  },
  
  updateAlert: async (alert: Alert): Promise<Alert> => {
    try {
      const response = await api.put(`/alerts/${alert.id}`, alert);
      return response.data;
    } catch (error) {
      console.error(`Error updating alert ${alert.id}:`, error);
      throw error;
    }
  },
  
  deleteAlert: async (id: string): Promise<void> => {
    try {
      await api.delete(`/alerts/${id}`);
    } catch (error) {
      console.error(`Error deleting alert ${id}:`, error);
      throw error;
    }
  }
};

// Transaction API functions
export const transactionsApi = {
  getTransactions: async (params?: PaginationParams): Promise<PaginatedResponse<Transaction>> => {
    try {
      const response = await api.get('/transactions', { params });
      return response.data;
    } catch (error) {
      console.error('Error fetching transactions:', error);
      // Return mock data for development
      const mockTransactions = [
        { id: '1', hash: '0x1a2b3c4d5e6f...', from: '0x1234...5678', to: '0x8765...4321', amount: 1.25, token: 'AVAX', timestamp: '2025-05-08T09:30:00Z', status: 'Confirmed', type: 'Send' },
        { id: '2', hash: '0xabcdef1234...', from: '0x9876...5432', to: '0x1234...5678', amount: 0.5, token: 'ETH', timestamp: '2025-05-08T08:15:00Z', status: 'Confirmed', type: 'Receive' },
        { id: '3', hash: '0x7890abcdef...', from: '0x1234...5678', to: '0xContract...', amount: 100, token: 'USDC', timestamp: '2025-05-08T07:45:00Z', status: 'Confirmed', type: 'Contract' },
        { id: '4', hash: '0x2468acef...', from: '0x1234...5678', to: '0xdead...beef', amount: 0.75, token: 'AVAX', timestamp: '2025-05-08T06:30:00Z', status: 'Pending', type: 'Send' },
        { id: '5', hash: '0x13579bdf...', from: '0xdead...beef', to: '0x1234...5678', amount: 2.5, token: 'MATIC', timestamp: '2025-05-07T23:15:00Z', status: 'Confirmed', type: 'Receive' },
      ];
      
      return {
        data: mockTransactions,
        total: mockTransactions.length,
        page: params?.page || 1,
        limit: params?.limit || 10,
        totalPages: 1
      };
    }
  },
  
  getTransaction: async (id: string): Promise<Transaction> => {
    try {
      const response = await api.get(`/transactions/${id}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching transaction ${id}:`, error);
      throw error;
    }
  }
};

// Node API functions
export const nodesApi = {
  getNodes: async (params?: PaginationParams): Promise<PaginatedResponse<Node>> => {
    try {
      const response = await api.get('/nodes', { params });
      return response.data;
    } catch (error) {
      console.error('Error fetching nodes:', error);
      // Return mock data for development
      const mockNodes = [
        { id: '1', name: 'AVAX-Mainnet-1', type: 'Validator', network: 'Avalanche', endpoint: 'https://node1.example.com:9650', status: 'Online', uptime: 99.98, cpu: 32, memory: 45, disk: 68, peers: 124, version: '1.9.12' },
        { id: '5', name: 'AVAX-Fuji-1', type: 'API', network: 'Avalanche Fuji', endpoint: 'https://fuji1.example.com:9650', status: 'Offline', uptime: 0, cpu: 0, memory: 0, disk: 65, peers: 0, version: '1.9.11' },
      ];
      
      return {
        data: mockNodes,
        total: mockNodes.length,
        page: params?.page || 1,
        limit: params?.limit || 10,
        totalPages: 1
      };
    }
  },
  
  getNode: async (id: string): Promise<Node> => {
    try {
      const response = await api.get(`/nodes/${id}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching node ${id}:`, error);
      throw error;
    }
  },
  
  createNode: async (node: Omit<Node, 'id'>): Promise<Node> => {
    try {
      const response = await api.post('/nodes', node);
      return response.data;
    } catch (error) {
      console.error('Error creating node:', error);
      throw error;
    }
  },
  
  updateNode: async (node: Node): Promise<Node> => {
    try {
      const response = await api.put(`/nodes/${node.id}`, node);
      return response.data;
    } catch (error) {
      console.error(`Error updating node ${node.id}:`, error);
      throw error;
    }
  }
};

// Health check API function
export const apiUtils = {
  healthCheck: async (): Promise<{ status: string; api_connected: boolean; version: string }> => {
    try {
      const response = await api.get('/health');
      return response.data;
    } catch (error) {
      console.error('Error checking API health:', error);
      return { status: 'error', api_connected: false, version: 'unknown' };
    }
  },
  
  // Cache control for performance optimization
  clearCache: async (): Promise<void> => {
    try {
      await api.post('/cache/clear');
    } catch (error) {
      console.error('Error clearing API cache:', error);
      throw error;
    }
  }
};

export default api;
