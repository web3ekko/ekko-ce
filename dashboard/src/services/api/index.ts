import api, { 
  walletsApi, 
  alertsApi, 
  transactionsApi, 
  nodesApi, 
  apiUtils,
  // Types
  Wallet,
  Alert,
  Transaction,
  Node,
  PaginationParams,
  PaginatedResponse
} from './ekko';
import authApi from './auth';

export {
  api as default,
  walletsApi,
  alertsApi,
  transactionsApi,
  nodesApi,
  apiUtils,
  authApi,
};

// Re-export types with 'export type' syntax for isolatedModules compatibility
export type {
  Wallet,
  Alert,
  Transaction,
  Node,
  PaginationParams,
  PaginatedResponse
};
