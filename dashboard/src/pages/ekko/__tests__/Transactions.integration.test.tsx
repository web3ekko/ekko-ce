/**
 * Integration tests for the Transactions page.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { configureStore } from '@reduxjs/toolkit';
import { MantineProvider } from '@mantine/core';
import Transactions from '../Transactions';
import { TransactionsService } from '@/services/api/transactions.service';

// Mock the transactions service
vi.mock('@/services/api/transactions.service', () => ({
  TransactionsService: {
    getTransactions: vi.fn(),
    exportTransactions: vi.fn(),
  },
}));

// Mock the realtime service
vi.mock('@/services/realtime/RealtimeTransactionService', () => ({
  default: {
    connect: vi.fn(),
    disconnect: vi.fn(),
  },
}));

const mockTransactionsService = TransactionsService as any;

// Mock store setup
const createMockStore = (initialState = {}) => {
  return configureStore({
    reducer: {
      auth: (state = { user: { email: 'test@example.com' } }) => state,
      wallets: (state = { 
        monitored: [
          {
            id: '1',
            address: '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416',
            name: 'Main Wallet',
            network: 'avalanche'
          }
        ]
      }) => state,
      realtimeTransactions: (state = {
        transactions: [],
        isConnecting: false,
        isConnected: false,
        connectionError: null,
      }) => state,
      ...initialState,
    },
  });
};

// Mock transaction data
const mockTransactions = [
  {
    hash: '0x1a2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890',
    from: '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416',
    to: '0x8ba1f109551bD432803012645Hac136c22C177e9',
    value: '2500000000000000000',
    gas: '21000',
    gasPrice: '20000000000',
    nonce: '42',
    input: '0x',
    blockNumber: 18500000,
    blockHash: '0xabc123def456...',
    transactionIndex: 0,
    timestamp: '2025-01-07T10:30:00Z',
    network: 'avalanche',
    subnet: 'mainnet',
    status: 'confirmed',
    tokenSymbol: 'AVAX',
    transactionType: 'send',
    decodedCall: {
      function: 'Transfer',
      params: { to: '0x8ba1f109551bD432803012645Hac136c22C177e9', value: '2.5' }
    }
  },
  {
    hash: '0x2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890ab',
    from: '0x8ba1f109551bD432803012645Hac136c22C177e9',
    to: '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416',
    value: '1000000000',
    gas: '65000',
    gasPrice: '25000000000',
    nonce: '43',
    input: '0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b8d4c0c8b3c2e1e416',
    blockNumber: 18499950,
    blockHash: '0xdef456ghi789...',
    transactionIndex: 1,
    timestamp: '2025-01-07T09:15:00Z',
    network: 'avalanche',
    subnet: 'mainnet',
    status: 'confirmed',
    tokenSymbol: 'USDC.e',
    transactionType: 'contract_interaction',
    decodedCall: {
      function: 'Transfer',
      params: { to: '0x742d35Cc6634C0532925a3b8D4C0C8b3C2e1e416', value: '1000' }
    }
  }
];

const mockTransactionsResponse = {
  transactions: mockTransactions,
  total: 2,
  limit: 20,
  offset: 0,
  hasMore: false
};

const renderWithProviders = (component: React.ReactElement, store = createMockStore()) => {
  return render(
    <Provider store={store}>
      <BrowserRouter>
        <MantineProvider>
          {component}
        </MantineProvider>
      </BrowserRouter>
    </Provider>
  );
};

describe('Transactions Page Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTransactionsService.getTransactions.mockResolvedValue(mockTransactionsResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should render the transactions page with data', async () => {
    renderWithProviders(<Transactions />);

    // Check page title
    expect(screen.getByText('Transactions')).toBeInTheDocument();
    expect(screen.getByText('View and analyze blockchain transactions')).toBeInTheDocument();

    // Wait for transactions to load
    await waitFor(() => {
      expect(screen.getByText('0x1a2b3c...567890')).toBeInTheDocument();
      expect(screen.getByText('0x2b3c4d...567890')).toBeInTheDocument();
    });

    // Check transaction details
    expect(screen.getByText('Send')).toBeInTheDocument();
    expect(screen.getByText('2500000000000000000 AVAX')).toBeInTheDocument();
    expect(screen.getByText('1000000000 USDC.e')).toBeInTheDocument();
  });

  it('should handle search functionality', async () => {
    renderWithProviders(<Transactions />);

    await waitFor(() => {
      expect(screen.getByText('0x1a2b3c...567890')).toBeInTheDocument();
    });

    // Find and use search input
    const searchInput = screen.getByPlaceholderText('Search transactions...');
    fireEvent.change(searchInput, { target: { value: '0x1a2b3c' } });

    // Wait for debounced search
    await waitFor(() => {
      expect(mockTransactionsService.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({
          search: '0x1a2b3c'
        })
      );
    }, { timeout: 3000 });
  });

  it('should handle tab filtering', async () => {
    renderWithProviders(<Transactions />);

    await waitFor(() => {
      expect(screen.getByText('Send')).toBeInTheDocument();
    });

    // Click on 'Send' tab
    const sendTab = screen.getByRole('tab', { name: /send/i });
    fireEvent.click(sendTab);

    await waitFor(() => {
      expect(mockTransactionsService.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({
          transactionTypes: ['send']
        })
      );
    });
  });

  it('should handle export functionality', async () => {
    const mockBlob = new Blob(['csv,data'], { type: 'text/csv' });
    mockTransactionsService.exportTransactions.mockResolvedValue(mockBlob);

    // Mock DOM methods for download
    const mockCreateElement = vi.fn();
    const mockAppendChild = vi.fn();
    const mockRemoveChild = vi.fn();
    const mockClick = vi.fn();
    const mockCreateObjectURL = vi.fn().mockReturnValue('blob:url');
    const mockRevokeObjectURL = vi.fn();

    const mockLink = {
      href: '',
      download: '',
      click: mockClick
    };

    mockCreateElement.mockReturnValue(mockLink);

    Object.defineProperty(document, 'createElement', {
      value: mockCreateElement,
      configurable: true
    });
    Object.defineProperty(document.body, 'appendChild', {
      value: mockAppendChild,
      configurable: true
    });
    Object.defineProperty(document.body, 'removeChild', {
      value: mockRemoveChild,
      configurable: true
    });
    Object.defineProperty(window.URL, 'createObjectURL', {
      value: mockCreateObjectURL,
      configurable: true
    });
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      value: mockRevokeObjectURL,
      configurable: true
    });

    renderWithProviders(<Transactions />);

    await waitFor(() => {
      expect(screen.getByText('Send')).toBeInTheDocument();
    });

    // Click export button
    const exportButton = screen.getByText('Export');
    fireEvent.click(exportButton);

    await waitFor(() => {
      expect(mockTransactionsService.exportTransactions).toHaveBeenCalled();
      expect(mockClick).toHaveBeenCalled();
    });
  });

  it('should handle loading states', async () => {
    // Mock a delayed response
    let resolvePromise: (value: any) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    
    mockTransactionsService.getTransactions.mockReturnValue(promise);

    renderWithProviders(<Transactions />);

    // Should show loading state
    await waitFor(() => {
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    // Resolve the promise
    resolvePromise!(mockTransactionsResponse);

    // Should show transactions
    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      expect(screen.getByText('Send')).toBeInTheDocument();
    });
  });

  it('should handle error states', async () => {
    mockTransactionsService.getTransactions.mockRejectedValue(new Error('API Error'));

    renderWithProviders(<Transactions />);

    await waitFor(() => {
      expect(screen.getByText('Error loading transactions')).toBeInTheDocument();
      expect(screen.getByText('API Error')).toBeInTheDocument();
      expect(screen.getByText('Retry')).toBeInTheDocument();
    });

    // Test retry functionality
    mockTransactionsService.getTransactions.mockResolvedValue(mockTransactionsResponse);
    
    const retryButton = screen.getByText('Retry');
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText('Send')).toBeInTheDocument();
    });
  });

  it('should handle empty state', async () => {
    mockTransactionsService.getTransactions.mockResolvedValue({
      transactions: [],
      total: 0,
      limit: 20,
      offset: 0,
      hasMore: false
    });

    renderWithProviders(<Transactions />);

    await waitFor(() => {
      expect(screen.getByText('No transactions found')).toBeInTheDocument();
      expect(screen.getByText('Try adjusting your search criteria')).toBeInTheDocument();
    });
  });

  it('should handle load more functionality', async () => {
    const initialResponse = {
      transactions: [mockTransactions[0]],
      total: 2,
      limit: 1,
      offset: 0,
      hasMore: true
    };

    const moreResponse = {
      transactions: [mockTransactions[1]],
      total: 2,
      limit: 1,
      offset: 1,
      hasMore: false
    };

    mockTransactionsService.getTransactions
      .mockResolvedValueOnce(initialResponse)
      .mockResolvedValueOnce(moreResponse);

    renderWithProviders(<Transactions />);

    await waitFor(() => {
      expect(screen.getByText('Send')).toBeInTheDocument();
      expect(screen.getByText('Load More Transactions')).toBeInTheDocument();
    });

    // Click load more
    const loadMoreButton = screen.getByText('Load More Transactions');
    fireEvent.click(loadMoreButton);

    await waitFor(() => {
      expect(screen.getByText('Send')).toBeInTheDocument();
      expect(screen.getByText('contract_interaction')).toBeInTheDocument();
      expect(screen.queryByText('Load More Transactions')).not.toBeInTheDocument();
    });
  });

  it('should show connection status indicators', async () => {
    const storeWithConnection = createMockStore({
      realtimeTransactions: {
        transactions: [],
        isConnecting: false,
        isConnected: true,
        connectionError: null,
      }
    });

    renderWithProviders(<Transactions />, storeWithConnection);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  it('should show connection error', async () => {
    const storeWithError = createMockStore({
      realtimeTransactions: {
        transactions: [],
        isConnecting: false,
        isConnected: false,
        connectionError: 'Connection failed',
      }
    });

    renderWithProviders(<Transactions />, storeWithError);

    await waitFor(() => {
      expect(screen.getByText('Connection failed')).toBeInTheDocument();
    });
  });

  it('should handle page size changes', async () => {
    renderWithProviders(<Transactions />);

    await waitFor(() => {
      expect(screen.getByText('Send')).toBeInTheDocument();
    });

    // Find and change page size
    const pageSizeSelect = screen.getByDisplayValue('20');
    fireEvent.change(pageSizeSelect, { target: { value: '50' } });

    await waitFor(() => {
      expect(mockTransactionsService.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 50,
          offset: 0
        })
      );
    });
  });
});
