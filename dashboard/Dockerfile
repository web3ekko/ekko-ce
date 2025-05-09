FROM node:23-alpine

WORKDIR /app

# Install Yarn and other dependencies
RUN apk add --no-cache libc6-compat curl
RUN corepack enable

# Copy package files first for better layer caching
COPY package.json yarn.lock* ./
COPY .yarnrc.yml* ./
COPY .yarn ./.yarn

# Install dependencies with verbose logging
RUN yarn install --immutable

# Copy source files
COPY . .

# Set environment variables
ENV NODE_ENV=development

# Expose the port the app runs on (Vite uses 5173 by default)
EXPOSE 5173

# Command to run the development server with host binding to all interfaces
CMD ["yarn", "dev", "--host", "0.0.0.0", "--port", "5173"]
