/**
 * Billing API Service
 *
 * API calls for billing and subscription management.
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS } from '../config/api'

export interface BillingPlan {
  id: string
  name: string
  slug: string
  price_usd: number
  billing_cycle: 'monthly' | 'yearly'
  features: string[]
  not_included: string[]
  max_wallets: number
  max_alerts: number
  max_api_calls: number
  max_notifications: number
  is_active: boolean
  is_default: boolean
}

export interface BillingSubscription {
  id: string
  plan: BillingPlan
  status: 'active' | 'trialing' | 'canceled' | 'past_due'
  current_period_start: string
  current_period_end: string
  cancel_at_period_end: boolean
  created_at: string
  updated_at: string
}

export interface BillingUsageItem {
  used: number
  limit: number
  percent: number
  unlimited: boolean
}

export interface BillingUsage {
  alerts: BillingUsageItem
  wallets: BillingUsageItem
  api_calls: BillingUsageItem
  notifications: BillingUsageItem
}

export interface BillingInvoice {
  id: string
  amount_usd: number
  status: 'paid' | 'open' | 'void' | 'uncollectible'
  billed_at: string
  paid_at?: string | null
}

export interface BillingOverview {
  subscription: BillingSubscription
  plans: BillingPlan[]
  usage: BillingUsage
  invoices: BillingInvoice[]
}

class BillingApiService {
  async getOverview(): Promise<BillingOverview> {
    const response = await httpClient.get<BillingOverview>(
      API_ENDPOINTS.BILLING.OVERVIEW
    )
    return response.data
  }

  async updateSubscription(planId: string): Promise<BillingSubscription> {
    const response = await httpClient.post<BillingSubscription>(
      API_ENDPOINTS.BILLING.SUBSCRIPTION,
      { plan_id: planId }
    )
    return response.data
  }
}

export const billingApiService = new BillingApiService()
export default billingApiService
