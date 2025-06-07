import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface DecodedCallData {
  function: string;
  params: { [key: string]: any };
}

export interface RealtimeTransaction {
  hash: string;
  from: string;
  to: string | null;
  value: string;
  input: string;
  decoded_call?: DecodedCallData;
  // Additional fields that might come from NATS or be derived
  timestamp?: number | string;
  blockNumber?: number;
  status?: string; // e.g., 'confirmed', 'pending'
  // For simplicity, let's assume the backend bridge might add a 'network' or 'tokenSymbol' if relevant
  network?: string; // e.g., 'ETH', 'AVAX'
  tokenSymbol?: string; // e.g., 'USDC' if it's a known token transfer
  // A derived type for easier UI handling
  transactionType?: 'send' | 'receive' | 'contract_interaction' | 'contract_creation' | 'unknown';
}

export interface RealtimeTransactionsState {
  transactions: RealtimeTransaction[];
  isConnecting: boolean;
  isConnected: boolean;
  error: string | null;
}

const initialState: RealtimeTransactionsState = {
  transactions: [],
  isConnecting: false,
  isConnected: false,
  error: null,
};

const realtimeTransactionsSlice = createSlice({
  name: 'realtimeTransactions',
  initialState,
  reducers: {
    connectionInitiated: (state) => {
      state.isConnecting = true;
      state.isConnected = false;
      state.error = null;
    },
    connectionEstablished: (state) => {
      state.isConnecting = false;
      state.isConnected = true;
      state.error = null;
    },
    connectionClosed: (state, action: PayloadAction<string | undefined>) => {
      state.isConnecting = false;
      state.isConnected = false;
      state.error = action.payload || 'Connection closed';
      // Optionally clear transactions on disconnect, or keep them
      // state.transactions = [];
    },
    connectionError: (state, action: PayloadAction<string>) => {
      state.isConnecting = false;
      state.isConnected = false;
      state.error = action.payload;
    },
    newTransactionReceived: (state, action: PayloadAction<RealtimeTransaction>) => {
      // Add to the beginning of the array to show newest first
      // Potentially add logic to prevent duplicates if the stream might send them
      if (!state.transactions.find((tx) => tx.hash === action.payload.hash)) {
        state.transactions.unshift(action.payload);
      }
      // Optional: Limit the number of transactions stored
      // const MAX_TRANSACTIONS = 100;
      // if (state.transactions.length > MAX_TRANSACTIONS) {
      //   state.transactions.pop();
      // }
    },
    clearRealtimeTransactions: (state) => {
      state.transactions = [];
    },
  },
});

export const {
  connectionInitiated,
  connectionEstablished,
  connectionClosed,
  connectionError,
  newTransactionReceived,
  clearRealtimeTransactions,
} = realtimeTransactionsSlice.actions;

export default realtimeTransactionsSlice.reducer;
