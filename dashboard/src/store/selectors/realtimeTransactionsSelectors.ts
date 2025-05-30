import { createSelector } from '@reduxjs/toolkit';
import { RootState } from '../rootReducer';
import { RealtimeTransaction } from '../slices/realtimeTransactionsSlice';

const selectRealtimeTransactionsState = (state: RootState) => state.realtimeTransactions;

export const selectAllRealtimeTransactions = createSelector(
  [selectRealtimeTransactionsState],
  (realtimeTransactionsState): RealtimeTransaction[] => realtimeTransactionsState.transactions
);

export const selectIsConnectingToRealtime = createSelector(
  [selectRealtimeTransactionsState],
  (realtimeTransactionsState): boolean => realtimeTransactionsState.isConnecting
);

export const selectIsConnectedToRealtime = createSelector(
  [selectRealtimeTransactionsState],
  (realtimeTransactionsState): boolean => realtimeTransactionsState.isConnected
);

export const selectRealtimeConnectionError = createSelector(
  [selectRealtimeTransactionsState],
  (realtimeTransactionsState): string | null => realtimeTransactionsState.error
);
