# Deployment Order

This document explains the order in which Flux applies resources.

## Why Order Matters

Some resources depend on others being ready first:
- **Terraform resources** need tf-controller CRDs installed
- **Apps** might need infrastructure like ingress controllers
- **Helm releases** need HelmRepositories to be synced

## Current Deployment Order

```
┌─────────────────────────────────────────────────┐
│  1. flux-system (bootstrapped first)            │
│     - Flux controllers                          │
│     - GitRepository source                      │
└─────────────────┬───────────────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────────────┐
│  2. infrastructure                              │
│     - Helm repositories (sources)               │
│     - tf-controller (installs CRDs)             │
│     - Vault                                     │
│     - External Secrets Operator                 │
└─────────────────┬───────────────────────────────┘
                  │
                  ├──────────────────┬─────────────┐
                  ↓                  ↓             ↓
┌──────────────────────────┐  ┌──────────────┐  ┌─────────────┐
│  3. terraform-configs    │  │  4. apps     │  │  (future)   │
│     - Vault Terraform    │  │     - podinfo│  │  - ingress  │
│     - Other IaC          │  │     - etc.   │  │  - monitoring│
└──────────────────────────┘  └──────────────┘  └─────────────┘
```

## Kustomization Dependencies

### clusters/homelab/infrastructure.yaml
```yaml
spec:
  # No dependencies - runs first after flux-system
  path: ./infrastructure/overlays/homelab
```

### clusters/homelab/terraform-configs.yaml
```yaml
spec:
  dependsOn:
    - name: infrastructure  # Waits for infrastructure
  path: ./infrastructure/base/terraform-configs
```

### clusters/homelab/apps.yaml
```yaml
spec:
  dependsOn:
    - name: infrastructure  # Waits for infrastructure
  path: ./apps/overlays/homelab
```

## Timing

Typical deployment timeline after a git push:

| Time | Event |
|------|-------|
| T+0s | Git push |
| T+30s | Flux detects change (polls every 1m, might catch earlier) |
| T+1m | Infrastructure kustomization starts |
| T+2m | Helm repositories synced |
| T+3m | tf-controller pod starting |
| T+4m | Vault pod starting |
| T+5m | ESO pod starting |
| T+6m | Infrastructure ready |
| T+7m | terraform-configs starts (Vault configuration) |
| T+8m | Apps start deploying |
| T+10m | Everything running |

*Times are approximate and depend on cluster resources*

## Health Checks

Flux waits for resources to be healthy before marking a kustomization as ready:

```bash
# Check what's blocking
flux get kustomizations -A

# If infrastructure stuck:
kubectl get helmreleases -n flux-system
kubectl get helmreleases -n vault
kubectl get helmreleases -n external-secrets

# If terraform-configs stuck:
kubectl get terraform -n flux-system
kubectl describe terraform vault-config -n flux-system

# If apps stuck:
kubectl get helmreleases -n podinfo
```

## Common Issues

### "no matches for kind Terraform"
- **Cause**: Trying to apply Terraform resource before tf-controller is ready
- **Solution**: Ensure Terraform resources are in terraform-configs kustomization, not infrastructure
- **Check**: `kubectl get crd | grep terraform`

### "HelmRepository not ready"
- **Cause**: Helm chart source not synced yet
- **Solution**: Wait, or check network connectivity
- **Check**: `flux get sources helm -A`

### "Dependency not ready"
- **Cause**: Parent kustomization has errors
- **Solution**: Fix parent kustomization first
- **Check**: `flux get kustomizations -A`

## Modifying Deployment Order

To add a new kustomization that depends on infrastructure:

```yaml
# clusters/homelab/my-new-kustomization.yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: my-component
  namespace: flux-system
spec:
  interval: 10m0s
  dependsOn:
    - name: infrastructure      # Wait for infrastructure
    - name: terraform-configs   # And terraform configs (optional)
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./path/to/my/component
  prune: true
  wait: true
```

## Manual Intervention Points

Some steps require manual intervention:

1. **Vault initialization** (one-time)
   ```bash
   ./bootstrap/init-vault-terraform.sh
   ```

2. **Vault unsealing** (after restart)
   ```bash
   kubectl exec -it -n vault vault-0 -- vault operator unseal
   ```

Everything else is fully automated!

## Debugging Stuck Deployments

```bash
# 1. Check overall status
flux get kustomizations -A

# 2. Look for the first failure in the chain
# Start from the top: infrastructure

# 3. Check events
kubectl get events -n flux-system --sort-by='.lastTimestamp' | tail -20

# 4. Check specific resources
kubectl describe kustomization infrastructure -n flux-system

# 5. Force reconciliation if needed
flux reconcile kustomization infrastructure --with-source

# 6. Check logs
flux logs --kind=Kustomization --name=infrastructure -n flux-system
```

## Success Criteria

All kustomizations should show "Applied revision":

```bash
$ flux get kustomizations -A

NAMESPACE     NAME               READY   MESSAGE
flux-system   flux-system        True    Applied revision: main@sha1:abc123
flux-system   infrastructure     True    Applied revision: main@sha1:abc123
flux-system   terraform-configs  True    Applied revision: main@sha1:abc123
flux-system   apps              True    Applied revision: main@sha1:abc123
```

If any show False, investigate that kustomization first!
