FROM node:23-alpine

WORKDIR /app

# Install Yarn 
RUN apk add --no-cache libc6-compat curl
RUN corepack enable

# Copy package files
COPY package.json yarn.lock* .yarnrc.yml ./
COPY .yarn ./.yarn

# Install dependencies
RUN yarn install

# Copy source files
COPY . .

# Set environment variables
ENV NODE_ENV=development

# Build the application
RUN yarn build

# Expose the port the app runs on
EXPOSE 5173

# Command to run the application
CMD ["yarn", "preview", "--host", "0.0.0.0"]
