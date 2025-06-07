export interface Wallet {
  id: string;
  blockchain_symbol: string;
  address: string;
  name: string;
  balance: number;
  status: string;
  subnet: string; // e.g., 'mainnet', 'sepolia', 'testnet'
  description?: string;
  isActive?: boolean;
  created_at?: string;
  updated_at?: string;
}

// Information needed for monitoring a wallet's transactions via NATS
export interface MonitoredWalletInfo {
  address: string;
  network: string; // e.g., 'eth', 'polygon' (derived from Wallet.blockchain_symbol)
  subnet: string; // e.g., 'mainnet', 'sepolia' (currently hardcoded, to be added to Wallet type)
}

export interface WalletFormValues {
  name: string;
  address: string;
  blockchain: string; // This corresponds to 'network' e.g. 'eth', 'polygon'
  subnet: string; // e.g., 'mainnet', 'sepolia', 'testnet'
  description?: string;
  isActive: boolean;
}
