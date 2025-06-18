import { AlertType, AlertCategory, AlertTypeConfig } from '@/@types/alert';

// Alert type configurations for dynamic form building
export const alertTypeConfigs: AlertTypeConfig[] = [
  {
    type: AlertType.WALLET,
    category: AlertCategory.BALANCE,
    name: "Wallet Balance Alert",
    description: "Monitor wallet balance changes",
    icon: "IconWallet",
    color: "#34C759",
    parameters: [
      {
        name: "wallet_id",
        type: "wallet_selector",
        required: true,
        label: "Select Wallet",
        description: "Choose the wallet to monitor"
      },
      {
        name: "threshold",
        type: "number",
        required: true,
        label: "Balance Threshold",
        description: "Alert when balance reaches this amount",
        min: 0,
        step: 0.1
      },
      {
        name: "comparison",
        type: "select",
        required: true,
        label: "Condition",
        description: "When to trigger the alert",
        options: [
          { value: "below", label: "Falls below" },
          { value: "above", label: "Goes above" }
        ]
      },
      {
        name: "token_symbol",
        type: "select",
        required: false,
        label: "Token (Optional)",
        description: "Specific token to monitor, leave empty for native token",
        options: [
          { value: "AVAX", label: "AVAX" },
          { value: "USDC", label: "USDC" },
          { value: "USDT", label: "USDT" },
          { value: "ETH", label: "ETH" }
        ]
      }
    ],
    examples: [
      "Alert when balance drops below 10 AVAX",
      "Notify when balance increases above 100 AVAX"
    ],
    queryTemplate: "Alert when {wallet_name} balance {comparison} {threshold} {token_symbol}"
  },
  {
    type: AlertType.WALLET,
    category: AlertCategory.TRANSACTION,
    name: "Transaction Alert",
    description: "Monitor incoming/outgoing transactions",
    icon: "IconArrowsRightLeft",
    color: "#FF3B30",
    parameters: [
      {
        name: "wallet_id",
        type: "wallet_selector",
        required: true,
        label: "Select Wallet",
        description: "Choose the wallet to monitor"
      },
      {
        name: "threshold",
        type: "number",
        required: false,
        label: "Transaction Amount",
        description: "Minimum transaction amount to alert on (optional)",
        min: 0,
        step: 0.1
      },
      {
        name: "comparison",
        type: "select",
        required: true,
        label: "Condition",
        description: "Type of transactions to monitor",
        options: [
          { value: "above", label: "Above amount" },
          { value: "below", label: "Below amount" },
          { value: "any", label: "Any transaction" }
        ]
      },
      {
        name: "token_symbol",
        type: "select",
        required: false,
        label: "Token (Optional)",
        description: "Specific token to monitor, leave empty for all tokens",
        options: [
          { value: "AVAX", label: "AVAX" },
          { value: "USDC", label: "USDC" },
          { value: "USDT", label: "USDT" },
          { value: "ETH", label: "ETH" }
        ]
      }
    ],
    examples: [
      "Alert on transactions above 5 AVAX",
      "Notify on any incoming transaction"
    ],
    queryTemplate: "Alert on transactions {comparison} {threshold} {token_symbol} in {wallet_name}"
  },
  {
    type: AlertType.PRICE,
    category: AlertCategory.PRICE_MOVEMENT,
    name: "Price Alert",
    description: "Monitor asset price changes",
    icon: "IconChartBar",
    color: "#007AFF",
    parameters: [
      {
        name: "asset",
        type: "select",
        required: true,
        label: "Select Asset",
        description: "Choose the cryptocurrency to monitor",
        options: [
          { value: "AVAX", label: "Avalanche (AVAX)" },
          { value: "ETH", label: "Ethereum (ETH)" },
          { value: "BTC", label: "Bitcoin (BTC)" },
          { value: "USDC", label: "USD Coin (USDC)" },
          { value: "USDT", label: "Tether (USDT)" }
        ]
      },
      {
        name: "threshold",
        type: "number",
        required: true,
        label: "Price Threshold ($)",
        description: "Target price in USD",
        min: 0,
        step: 0.01
      },
      {
        name: "comparison",
        type: "select",
        required: true,
        label: "Condition",
        description: "When to trigger the alert",
        options: [
          { value: "above", label: "Goes above" },
          { value: "below", label: "Falls below" }
        ]
      }
    ],
    examples: [
      "Alert when AVAX price goes above $50",
      "Notify when ETH drops below $2000"
    ],
    queryTemplate: "Alert when {asset} price {comparison} ${threshold}"
  },
  {
    type: AlertType.TIME_BOUND,
    category: AlertCategory.YIELD,
    name: "DeFi Yield Alert",
    description: "Monitor DeFi positions and yields",
    icon: "IconTrendingUp",
    color: "#9775FA",
    parameters: [
      {
        name: "protocol",
        type: "select",
        required: true,
        label: "DeFi Protocol",
        description: "Choose the DeFi protocol to monitor",
        options: [
          { value: "trader_joe", label: "Trader Joe" },
          { value: "pangolin", label: "Pangolin" },
          { value: "aave", label: "Aave" },
          { value: "benqi", label: "Benqi" }
        ]
      },
      {
        name: "apr_threshold",
        type: "number",
        required: true,
        label: "APR Threshold (%)",
        description: "Target APR percentage",
        min: 0,
        max: 1000,
        step: 0.1
      },
      {
        name: "comparison",
        type: "select",
        required: true,
        label: "Condition",
        description: "When to trigger the alert",
        options: [
          { value: "below", label: "Falls below" },
          { value: "above", label: "Goes above" }
        ]
      },
      {
        name: "wallet_id",
        type: "wallet_selector",
        required: false,
        label: "Wallet (Optional)",
        description: "Monitor specific wallet positions only"
      }
    ],
    examples: [
      "Alert when LP APR drops below 20%",
      "Notify when staking rewards exceed 15% APR"
    ],
    queryTemplate: "Alert when {protocol} APR {comparison} {apr_threshold}%"
  }
];

// Helper function to get alert type config
export const getAlertTypeConfig = (type: AlertType, category: AlertCategory): AlertTypeConfig | undefined => {
  return alertTypeConfigs.find(config => config.type === type && config.category === category);
};

// Helper function to get all configs for a specific type
export const getConfigsForType = (type: AlertType): AlertTypeConfig[] => {
  return alertTypeConfigs.filter(config => config.type === type);
};

// Helper function to generate query from template and parameters
export const generateQueryFromTemplate = (template: string, parameters: Record<string, any>): string => {
  let query = template;
  
  // Replace template variables with actual values
  Object.entries(parameters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query = query.replace(new RegExp(`{${key}}`, 'g'), String(value));
    }
  });
  
  // Clean up any remaining template variables
  query = query.replace(/{[^}]+}/g, '').replace(/\s+/g, ' ').trim();
  
  return query;
};

// Helper function to determine data sources based on alert type
export const determineDataSources = (type: AlertType, category: AlertCategory): string[] => {
  const key = `${type}_${category}`;
  const dataSources: Record<string, string[]> = {
    'wallet_balance': ['wallet_balances', 'token_balances'],
    'wallet_transaction': ['transaction_stream', 'wallet_transactions'],
    'price_price_movement': ['price_feeds', 'market_data'],
    'time_bound_yield': ['defi_protocols', 'yield_data', 'liquidity_pools']
  };
  
  return dataSources[key] || ['general'];
};
