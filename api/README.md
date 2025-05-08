# Ekko FastAPI Service

A lightweight API service that interfaces with NATS JetStream for the Ekko Dashboard, providing:

1. REST API endpoints for the Mantine dashboard frontend
2. Background processing of NATS messages
3. JetStream storage for wallet and alert data

## Features

- Complete REST API for wallets and alerts data
- Real-time message processing from NATS topics
- Automatic stream and key-value store creation
- Event publishing for front-end notifications

## API Endpoints

### Wallets
- `GET /wallets` - List all wallets
- `GET /wallets/{id}` - Get a specific wallet
- `POST /wallets` - Create a new wallet
- `PUT /wallets/{id}` - Update a wallet
- `DELETE /wallets/{id}` - Delete a wallet

### Alerts
- `GET /alerts` - List all alerts
- `GET /alerts/{id}` - Get a specific alert
- `POST /alerts` - Create a new alert
- `PUT /alerts/{id}` - Update an alert
- `DELETE /alerts/{id}` - Delete an alert

### System
- `GET /health` - Health check endpoint
- `GET /` - API status check

## Development

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the API server with auto-reload
uvicorn app.main:app --reload
```

### Environment Variables
- `NATS_URL` - URL for the NATS server (default: `nats://localhost:4222`)

## API Documentation

When running, access the auto-generated API documentation at:
- OpenAPI UI: http://localhost:8000/docs
- ReDoc UI: http://localhost:8000/redoc
