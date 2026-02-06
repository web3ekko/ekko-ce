# Deployment Documentation vs Reality Comparison

This document compares the actual deployment process (as implemented in GitLab CI) with the current documentation.

## Executive Summary

**Status**: Documentation is significantly outdated and doesn't reflect actual CI/CD deployment process.

**Key Issues**:
- ❌ References non-existent scripts (`build-actors.sh`)
- ❌ Uses old manifest names (`ekko-actors.wadm.yaml`)
- ❌ Doesn't document official Helm chart approach
- ❌ Missing manifest templating documentation
- ❌ No GitLab CI/CD documentation
- ❌ Missing verification step documentation

## Actual CI/CD Deployment Process

### GitLab CI Pipeline (.gitlab-ci.yml)

**Build Stage** (`build-wasmcloud-actors`):
```yaml
- image: rust:1.75
- rustup target add wasm32-wasip1
- cargo install wash-cli
- cd apps/wasmcloud
- ./build.sh                              # ✅ Correct script name
- export ACTOR_TAG=${CI_COMMIT_SHORT_SHA}
- ./push-actors-to-registry.sh            # Pushes to GitLab Container Registry
```

**Deploy Stage** (`deploy-wasmcloud-production`):
```yaml
- helm upgrade --install ekko-wasmcloud \
    oci://ghcr.io/wasmcloud/charts/wasmcloud-platform \  # Official chart
    --version 0.1.2 \
    --namespace ekko-production \
    # ... comprehensive configuration ...

- export MANIFEST_VERSION=${CI_COMMIT_SHORT_SHA}
- export ACTOR_TAG=${CI_COMMIT_SHORT_SHA}
- ./generate-manifest.sh                  # Template → Generated manifest

- wash app put manifests/ekko-actors-generated.yaml
- wash app deploy ekko-platform ${CI_COMMIT_SHORT_SHA}
```

**Verification Stage** (`verify-wasmcloud-production`):
```yaml
- ./verify-wadm-deployment.sh             # NEW: Manifest-driven verification
```

### Key Characteristics

1. **OCI Registry Approach**: All actors stored as OCI artifacts in GitLab Container Registry
2. **Official Helm Chart**: Uses `oci://ghcr.io/wasmcloud/charts/wasmcloud-platform:0.1.2`
3. **Template-Based Manifests**: `ekko-actors.template.yaml` → `ekko-actors-generated.yaml`
4. **Version Strategy**: Uses `CI_COMMIT_SHORT_SHA` for production, not `v1.0.0`
5. **Automated Verification**: Validates all actors and providers from manifest

## Current Documentation Issues

### DEPLOYMENT-GUIDE.md

**Line 58**: ❌ `./build-actors.sh`
- **Issue**: This script doesn't exist
- **Should Be**: `./build.sh`

**Line 174**: ❌ `wash app deploy ekko-actors.wadm.yaml`
- **Issue**: Old manifest name
- **Should Be**: Generated from template via `generate-manifest.sh`

**Line 157**: ❌ Missing official Helm chart documentation
- **Issue**: Entire deployment section describes manual WADM deployment
- **Should Be**: Document official Helm chart with full configuration

**Missing**: No mention of `generate-manifest.sh`
- **Issue**: Template approach is core to deployment strategy
- **Should Be**: Document template system and variable substitution

**Missing**: No GitLab CI/CD section
- **Issue**: Primary production deployment method not documented
- **Should Be**: Full GitLab CI pipeline documentation

**Missing**: No verification step
- **Issue**: New verification step not documented
- **Should Be**: Document `verify-wadm-deployment.sh` and manifest-driven checks

**Line 192**: ❌ `wash app list` shows wrong app name
- **Issue**: Examples show `ekko-actors`
- **Should Be**: `ekko-platform`

### README.md

**Generally Better** but still has issues:

- ✅ Correctly mentions `./build.sh`
- ✅ Mentions `generate-manifest.sh`
- ✅ Mentions official chart
- ⚠️  Could document GitLab CI process
- ⚠️  Could mention verification step
- ⚠️  Some examples use old names

## Recommended Updates

### 1. DEPLOYMENT-GUIDE.md - Complete Rewrite

Create two sections:
1. **Production Deployment (GitLab CI/CD)** - Document actual CI pipeline
2. **Development Deployment** - Manual deployment for local testing

**Required Content**:
- Official Helm chart deployment
- Template-based manifest system
- OCI registry workflow
- Verification step
- Correct script names
- CI environment variables

### 2. README.md - Minor Updates

- Add GitLab CI/CD quick reference
- Document verification step
- Update examples to use correct names
- Add link to updated DEPLOYMENT-GUIDE.md

### 3. New Document: CI-CD-DEPLOYMENT.md

Create dedicated CI/CD documentation covering:
- Pipeline stages and dependencies
- Environment variables required
- Manual triggering process
- Troubleshooting CI failures
- Rollback procedures

## Quick Fix Script Names

| Current Doc | Actual Script | Status |
|-------------|---------------|--------|
| `build-actors.sh` | `build.sh` | ❌ Wrong |
| `ekko-actors.wadm.yaml` | `ekko-actors-generated.yaml` | ❌ Wrong |
| `ekko-actors` (app name) | `ekko-platform` | ❌ Wrong |
| N/A | `generate-manifest.sh` | ⚠️  Missing |
| N/A | `push-actors-to-registry.sh` | ⚠️  Missing |
| N/A | `verify-wadm-deployment.sh` | ⚠️  Missing |

## Deployment Workflow Comparison

### Documented (DEPLOYMENT-GUIDE.md)
```
1. ./build-actors.sh (WRONG - doesn't exist)
2. wash push <registry>/<actor>:v1.0.0
3. Update wadm manifest manually
4. wash app deploy ekko-actors.wadm.yaml (WRONG - old name)
5. wash get inventory
```

### Actual (GitLab CI)
```
1. ./build.sh
2. ./push-actors-to-registry.sh (automated)
3. ./generate-manifest.sh (template → generated)
4. Deploy infrastructure (Helm chart)
5. wash app put manifests/ekko-actors-generated.yaml
6. wash app deploy ekko-platform ${CI_COMMIT_SHORT_SHA}
7. ./verify-wadm-deployment.sh (NEW - automated verification)
```

### Actual (Manual via scripts/deployment/deploy)
```
1. ./scripts/deployment/deploy .env.orbstack
   OR
   ./build.sh
   ./push-actors-to-registry.sh
   ./generate-manifest.sh
   wash app put manifests/ekko-actors-generated.yaml
   wash app deploy ekko-platform v1.0.0
```

## Priority Actions

1. **High Priority**: Fix script name references (`build-actors.sh` → `build.sh`)
2. **High Priority**: Update manifest references to template system
3. **High Priority**: Document official Helm chart deployment
4. **Medium Priority**: Add GitLab CI/CD section
5. **Medium Priority**: Document verification step
6. **Low Priority**: Update app name in examples

## Conclusion

The documentation needs significant updates to reflect:
- Official Helm chart approach
- Template-based manifest system
- GitLab CI/CD automated deployment
- New verification step
- Correct script and file names

Recommended approach: **Complete rewrite of DEPLOYMENT-GUIDE.md** to match actual CI/CD process.
