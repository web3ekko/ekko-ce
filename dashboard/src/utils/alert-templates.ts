export type AlertTargetType = 'wallet' | 'network' | 'protocol' | 'token' | 'contract' | 'nft'

export type TemplateVariable = {
  id?: string
  name?: string
  label?: string
  description?: string
  type?: string
  required?: boolean
  default?: unknown
  validation?: {
    options?: Array<{ value: string; label?: string }> | string[]
  }
}

export type TemplateLike = {
  template_type?: string
  alert_type?: string
  spec?: { variables?: TemplateVariable[] } | null
  variables?: TemplateVariable[] | null
}

export function getVariableId(variable: TemplateVariable): string | null {
  const raw = variable.id ?? variable.name
  if (!raw || typeof raw !== 'string') return null
  const trimmed = raw.trim()
  return trimmed.length ? trimmed : null
}

export function buildTargetingVariableIds(alertType: AlertTargetType): Set<string> {
  const base = new Set([
    'network',
    'networks',
    'network_key',
    'chain',
    'chains',
    'chain_id',
    'subnet',
    'network_id',
  ])

  if (alertType === 'wallet') {
    ;[
      'wallet',
      'wallet_key',
      'wallet_address',
      'address',
      'wallet_group',
      'wallet_group_id',
      'wallets',
      'addresses',
      'target_wallet',
      'target_key',
      'target',
      'targets',
    ].forEach((id) => base.add(id))
    return base
  }

  if (alertType === 'network') {
    base.add('network_key')
    return base
  }

  if (alertType === 'protocol') {
    ;['protocol_key', 'protocol', 'protocol_name', 'protocol_id'].forEach((id) => base.add(id))
    return base
  }

  if (alertType === 'token') {
    ;[
      'token',
      'token_key',
      'token_address',
      'token_contract',
      'token_contract_address',
      'token_id',
      'asset',
      'asset_address',
      'tokens',
    ].forEach((id) => base.add(id))
    return base
  }

  if (alertType === 'contract' || alertType === 'nft') {
    ;[
      'contract',
      'contract_key',
      'contract_address',
      'contract_addresses',
      'contracts',
      'protocol',
      'protocol_address',
      'protocol_addresses',
      'protocol_contract',
      'collection',
      'collection_key',
      'collection_address',
      'collection_addresses',
      'nft_contract',
      'nft_contract_address',
      'token_id',
    ].forEach((id) => base.add(id))
    return base
  }

  return base
}

export function isValueProvided(value: unknown): boolean {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.length > 0
  return true
}

export function setsEqual<T>(a: Set<T>, b: Set<T>): boolean {
  if (a.size !== b.size) return false
  for (const v of a) {
    if (!b.has(v)) return false
  }
  return true
}

export function getTemplateTargetType(template: Pick<TemplateLike, 'template_type' | 'alert_type'>): AlertTargetType {
  const templateType = (template.template_type || '').toLowerCase()
  if (templateType === 'wallet') return 'wallet'
  if (templateType === 'token') return 'token'
  if (templateType === 'network') return 'network'
  if (templateType === 'protocol') return 'protocol'
  if (templateType === 'contract') return 'contract'
  if (templateType === 'anomaly') return 'network'

  const fallback = (template.alert_type || '').toLowerCase()
  if (
    fallback === 'wallet' ||
    fallback === 'network' ||
    fallback === 'protocol' ||
    fallback === 'token' ||
    fallback === 'contract' ||
    fallback === 'nft'
  ) {
    return fallback as AlertTargetType
  }

  return 'wallet'
}

export function extractTemplateVariables(template: TemplateLike): TemplateVariable[] {
  const specVars = template.spec?.variables
  if (Array.isArray(specVars)) return specVars
  if (Array.isArray(template.variables)) return template.variables
  return []
}

export function getTemplateRequiredParamIds(template: TemplateLike): Set<string> {
  const targetAlertType = getTemplateTargetType(template)
  const targetingIds = buildTargetingVariableIds(targetAlertType)

  const requiredIds = new Set<string>()
  for (const variable of extractTemplateVariables(template)) {
    if (!variable?.required) continue
    const id = getVariableId(variable)
    if (!id) continue
    if (targetingIds.has(id.toLowerCase())) continue
    requiredIds.add(id.toLowerCase())
  }
  return requiredIds
}

