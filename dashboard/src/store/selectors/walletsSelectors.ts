import { createSelector } from '@reduxjs/toolkit';
import { RootState } from '../rootReducer';
import type { Wallet, MonitoredWalletInfo } from '@/@types/wallet'; // Ensure Wallet & MonitoredWalletInfo types are imported

// Selector for the wallets slice state
const selectWalletsState = (state: RootState) => state.wallets;

// Selector to get the array of wallet objects
export const selectAllWallets = createSelector(
  [selectWalletsState],
  (walletsState): Wallet[] => walletsState.wallets
);

// Selector to get just the addresses of all wallets
export const selectWalletAddresses = createSelector([selectAllWallets], (wallets): string[] =>
  (wallets || []).map((wallet) => wallet.address)
);

// Selector to get active wallet addresses (if 'status' field is used like 'active')
// Make sure your Wallet type has a 'status' field if you use this.
// For now, assuming 'isActive' boolean field from WalletFormValues might translate to a status.
// Or, if all wallets in the store are considered active for monitoring:
export const selectActiveWalletAddresses = createSelector(
  [selectAllWallets],
  (wallets): string[] =>
    (wallets || [])
      // .filter(wallet => wallet.status === 'active') // Example if 'status' field exists
      // .filter(wallet => wallet.isActive) // Example if 'isActive' field exists on Wallet type
      .map((wallet) => wallet.address) // Currently, sends all wallet addresses
);

export const selectWalletsLoading = createSelector(
  [selectWalletsState],
  (walletsState): boolean => walletsState.loading
);

// Selector to get an array of MonitoredWalletInfo objects for the RealtimeTransactionService
export const selectMonitoredWallets = createSelector(
  [selectAllWallets],
  (wallets): MonitoredWalletInfo[] =>
    (wallets || []).map((wallet) => ({
      address: wallet.address,
      network: wallet.blockchain_symbol, // Use blockchain_symbol as network
      subnet: wallet.subnet, // Use the subnet from the Wallet object
    }))
);

export const selectWalletsError = createSelector(
  [selectWalletsState],
  (walletsState): string | null => walletsState.error
);
