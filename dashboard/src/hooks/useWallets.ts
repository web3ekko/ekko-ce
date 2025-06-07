import { useState, useEffect, useCallback } from 'react';
import { walletsApi, Wallet, PaginationParams } from '../services/api';

interface UseWalletsResult {
  wallets: Wallet[];
  loading: boolean;
  error: string | null;
  totalWallets: number;
  totalPages: number;
  currentPage: number;
  pageSize: number;
  fetchWallets: (params?: PaginationParams) => Promise<void>;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
}

export function useWallets(initialPage = 1, initialPageSize = 10): UseWalletsResult {
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalWallets, setTotalWallets] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);

  const fetchWallets = useCallback(
    async (params?: PaginationParams) => {
      setLoading(true);
      setError(null);

      try {
        const paginationParams = {
          page: params?.page || currentPage,
          limit: params?.limit || pageSize,
          sort: params?.sort,
          order: params?.order,
        };

        const response = await walletsApi.getWallets(paginationParams);

        setWallets(response.data);
        setTotalWallets(response.total);
        setTotalPages(response.totalPages);
        setCurrentPage(response.page);
      } catch (err) {
        console.error('Error fetching wallets:', err);
        setError('Failed to load wallets. Please try again later.');
      } finally {
        setLoading(false);
      }
    },
    [currentPage, pageSize]
  );

  // Change page
  const setPage = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  // Change page size
  const setPageSizeValue = useCallback((size: number) => {
    setPageSize(size);
    setCurrentPage(1); // Reset to first page when changing page size
  }, []);

  // Fetch wallets when page or pageSize changes
  useEffect(() => {
    fetchWallets();
  }, [fetchWallets, currentPage, pageSize]);

  return {
    wallets,
    loading,
    error,
    totalWallets,
    totalPages,
    currentPage,
    pageSize,
    fetchWallets,
    setPage,
    setPageSize: setPageSizeValue,
  };
}
