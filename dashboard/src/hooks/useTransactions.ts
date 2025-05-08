import { useState, useEffect, useCallback } from 'react';
import { transactionsApi, Transaction, PaginationParams } from '../services/api';

interface UseTransactionsResult {
  transactions: Transaction[];
  loading: boolean;
  error: string | null;
  totalTransactions: number;
  totalPages: number;
  currentPage: number;
  pageSize: number;
  fetchTransactions: (params?: PaginationParams) => Promise<void>;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
}

export function useTransactions(initialPage = 1, initialPageSize = 10): UseTransactionsResult {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalTransactions, setTotalTransactions] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);

  const fetchTransactions = useCallback(async (params?: PaginationParams) => {
    setLoading(true);
    setError(null);
    
    try {
      const paginationParams = {
        page: params?.page || currentPage,
        limit: params?.limit || pageSize,
        sort: params?.sort,
        order: params?.order
      };
      
      const response = await transactionsApi.getTransactions(paginationParams);
      
      setTransactions(response.data);
      setTotalTransactions(response.total);
      setTotalPages(response.totalPages);
      setCurrentPage(response.page);
      
    } catch (err) {
      console.error('Error fetching transactions:', err);
      setError('Failed to load transactions. Please try again later.');
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize]);

  // Change page
  const setPage = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  // Change page size
  const setPageSizeValue = useCallback((size: number) => {
    setPageSize(size);
    setCurrentPage(1); // Reset to first page when changing page size
  }, []);

  // Fetch transactions when page or pageSize changes
  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions, currentPage, pageSize]);

  return { 
    transactions, 
    loading, 
    error, 
    totalTransactions, 
    totalPages, 
    currentPage, 
    pageSize, 
    fetchTransactions, 
    setPage, 
    setPageSize: setPageSizeValue 
  };
}
