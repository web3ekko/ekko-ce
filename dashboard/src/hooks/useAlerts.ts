import { useState, useEffect, useCallback } from 'react';
import { alertsApi, Alert, PaginationParams } from '../services/api';

interface UseAlertsResult {
  alerts: Alert[];
  loading: boolean;
  error: string | null;
  totalAlerts: number;
  totalPages: number;
  currentPage: number;
  pageSize: number;
  fetchAlerts: (params?: PaginationParams) => Promise<void>;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
}

export function useAlerts(initialPage = 1, initialPageSize = 10): UseAlertsResult {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalAlerts, setTotalAlerts] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);

  const fetchAlerts = useCallback(
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

        const response = await alertsApi.getAlerts(paginationParams);

        setAlerts(response.data);
        setTotalAlerts(response.total);
        setTotalPages(response.totalPages);
        setCurrentPage(response.page);
      } catch (err) {
        console.error('Error fetching alerts:', err);
        setError('Failed to load alerts. Please try again later.');
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

  // Fetch alerts when page or pageSize changes
  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts, currentPage, pageSize]);

  return {
    alerts,
    loading,
    error,
    totalAlerts,
    totalPages,
    currentPage,
    pageSize,
    fetchAlerts,
    setPage,
    setPageSize: setPageSizeValue,
  };
}
