# Tutorial 3: Building Custom Alert Templates & Parameter Schemas

Alert Templates in Ekko CE allow teams to define reusable monitoring blueprints. Rather than creating static one-off alerts, templates accept parametric placeholders (e.g. `{{wallet}}`, `{{threshold}}`, `{{token}}`), making it easy for non-technical users or community members to instantiate custom alerts safely.

---

## Template Anatomy

An Alert Template consists of four components:
1. **`nl_template`**: Natural language template string with mustache-style variables.
2. **`variables`**: Schema defining variable names, types (`address`, `number`, `string`), and validation rules.
3. **`spec_blueprint`**: Standardized condition evaluation blueprint for the wasmCloud execution engine.
4. **Metadata**: Event types, category tagging, and organization visibility scopes.

---

## Step 1: Create a Template via API

Send a `POST` request to `/api/alerts/templates/`:

```json
{
  "name": "DeFi Liquidity Pool Withdrawal Alert",
  "description": "Triggers when a wallet withdraws liquidity above a specified USD equivalent from a Pool contract",
  "nl_template": "Notify me when wallet {{wallet}} withdraws more than {{amount}} {{token}} from liquidity pool {{pool_address}}",
  "variables": [
    { "name": "wallet", "type": "address", "required": true },
    { "name": "amount", "type": "number", "required": true },
    { "name": "token", "type": "string", "required": true },
    { "name": "pool_address", "type": "address", "required": true }
  ],
  "spec_blueprint": {
    "event_type": "CONTRACT_LOG_EVENT",
    "sub_event": "DEFI_WITHDRAWAL",
    "conditions": {
      "contract": "{{pool_address}}",
      "user": "{{wallet}}",
      "amount_gte": "{{amount}}"
    }
  },
  "event_type": "DEFI_EVENT",
  "is_public": true
}
```

---

## Step 2: Organize Templates into Alert Groups

Alert Groups allow teams to cluster related templates (e.g., "Treasury Security", "Protocol Risk", "Whale Movements"):

1. Open Dashboard -> **Alert Groups**.
2. Click **Create Group**.
3. Name the group `Treasury Safeguards`.
4. Add your newly created template to the group.

---

## Step 3: Instantiate an Alert from a Template

Users can now create instances from the template by passing concrete parameters:

```json
POST /api/alerts/templates/{template_id}/instantiate/
{
  "name": "Team Treasury Liquidity Watch",
  "params": {
    "wallet": "0x8888888888888888888888888888888888888888",
    "amount": 50000,
    "token": "USDC",
    "pool_address": "0x9999999999999999999999999999999999999999"
  }
}
```

This creates an active monitoring alert instance tied to your team's configuration.
