# Build stage
FROM golang:1.24 AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy go.mod and go.sum first for better caching
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build without using the vendor directory
RUN rm -rf vendor && go mod tidy

# Build the application with optimizations
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -mod=mod -ldflags="-w -s" -o pipeline ./cmd/ekko-pipeline

# Final stage (Debian-based runtime)
FROM golang:1.24

# Create non-root user
RUN groupadd -r ekko && useradd -r -g ekko ekko

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    bash \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copy binary from builder and set permissions
COPY --from=builder /build/pipeline /app/
RUN chown ekko:ekko /app/pipeline && \
    chmod 500 /app/pipeline

# Copy start script and set permissions
COPY scripts/start.sh /app/
RUN chown ekko:ekko /app/start.sh && \
    chmod 500 /app/start.sh

# Switch to non-root user
USER ekko

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD nc -z localhost ${METRICS_PORT:-9090} || exit 1

# Run start script
ENTRYPOINT ["/app/start.sh"]
