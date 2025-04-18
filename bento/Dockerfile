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

# Final stage
FROM alpine:latest

# Install runtime dependencies
RUN apk add --no-cache ca-certificates tzdata

# Set working directory
WORKDIR /app

# Copy binary and configs
COPY --from=builder /build/benthos /app/benthos
COPY config/processor.yaml /app/config.yaml
COPY config/eth_processor.yaml /app/eth_processor.yaml
COPY config/avax_processor.yaml /app/avax_processor.yaml

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV BENTHOS_CONFIG=/app/config.yaml

# Set entrypoint
ENTRYPOINT ["/app/benthos"]
CMD ["-c", "${BENTHOS_CONFIG}"]
