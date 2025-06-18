// Enhanced Alert Types
export enum AlertType {
  WALLET = "wallet",
  PRICE = "price",
  TIME_BOUND = "time_bound",
  DEFI_PROTOCOL = "defi_protocol",
  PORTFOLIO = "portfolio"
}

export enum AlertCategory {
  BALANCE = "balance",
  TRANSACTION = "transaction",
  PRICE_MOVEMENT = "price_movement",
  YIELD = "yield",
  LIQUIDATION = "liquidation",
  CUSTOM = "custom"
}

export interface AlertSchedule {
  type: string; // "real-time", "interval", "cron"
  interval_seconds?: number;
  cron_expression?: string;
  timezone: string;
}

export interface AlertCondition {
  query: string;
  parameters: Record<string, any>;
  polars_code?: string;
  data_sources: string[];
  estimated_frequency: string;
}

export interface JobSpecification {
  job_name: string;
  polars_code: string;
  data_sources: string[];
  schedule: AlertSchedule;
  validation_rules: Record<string, any>;
}

// Enhanced Alert interface
export interface Alert {
  id: string;
  user_id: string;
  name: string;
  description?: string;

  // Type System
  type: AlertType;
  category: AlertCategory;

  // Condition Definition
  condition: AlertCondition;

  // Execution Settings
  schedule: AlertSchedule;
  enabled: boolean;

  // Metadata
  created_at: string;
  updated_at?: string;

  // DSPy Generated
  job_spec?: JobSpecification;
  job_spec_generated_at?: string;

}

// Alert creation interfaces
export interface AlertCreate {
  id?: string;
  user_id?: string;
  name: string;
  description?: string;
  type: AlertType;
  category: AlertCategory;
  condition: AlertCondition;
  schedule?: AlertSchedule;
  enabled?: boolean;
}

// Enhanced form values for alert creation wizard
export interface AlertFormValues {
  // Step 1: Alert Type & Category Selection
  type: AlertType;
  category: AlertCategory;

  // Step 2: Basic Information
  name: string;
  description?: string;

  // Step 3: Condition Building
  query: string;
  parameters: {
    // Wallet-related parameters
    wallet_id?: string;
    wallet_address?: string;

    // Threshold parameters
    threshold?: number;
    threshold_type?: 'amount' | 'percentage';
    comparison?: 'above' | 'below' | 'equals' | 'any';

    // Asset parameters
    asset?: string;
    token_symbol?: string;

    // Time parameters
    timeframe?: string;

    // DeFi parameters
    protocol?: string;
    pool_address?: string;
    apr_threshold?: number;
  };

  // Step 4: Schedule Configuration
  schedule: {
    type: 'real-time' | 'interval' | 'cron';
    interval_seconds?: number;
    cron_expression?: string;
    timezone: string;
  };

  // Step 5: Settings
  enabled: boolean;
}

// Alert parameter configuration for dynamic form building
export interface AlertParameterConfig {
  name: string;
  type: 'wallet_selector' | 'number' | 'select' | 'asset_selector' | 'text';
  required: boolean;
  label: string;
  description?: string;
  min?: number;
  max?: number;
  step?: number;
  options?: { value: string; label: string }[];
}

// Alert type configuration for form building
export interface AlertTypeConfig {
  type: AlertType;
  category: AlertCategory;
  name: string;
  description: string;
  icon: string; // Icon name for Tabler icons
  color: string;
  parameters: AlertParameterConfig[];
  examples: string[];
  queryTemplate: string;
}

// Alert template interface
export interface AlertTemplate {
  id: string;
  name: string;
  description: string;
  type: AlertType;
  category: AlertCategory;
  condition_template: string;
  parameters: AlertTemplateParameter[];
  examples: string[];
  usage_count: number;
  rating: number;
}

export interface AlertTemplateParameter {
  name: string;
  type: string;
  required: boolean;
  default?: any;
  description: string;
  options?: any[];
}
