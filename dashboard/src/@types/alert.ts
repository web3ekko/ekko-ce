export interface Alert {
  id: string;
  type: string;
  message: string;
  time: string;
  status: string;
  icon?: string;
  priority?: string;
  related_wallet?: string;
  query?: string;
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
  query?: string;
}

export interface AlertFormValues {
  type: string;
  message: string;
  priority: string;
  related_wallet: string;
  query: string;
  threshold: number;
  enableNotifications: boolean;
}
