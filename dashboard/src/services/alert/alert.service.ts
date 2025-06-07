import ApiService from '@/services/ApiService';
import type { Alert, AlertCreate } from '@/@types/alert';
import { v4 as uuidv4 } from 'uuid';

// Helper function to handle API errors
const handleApiError = (error: any, operation: string) => {
  console.error(`Error ${operation}:`, error);
  if (error.response) {
    // The request was made and the server responded with a status code
    // that falls out of the range of 2xx
    console.error('Response data:', error.response.data);
    console.error('Response status:', error.response.status);
    throw new Error(error.response.data?.detail || `Failed to ${operation}`);
  } else if (error.request) {
    // The request was made but no response was received
    console.error('No response received:', error.request);
    throw new Error(`No response from server while trying to ${operation}`);
  } else {
    // Something happened in setting up the request that triggered an Error
    throw new Error(`Error occurred while trying to ${operation}: ${error.message}`);
  }
};

export const AlertService = {
  async getAlerts(): Promise<Alert[]> {
    try {
      const res = await ApiService.fetchData<null, Alert[]>({
        url: '/alerts',
        method: 'GET',
      });
      return res.data;
    } catch (error) {
      return handleApiError(error, 'fetch alerts');
    }
  },

  async getAlert(id: string): Promise<Alert> {
    try {
      const res = await ApiService.fetchData<null, Alert>({
        url: `/alerts/${id}`,
        method: 'GET',
      });
      return res.data;
    } catch (error) {
      return handleApiError(error, 'fetch alert');
    }
  },

  async getAlertJobspec(id: string): Promise<any> {
    try {
      const res = await ApiService.fetchData<null, any>({
        url: `/alerts/${id}/jobspec`,
        method: 'GET',
      });
      return res.data;
    } catch (error) {
      return handleApiError(error, 'retrieve alert jobspec');
    }
  },

  async generateJobSpec(id: string): Promise<any> {
    try {
      const res = await ApiService.fetchData<null, any>({
        url: `/alerts/${id}/generate-jobspec`,
        method: 'POST',
      });
      return res.data;
    } catch (error) {
      return handleApiError(error, 'generate job specification');
    }
  },

  async createAlert(alertData: AlertCreate): Promise<Alert> {
    try {
      console.log('Creating alert with data:', alertData);

      // Generate ID on client side if not provided
      const alertWithId: Alert = {
        ...alertData,
        id: alertData.id || uuidv4(),
        time: alertData.time || new Date().toISOString(),
      };

      const res = await ApiService.fetchData<Alert, Alert>({
        url: '/alerts',
        method: 'POST',
        data: alertWithId,
      });
      console.log('Alert created successfully:', res.data);
      return res.data;
    } catch (error) {
      return handleApiError(error, 'create alert');
    }
  },

  async updateAlert(id: string, alertData: Partial<Alert>): Promise<Alert> {
    try {
      const res = await ApiService.fetchData<Partial<Alert>, Alert>({
        url: `/alerts/${id}`,
        method: 'PUT',
        data: { ...alertData, id },
      });
      return res.data;
    } catch (error) {
      return handleApiError(error, 'update alert');
    }
  },

  async deleteAlert(id: string): Promise<void> {
    try {
      await ApiService.fetchData<null, void>({
        url: `/alerts/${id}`,
        method: 'DELETE',
      });
    } catch (error) {
      handleApiError(error, 'delete alert');
    }
  },
};
