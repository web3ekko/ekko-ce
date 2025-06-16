import appConfig from '@/configs/app.config';

export interface NotificationDestination {
  id: string;
  type: 'email' | 'telegram' | 'discord';
  name: string;
  address: string;
  enabled: boolean;
  created_at: string;
}

export interface NotificationSettings {
  destinations: NotificationDestination[];
}

class NotificationsService {
  private baseUrl = `${appConfig.apiPrefix}/api/notifications`;

  async getSettings(): Promise<NotificationSettings> {
    try {
      const response = await fetch(`${this.baseUrl}/settings`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching notification settings:', error);
      // Return default settings on error
      return {
        email: '',
        emailEnabled: false,
        telegram: '',
        telegramEnabled: false,
        discord: '',
        discordEnabled: false,
      };
    }
  }

  async saveSettings(settings: NotificationSettings): Promise<NotificationSettings> {
    try {
      const response = await fetch(`${this.baseUrl}/settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error saving notification settings:', error);
      throw error;
    }
  }
}

export const notificationsService = new NotificationsService();
