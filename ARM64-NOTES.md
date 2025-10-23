# ARM64 / Raspberry Pi Compatibility Notes

This repository is configured to run on ARM64 architecture (Raspberry Pi).

## Verified ARM64-Compatible Components

All infrastructure components have been configured with ARM64-compatible images:

### ✅ Vault
- **Image**: `hashicorp/vault:1.15.6` (official multi-arch)
- **Injector**: `hashicorp/vault-k8s:1.4.1` (official multi-arch)
- **Status**: Fully supported on ARM64

### ✅ Terraform Controller
- **Image**: `ghcr.io/weaveworks/tf-controller:v0.16.0-rc.4` (multi-arch)
- **Runner**: `ghcr.io/weaveworks/tf-runner:v0.16.0-rc.4` (multi-arch)
- **Status**: Fully supported on ARM64

### ✅ External Secrets Operator
- **Image**: Uses official ESO images (multi-arch by default)
- **Status**: Fully supported on ARM64

### ✅ Flux CD
- **All components**: Flux is ARM64-native
- **Status**: Fully supported on ARM64

### ✅ Podinfo (Example App)
- **Image**: Multi-arch by default
- **Status**: ARM64 compatible

## Adding New Applications

When adding new applications, ensure they support ARM64:

### Check Image Compatibility

```bash
# Check if an image supports ARM64
docker manifest inspect <image:tag> | jq '.manifests[] | select(.platform.architecture=="arm64")'

# Or use crane
crane manifest <image:tag> | jq '.manifests[] | select(.platform.architecture=="arm64")'
```

### Common ARM64-Compatible Applications

✅ **Web Servers:**
- nginx (official image)
- traefik (official image)
- caddy (official image)

✅ **Databases:**
- PostgreSQL (official image)
- MySQL/MariaDB (official image)
- MongoDB (official image)
- Redis (official image)

✅ **Monitoring:**
- Prometheus (official image)
- Grafana (official image)
- Loki (official image)

✅ **CI/CD:**
- GitLab (official ARM64 support)
- Gitea (official image)
- Drone CI (official image)

✅ **Storage:**
- MinIO (official image)
- Longhorn (ARM64 support)

### Problematic Applications

Some applications don't have ARM64 images or have known issues:

❌ **Limited/No ARM64 Support:**
- Some older Java applications
- Applications with x86-specific dependencies
- Some proprietary software

**Workarounds:**
1. Use QEMU emulation (slow, not recommended)
2. Find ARM64 alternatives
3. Build your own ARM64 images
4. Use ARM64-specific forks

## Image Best Practices

### Specify Image Tags

Always specify exact image tags to ensure consistency:

```yaml
# Good
image:
  repository: hashicorp/vault
  tag: "1.15.6"

# Avoid
image:
  repository: hashicorp/vault
  tag: "latest"
```

### Verify Multi-Arch Support

Before deploying, verify the image supports ARM64:

```bash
# Using Docker
docker pull --platform linux/arm64 hashicorp/vault:1.15.6

# Using kubectl
kubectl run test --image=hashicorp/vault:1.15.6 --rm -it --restart=Never -- /bin/sh
```

### Platform Node Selectors (If Needed)

If you have a mixed architecture cluster:

```yaml
nodeSelector:
  kubernetes.io/arch: arm64
```

## Troubleshooting ARM64 Issues

### Image Pull Errors

**Symptom:**
```
exec format error
standard_init_linux.go:228: exec user process caused: exec format error
```

**Cause:** Trying to run x86_64 image on ARM64

**Solution:**
1. Check if ARM64 image exists
2. Update to multi-arch image
3. Find ARM64 alternative

### Performance Issues

ARM64 on Raspberry Pi is powerful but has limitations:

**CPU:**
- Raspberry Pi 4: 4 cores @ 1.5GHz (or 1.8GHz on Pi 4B+)
- Raspberry Pi 5: 4 cores @ 2.4GHz

**Memory:**
- Available in 2GB, 4GB, 8GB variants
- Choose resource limits accordingly

**Storage:**
- SD card I/O can be slow
- Consider USB3 SSD for better performance

### Resource Limits

Adjust resource limits for Raspberry Pi constraints:

```yaml
resources:
  requests:
    cpu: 50m      # Lower for Pi
    memory: 64Mi  # Conservative memory
  limits:
    cpu: 500m     # Don't starve other pods
    memory: 512Mi # Leave headroom
```

## Testing New Images

Before deploying to production:

```bash
# Test locally on Pi
docker run --rm -it --platform linux/arm64 <image:tag> /bin/sh

# Or in k3s
kubectl run test-pod \
  --image=<image:tag> \
  --rm -it \
  --restart=Never \
  -- /bin/sh
```

## Building Custom ARM64 Images

If you need to build your own:

```dockerfile
# Multi-arch Dockerfile
FROM --platform=$BUILDPLATFORM golang:1.21 as builder
ARG TARGETPLATFORM
ARG BUILDPLATFORM
# ... build for target platform

FROM alpine:latest
# ... final image
```

Build multi-arch:
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t myapp:latest \
  --push \
  .
```

## Resource Monitoring

Monitor resource usage on your Pi cluster:

```bash
# Node resources
kubectl top nodes

# Pod resources
kubectl top pods -A

# Check for resource pressure
kubectl describe nodes | grep -A 5 "Allocated resources"
```

## Performance Optimization

### 1. Use Local Storage

For databases and stateful apps, use local SSD over NFS/network storage.

### 2. Limit Concurrent Deployments

```yaml
# In infrastructure kustomization
spec:
  wait: true  # Wait for resources to be ready
  timeout: 10m
```

### 3. Set Resource Requests/Limits

Always set both to prevent resource contention:

```yaml
resources:
  requests:  # Guaranteed
    cpu: 100m
    memory: 128Mi
  limits:    # Maximum
    cpu: 500m
    memory: 512Mi
```

### 4. Use Pod Disruption Budgets

For critical services:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: vault-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: vault
```

## Raspberry Pi Models

Recommended for k3s clusters:

✅ **Raspberry Pi 5** (Best)
- 4 cores @ 2.4GHz
- 4GB or 8GB RAM
- PCIe for NVMe SSD

✅ **Raspberry Pi 4 (8GB)** (Good)
- 4 cores @ 1.8GHz
- 8GB RAM
- USB3 for SSD

⚠️ **Raspberry Pi 4 (4GB)** (Acceptable)
- Limit number of services
- Monitor memory usage

❌ **Raspberry Pi 3** (Not Recommended)
- Only 1GB RAM
- Slower CPU
- Will struggle with multiple services

## Cluster Sizing Guide

| Cluster Size | Recommended For | Min RAM per Node |
|--------------|----------------|------------------|
| 3 nodes | Small homelab | 4GB |
| 5 nodes | Medium homelab | 4GB |
| 7+ nodes | Large homelab | 8GB |

## Additional Resources

- [k3s on Raspberry Pi](https://docs.k3s.io/installation/requirements)
- [Docker Hub ARM64 images](https://hub.docker.com/search?architecture=arm64)
- [CNCF Landscape ARM64](https://landscape.cncf.io/)
- [Awesome ARM](https://github.com/embedded-boston/awesome-embedded-systems)

## Verification Checklist

Before deploying a new application:

- [ ] Check image supports `linux/arm64`
- [ ] Test image on one Pi node
- [ ] Set appropriate resource limits
- [ ] Monitor resource usage
- [ ] Document any ARM64-specific configuration
