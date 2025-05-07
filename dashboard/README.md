# Ekko Dashboard

A modern Mantine-based UI for the Ekko Blockchain Monitor, designed to replace the Streamlit interface.

## Features

- Modern UI built with Mantine and Next.js
- TypeScript for type safety
- Responsive design for desktop and mobile
- Dashboard with key metrics
- Wallet management
- Alert system
- Agent monitoring
- Analytics

## Development

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
# Install dependencies
npm install
# or
yarn

# Run development server
npm run dev
# or
yarn dev
```

### Building for Production

```bash
npm run build
npm start
```

## Docker

The application can be built and run with Docker:

```bash
# Build the Docker image
docker build -t ekko-dashboard .

# Run the container
docker run -p 3000:3000 ekko-dashboard
```

## Environment Variables

- `NODE_ENV` - Environment (development, production)
- `VALKEY_URL` - URL for the Redis/Valkey connection
- `NATS_URL` - URL for NATS connection
- `API_URL` - URL for the backend API (optional, defaults to current host)

## Connecting to Backend Services

The dashboard connects to:
- Valkey/Redis for caching and real-time data
- NATS for messaging and events
- Streamlit backend API for data persistence
