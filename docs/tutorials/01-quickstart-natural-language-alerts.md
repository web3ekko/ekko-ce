# Tutorial 1: Natural Language Alerts & Webhooks

In this tutorial, you will learn how to start Ekko CE, create a real-time blockchain monitoring alert using natural language, and route triggered notifications to a webhook target.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/) or OrbStack installed and running.
- A local terminal shell.
- A free webhook inspection endpoint (e.g. from [webhook.site](https://webhook.site)).

---

## Step 1: Clone and Start Ekko CE

1. Copy the environment configuration defaults:

   ```bash
   cp .env.example .env
   ```

2. Start the full service stack:

   ```bash
   docker compose up --build -d
   ```

3. Confirm all services are healthy:

   ```bash
   docker compose ps
   ```

   You should see `postgres`, `redis`, `nats`, `minio`, `api`, `dashboard`, and `wasmcloud` running.

---

## Step 2: Access the Dashboard

Open your web browser and navigate to:
```
http://localhost:3000
```

You will be greeted by the Ekko CE Dashboard home page.

---

## Step 3: Authenticate & Generate API Tokens

Ekko CE enforces Knox Token authentication for protected REST API endpoints.

### Option A: Dashboard Login
Log in or sign up on `http://localhost:3000` using WebAuthn/Passkeys or Email OTP fallback.

### Option B: Generating Tokens for cURL / API Testing
Run the following command to generate a Knox API token for testing:

```bash
docker compose exec api python manage.py shell -c "from authentication.models import User; from knox.models import AuthToken; user, _ = User.objects.get_or_create(email='dev@ekko.dev', defaults={'username': 'devuser'}); _, token = AuthToken.objects.create(user); print('AUTH_TOKEN:', token)"
```

Verify token authentication with a GET request:

```bash
curl -H "Authorization: Token <YOUR_AUTH_TOKEN>" http://localhost:8000/api/alert-templates/
```

---

## Step 4: Create an Alert Using Natural Language

1. On the dashboard homepage, navigate to **Create Alert**.
2. In the natural language input prompt, enter your monitoring intent in plain English:

   ```text
   Alert me when wallet 0x742d35Cc6634C0532925a3b844Bc454e4438f44e sends more than 10 AVAX on Avalanche C-Chain
   ```

3. Click **Parse Intent**.
4. The Ekko API will call the NLP parser endpoint (`/api/alerts/parse/`) and return a structured alert specification detailing:
   - **Target Address:** `0x742d35Cc6634C0532925a3b844Bc454e4438f44e`
   - **Condition:** `value > 10 AVAX`
   - **Direction:** `OUTBOUND`
   - **Network:** `Avalanche C-Chain`

5. Confirm the parsed specification and click **Create Alert Instance**.

---

## Step 4: Configure Webhook Notification Channel

1. Navigate to **Alert Settings** -> **Notification Channels**.
2. Click **Add Channel** and select **Webhook**.
3. Paste your [webhook.site](https://webhook.site) URL into the `Endpoint URL` field:
   ```text
   https://webhook.site/your-unique-id
   ```
4. Set the payload format to `JSON` and click **Save Channel**.

---

## Step 5: Test and Verify Notifications

When matching transaction activity occurs on the monitored network, Ekko's `alerts-processor` actor evaluates the condition and dispatches a notification payload to your webhook.

### Example Webhook Payload:
```json
{
  "event": "ALERT_TRIGGERED",
  "alert_id": "alt_8f93a10c",
  "alert_name": "AVAX Transfer Threshold > 10 AVAX",
  "chain": "avalanche-c-chain",
  "transaction_hash": "0xa1b2c3d4e5f6...",
  "from_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
  "value_formatted": "25.0 AVAX",
  "timestamp": "2026-07-25T13:30:00Z"
}
```

---

## Next Steps

- Proceed to [Tutorial 2: Monitoring Avalanche Subnets (L1s) & Custom Chains](./02-monitoring-avalanche-subnets.md).
