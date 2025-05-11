export interface Wallet {
  id: string;
  blockchain_symbol: string;
  address: string;
  name: string;
  balance: number;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface WalletFormValues {
  name: string;
  address: string;
  blockchain: string;
  description?: string;
  isActive: boolean;
}
