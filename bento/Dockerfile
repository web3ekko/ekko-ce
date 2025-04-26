# Build stage
FROM golang:1.21-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git build-base

# Set working directory
WORKDIR /build

# Copy Go module files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build custom Benthos with our processors
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o benthos ./cmd/benthos

# Build all plugins in bento/plugins as .so files
RUN mkdir -p /build/plugins \
  && for f in ./bento/plugins/*.go; do \
    name=$(basename "$f" .go); \
    CGO_ENABLED=1 GOOS=linux GOARCH=amd64 go build -buildmode=plugin -o /build/plugins/$name.so $f; \
  done


# Final stage
FROM alpine:latest

# Install runtime dependencies
RUN apk add --no-cache ca-certificates tzdata

# Set working directory
WORKDIR /app

# Copy binary, plugins, and configs
COPY --from=builder /build/benthos /app/benthos
COPY --from=builder /build/plugins /app/plugins
# COPY config/processor.yaml /app/config.yaml
# COPY config/eth_processor.yaml /app/eth_processor.yaml
# COPY config/avax_processor.yaml /app/avax_processor.yaml
COPY config/evm_decode_pipeline.yaml /app/evm_decode_pipeline.yaml
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV BENTHOS_CONFIG=/app/evm_decode_pipeline.yaml

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
