import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { WalletService } from '@/services/wallet/wallet.service';
import type { Wallet } from '@/@types/wallet';

export interface WalletsState {
  wallets: Wallet[];
  loading: boolean;
  error: string | null;
}

const initialState: WalletsState = {
  wallets: [],
  loading: false,
  error: null,
};

// Async thunk to fetch wallets
export const fetchWallets = createAsyncThunk(
  'wallets/fetchWallets',
  async (_, { rejectWithValue }) => {
    try {
      const data = await WalletService.getWallets();
      return data;
    } catch (err: any) {
      return rejectWithValue(err.message || 'Failed to fetch wallets');
    }
  }
);

// Async thunk to create a wallet
export const createWallet = createAsyncThunk(
  'wallets/createWallet',
  async (walletData: Omit<Wallet, 'id' | 'created_at' | 'updated_at'>, { dispatch, rejectWithValue }) => {
    try {
      const newWallet = await WalletService.createWallet(walletData);
      dispatch(fetchWallets()); // Refresh the list after creating
      return newWallet;
    } catch (err: any) {
      return rejectWithValue(err.message || 'Failed to create wallet');
    }
  }
);

// Async thunk to delete a wallet
export const deleteWallet = createAsyncThunk(
  'wallets/deleteWallet',
  async (walletId: string, { dispatch, rejectWithValue }) => {
    try {
      await WalletService.deleteWallet(walletId);
      dispatch(fetchWallets()); // Refresh the list after deleting
      return walletId;
    } catch (err: any) {
      return rejectWithValue(err.message || 'Failed to delete wallet');
    }
  }
);

// Async thunk to update a wallet
export const updateWallet = createAsyncThunk(
  'wallets/updateWallet',
  async ({ id, data }: { id: string; data: Partial<Wallet> }, { dispatch, rejectWithValue }) => {
    try {
      const updatedWallet = await WalletService.updateWallet(id, data);
      dispatch(fetchWallets()); // Refresh the list after updating
      return updatedWallet;
    } catch (err: any) {
      return rejectWithValue(err.message || 'Failed to update wallet');
    }
  }
);

const walletsSlice = createSlice({
  name: 'wallets',
  initialState,
  reducers: {
    setWallets: (state, action: PayloadAction<Wallet[]>) => {
      state.wallets = action.payload;
    },
    clearWalletsError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch Wallets
      .addCase(fetchWallets.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchWallets.fulfilled, (state, action: PayloadAction<Wallet[]>) => {
        state.wallets = action.payload;
        state.loading = false;
      })
      .addCase(fetchWallets.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Create Wallet
      .addCase(createWallet.pending, (state) => {
        state.loading = true; 
      })
      .addCase(createWallet.fulfilled, (state) => {
        state.loading = false; // fetchWallets will update the list and loading state
      })
      .addCase(createWallet.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Delete Wallet
      .addCase(deleteWallet.pending, (state) => {
        state.loading = true;
      })
      .addCase(deleteWallet.fulfilled, (state) => {
        state.loading = false; // fetchWallets will update the list and loading state
      })
      .addCase(deleteWallet.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Update Wallet
      .addCase(updateWallet.pending, (state) => {
        state.loading = true;
      })
      .addCase(updateWallet.fulfilled, (state) => {
        state.loading = false; // fetchWallets will update the list and loading state
      })
      .addCase(updateWallet.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
  },
});

export const { setWallets, clearWalletsError } = walletsSlice.actions;
export default walletsSlice.reducer;
