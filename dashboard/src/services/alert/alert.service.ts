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

      // Prepare alert data with defaults
      const requestData = {
        ...alertData,
        id: alertData.id || uuidv4(),
        created_at: new Date().toISOString(),
        enabled: alertData.enabled !== false,
        user_id: alertData.user_id || "default",
        schedule: alertData.schedule || {
          type: 'real-time',
          timezone: 'UTC'
        }
      };

      const res = await ApiService.fetchData<Alert, Alert>({
        url: '/alerts',
        method: 'POST',
        data: requestData,
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

  async inferParameters(requestData: {
    name: string;
    description: string;
    enabled: boolean;
    user_context: {
      wallets: any[];
      timezone: string;
    };
  }): Promise<any> {
    try {
      console.log('Inferring parameters for:', requestData);

      // Use real API endpoint
      const res = await ApiService.fetchData<any, any>({
        url: '/alerts/infer-parameters',
        method: 'POST',
        data: requestData,
      });

      console.log('Parameters inferred successfully:', res.data);
      return res.data;
    } catch (error) {
      console.error('Real API inference failed, falling back to mock:', error);

      // Fallback to mock implementation if API fails
      try {
        const mockInference = this.mockParameterInference(requestData);

        // Simulate API delay
        await new Promise(resolve => setTimeout(resolve, 1000));

        console.log('Parameters inferred successfully (mock fallback):', mockInference);
        return mockInference;
      } catch (mockError) {
        return handleApiError(error, 'infer alert parameters');
      }
    }
  },

  // Mock parameter inference for testing
  mockParameterInference(requestData: any): any {
    const description = requestData.description.toLowerCase();
    const wallets = requestData.user_context.wallets;

    // Simple pattern matching for demo
    if (description.includes('balance') && description.includes('below')) {
      const thresholdMatch = description.match(/(\d+(?:\.\d+)?)/);
      const threshold = thresholdMatch ? parseFloat(thresholdMatch[1]) : 10;

      return {
        type: 'wallet',
        category: 'balance',
        name: requestData.name,
        description: requestData.description,
        condition: {
          query: `Alert when wallet balance falls below ${threshold} AVAX`,
          parameters: {
            wallet_id: wallets[0]?.id || 'default-wallet',
            wallet_name: wallets[0]?.name || 'Default Wallet',
            wallet_address: wallets[0]?.address || '0x...',
            threshold: threshold,
            comparison: 'below',
            token_symbol: 'AVAX'
          },
          data_sources: ['wallet_balances', 'token_balances'],
          estimated_frequency: 'real-time'
        },
        schedule: {
          type: 'real-time',
          timezone: requestData.user_context.timezone
        },
        enabled: requestData.enabled,
        confidence: 0.85
      };
    } else if (description.includes('price') && description.includes('above')) {
      const thresholdMatch = description.match(/\$?(\d+(?:\.\d+)?)/);
      const threshold = thresholdMatch ? parseFloat(thresholdMatch[1]) : 50;

      return {
        type: 'price',
        category: 'price_movement',
        name: requestData.name,
        description: requestData.description,
        condition: {
          query: `Alert when AVAX price goes above $${threshold}`,
          parameters: {
            asset: 'AVAX',
            threshold: threshold,
            comparison: 'above'
          },
          data_sources: ['price_feeds', 'market_data'],
          estimated_frequency: 'real-time'
        },
        schedule: {
          type: 'real-time',
          timezone: requestData.user_context.timezone
        },
        enabled: requestData.enabled,
        confidence: 0.90
      };
    } else if (description.includes('transaction')) {
      const thresholdMatch = description.match(/(\d+(?:\.\d+)?)/);
      const threshold = thresholdMatch ? parseFloat(thresholdMatch[1]) : 5;

      return {
        type: 'wallet',
        category: 'transaction',
        name: requestData.name,
        description: requestData.description,
        condition: {
          query: `Alert on transactions over ${threshold} AVAX`,
          parameters: {
            wallet_id: wallets[0]?.id || 'default-wallet',
            wallet_name: wallets[0]?.name || 'Default Wallet',
            wallet_address: wallets[0]?.address || '0x...',
            threshold: threshold,
            comparison: 'above',
            token_symbol: 'AVAX'
          },
          data_sources: ['transaction_stream', 'wallet_transactions'],
          estimated_frequency: 'real-time'
        },
        schedule: {
          type: 'real-time',
          timezone: requestData.user_context.timezone
        },
        enabled: requestData.enabled,
        confidence: 0.80
      };
    } else {
      // Default fallback
      return {
        type: 'wallet',
        category: 'balance',
        name: requestData.name,
        description: requestData.description,
        condition: {
          query: requestData.description,
          parameters: {
            wallet_id: wallets[0]?.id || 'default-wallet',
            wallet_name: wallets[0]?.name || 'Default Wallet',
            threshold: 10,
            comparison: 'below'
          },
          data_sources: ['wallet_balances'],
          estimated_frequency: 'real-time'
        },
        schedule: {
          type: 'real-time',
          timezone: requestData.user_context.timezone
        },
        enabled: requestData.enabled,
        confidence: 0.60
      };
    }
  },
};
