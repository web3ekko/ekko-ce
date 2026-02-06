# Ekko CE (Community Edition)

A minimal, open-source extraction of the Ekko platform with three core services:

- `api/` — Django REST API
- `dashboard/` — React + Vite dashboard
- `wasmcloud/` — wasmCloud actors/providers source tree

This repo is wired to run the stack with a single Docker Compose file for local development.

## Quick Start

1. Build and start everything:

```bash
docker compose up --build
```

2. (Optional) Create an admin user:

```bash
docker compose exec api python manage.py createsuperuser
```

3. Open the apps:

- Dashboard: http://localhost:3000
- API health: http://localhost:8000/health/
- API admin: http://localhost:8000/admin/
- NATS monitoring: http://localhost:8222
- MinIO console: http://localhost:9001

## Environment Overrides

Compose uses sensible defaults. To override, copy `.env.example` to `.env` and adjust values.

```bash
cp .env.example .env
```

## What Docker Compose Runs

- PostgreSQL
- Redis
- NATS (JetStream enabled)
- MinIO (S3-compatible storage)
- Docker registry (for wasmCloud artifacts)
- Django API
- React dashboard
- wasmCloud host

The API container runs database migrations on startup and collects static files automatically.

## wasmCloud Notes

The `wasmcloud/` directory contains the actor/provider source. The compose stack starts a wasmCloud host, but does not deploy actors/providers by default.

For building and deploying actors/providers, follow the instructions in `wasmcloud/README.md` and use the local registry (`localhost:5001`) if you want to publish artifacts from your machine.

## Common Commands

Stop the stack:

```bash
docker compose down
```

Reset all data:

```bash
docker compose down -v
```

Re-run migrations:

```bash
docker compose exec api python manage.py migrate
```

## Troubleshooting

- If ports are already in use, update the port mappings in `docker-compose.yml`.
- If the dashboard fails to build, delete the build cache with:

```bash
docker builder prune
```
