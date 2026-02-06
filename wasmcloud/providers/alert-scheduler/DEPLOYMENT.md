# Alert Scheduler Provider - WADM Deployment Guide

This provider is packaged as a PAR and deployed as a wasmCloud capability via WADM (no Docker/Helm).

## Build and Package

### Local PAR (host architecture)
```bash
cd apps/wasmcloud
./build-provider.sh alert-scheduler
```

### K8s/Linux PARs (cross-compile)
```bash
cd apps/wasmcloud
SKIP_ACTOR_BUILD=true ./build.sh
```

### Push to Registry
```bash
cd apps/wasmcloud
PUSH_TO_REGISTRY=true ./build-provider.sh alert-scheduler
```

## WADM Manifest Entry

Add/update the provider entry in `apps/wasmcloud/manifests/ekko-actors.template.yaml`:

```yaml
- name: alert-scheduler
  type: capability
  properties:
    image: ${PROVIDER_REGISTRY}/alert-scheduler:${PROVIDER_TAG}
    config:
      - name: alert-scheduler-config
        properties:
          redis_url: "${REDIS_URL}"
          nats_url: "${NATS_URL}"
          nats_stream_name: "ALERT_JOBS"
          deduplication_window_seconds: "300"
          schedule_request_dedupe_ttl_secs: "86400"
          max_concurrent_alerts: "50000"
```

## Deploy via WADM

```bash
cd apps/wasmcloud
MANIFEST_VERSION=v1.0.1 ./generate-manifest.sh
wash app put manifests/ekko-actors-generated.yaml
wash app deploy ekko-platform v1.0.1
```

## Verify

```bash
wash app status ekko-platform
wash get providers | rg alert-scheduler
```

## Configuration Keys

Required:
- `redis_url`

Optional (defaults in code):
- `nats_url`
- `nats_stream_name`
- `deduplication_window_seconds`
- `schedule_request_dedupe_ttl_secs`
- `max_concurrent_alerts`
- `cleanup_batch_size`
- `max_instance_age_seconds`
- `redis_pool_size`
- `connection_timeout_ms`
- `retry_attempts`
- `retry_delay_ms`
- `instance_scan_batch_size`
- `schedule_due_batch_size`
- `microbatch_max_targets`
- `event_job_targets_cap`

## References

- PRD: `docs/prd/wasmcloud/providers/PRD-Alert-Scheduler-Provider-v2-USDT.md`
- WADM template: `apps/wasmcloud/manifests/ekko-actors.template.yaml`
- Build script: `apps/wasmcloud/build.sh`
