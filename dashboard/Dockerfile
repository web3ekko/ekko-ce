# Ekko Dashboard Dockerfile
# Multi-stage build for React + TypeScript + Vite application

# Build stage
FROM node:20-slim AS builder

WORKDIR /app

# Build arguments for environment configuration
ARG VITE_API_URL=https://api.ekko.local
ARG VITE_WS_URL=wss://api.ekko.local
ARG VITE_WEBAUTHN_RP_ID=localhost
ARG VITE_WEBAUTHN_RP_NAME="Ekko Dashboard"
ARG VITE_APP_NAME="Ekko Dashboard"
ARG VITE_APP_VERSION=1.0.0

# Set environment variables from build args
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL
ENV VITE_WEBAUTHN_RP_ID=$VITE_WEBAUTHN_RP_ID
ENV VITE_WEBAUTHN_RP_NAME=$VITE_WEBAUTHN_RP_NAME
ENV VITE_APP_NAME=$VITE_APP_NAME
ENV VITE_APP_VERSION=$VITE_APP_VERSION

# Copy package files
COPY package*.json yarn.lock ./

# Install dependencies (with SSL bypass for build)
RUN yarn config set strict-ssl false && \
    yarn install --frozen-lockfile

# Copy source code
COPY . .

# Build the application (uses ENV variables set above)
RUN yarn build

# Production stage
FROM nginx:alpine AS production

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy the full nginx configuration with SPA support
COPY nginx.full.conf /etc/nginx/nginx.conf

# Expose port
EXPOSE 80

# Health check - using wget since it's available in alpine
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
