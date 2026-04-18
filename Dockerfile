# Build stage
FROM golang:1.25-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /mindbank ./cmd/mindbank
RUN CGO_ENABLED=0 GOOS=linux go build -o /mindbank-mcp ./cmd/mindbank-mcp

# Runtime stage
FROM alpine:3.19
RUN apk --no-cache add ca-certificates tzdata curl
COPY --from=builder /mindbank /usr/local/bin/mindbank
COPY --from=builder /mindbank-mcp /usr/local/bin/mindbank-mcp
COPY internal/db/migrations /app/migrations
COPY scripts/run-migrations.sh /app/scripts/run-migrations.sh
RUN chmod +x /app/scripts/run-migrations.sh
WORKDIR /app
EXPOSE 8095
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8095/api/v1/health || exit 1
ENTRYPOINT ["mindbank"]
