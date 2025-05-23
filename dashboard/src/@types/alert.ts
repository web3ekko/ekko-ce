export interface Alert {
  id: string;
  type: string;
  message: string;
  time: string;
  status: string;
  icon?: string;
  priority?: string;
  related_wallet_id?: string;
  related_wallet?: string; // Keeping for backward compatibility
  query?: string;
  notifications_enabled?: boolean;
}

// Complete separate interface for creating alerts to avoid TypeScript conflicts
export interface AlertCreate {
  id?: string;
  type: string;
  message: string;
  time?: string;
  status: string;
  icon?: string;
  priority?: string;
  related_wallet?: string;
  related_wallet_id?: string;
  query?: string;
  notifications_enabled?: boolean;
}

export interface AlertFormValues {
  type: string;
  message: string;
  priority: string;
  related_wallet_id: string;
  query: string;
  threshold: number;
  enableNotifications: boolean;
}
