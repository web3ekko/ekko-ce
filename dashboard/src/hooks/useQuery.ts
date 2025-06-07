import { useLocation } from 'react-router-dom';
import { useMemo } from 'react';

/**
 * Custom hook to parse URL search parameters
 * @returns URLSearchParams object for easy query parameter access
 */
export default function useQuery() {
  const { search } = useLocation();

  return useMemo(() => new URLSearchParams(search), [search]);
}
