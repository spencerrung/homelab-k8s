# Quick Start Guide

This guide will get your homelab k8s cluster up and running with GitOps.

## Prerequisites

- Running k3s cluster on Raspberry Pis (bootstrapped via ansible)
- kubectl configured to access your cluster
- Flux CLI installed: `curl -s https://fluxcd.io/install.sh | sudo bash`
- GitHub account and personal access token

## Step 1: Bootstrap Flux

```bash
# Set your GitHub token
export GITHUB_TOKEN=<your-token>

# Run the bootstrap script
./bootstrap/flux-bootstrap.sh
```

This will:
- Install Flux in the `flux-system` namespace
- Connect Flux to this GitHub repository
- Start syncing infrastructure and applications

## Step 2: Verify Flux Installation

```bash
# Check Flux components
flux check

# Watch reconciliation
flux get kustomizations --watch
```

You should see:
- `flux-system` - Flux itself
- `infrastructure` - Infrastructure components (Vault, ESO)
- `apps` - Applications (podinfo example)

## Step 3: Initialize Vault with Terraform

This setup uses **Terraform Controller** to automatically configure Vault. The Terraform runs in-cluster via Flux and stays in sync automatically!

```bash
# Run the initialization script (handles Vault init + Terraform setup)
./bootstrap/init-vault-terraform.sh
```

This will:
1. Initialize Vault (if needed)
2. Unseal Vault
3. Create a Kubernetes secret with your Vault token
4. Let Terraform automatically configure:
   - KV v2 secrets engine
   - Kubernetes authentication
   - Policies and roles for External Secrets Operator
   - Test secrets

Or manually:

```bash
# Initialize Vault
kubectl exec -it -n vault vault-0 -- vault operator init

# SAVE THE OUTPUT! You need the unseal keys and root token

# Unseal Vault (use 3 of 5 keys)
kubectl exec -it -n vault vault-0 -- vault operator unseal <key-1>
kubectl exec -it -n vault vault-0 -- vault operator unseal <key-2>
kubectl exec -it -n vault vault-0 -- vault operator unseal <key-3>

# Create secret for Terraform
kubectl create secret generic vault-terraform-vars \
  --from-literal=vault_token=<your-root-token> \
  --namespace=flux-system
```

## Step 4: Verify Terraform Configuration

Terraform Controller should have automatically configured everything. Let's verify:

```bash
# Check Terraform resource status
kubectl get terraform -n flux-system
kubectl describe terraform vault-config -n flux-system

# Check Terraform outputs (configured resources)
kubectl get secret vault-terraform-outputs -n flux-system -o jsonpath='{.data}' | jq

# Verify Vault configuration was applied
kubectl exec -it -n vault vault-0 -- vault auth list
kubectl exec -it -n vault vault-0 -- vault secrets list
kubectl exec -it -n vault vault-0 -- vault policy list
```

If Terraform failed, check logs:
```bash
kubectl logs -n flux-system -l app.kubernetes.io/name=tf-controller --follow
kubectl logs -n flux-system -l infra.contrib.fluxcd.io/terraform=vault-config
```

## Step 5: Test the Setup

### Check deployed applications

```bash
# Check all Helm releases
flux get helmreleases -A

# Should show:
# - vault (in vault namespace)
# - external-secrets (in external-secrets namespace)
# - podinfo (in podinfo namespace)
```

### Test Vault

```bash
# Add a test secret
kubectl exec -it -n vault vault-0 -- vault kv put secret/test password=mypassword

# Read it back
kubectl exec -it -n vault vault-0 -- vault kv get secret/test
```

### Access Vault UI (optional)

```bash
kubectl port-forward -n vault svc/vault 8200:8200
# Visit http://localhost:8200
```

## Step 6: Add Your First Application

1. **Create app directory:**
   ```bash
   mkdir -p apps/base/myapp
   ```

2. **Add Kubernetes manifests or HelmRelease**

3. **Add to kustomization:**
   ```bash
   # Edit apps/base/kustomization.yaml
   # Add: - myapp/
   ```

4. **Commit and push:**
   ```bash
   git add .
   git commit -m "Add myapp"
   git push
   ```

5. **Watch Flux deploy it:**
   ```bash
   flux get kustomizations --watch
   ```

## Common Commands

```bash
# Force reconciliation
flux reconcile kustomization apps --with-source

# View Flux logs
flux logs --follow --all-namespaces

# Suspend/resume reconciliation
flux suspend kustomization apps
flux resume kustomization apps

# Check status
kubectl get kustomizations -A
kubectl get helmreleases -A
kubectl get terraform -A

# View Terraform status
kubectl describe terraform vault-config -n flux-system
kubectl logs -n flux-system -l app.kubernetes.io/name=tf-controller

# Unseal Vault after restart
kubectl exec -it -n vault vault-0 -- vault operator unseal <key>

# Force Terraform reconciliation
kubectl annotate terraform vault-config -n flux-system reconcile.fluxcd.io/requestedAt="$(date +%s)"
```

## Directory Structure

```
.
├── clusters/homelab/          # Flux cluster config
│   ├── infrastructure.yaml    # Points to infrastructure
│   └── apps.yaml             # Points to apps
├── infrastructure/           # Core infrastructure
│   ├── base/
│   │   ├── vault/           # Vault secret management
│   │   ├── external-secrets/ # External Secrets Operator
│   │   └── sources/         # Helm repositories
│   └── overlays/homelab/
└── apps/                     # Applications
    ├── base/
    │   └── podinfo/         # Example app
    └── overlays/homelab/
```

## Next Steps

1. **Remove example app:** Delete `apps/base/podinfo/` when you don't need it
2. **Add more infrastructure:**
   - Ingress controller (Traefik/nginx)
   - Cert-manager for TLS
   - Monitoring (Prometheus/Grafana)
   - Storage provisioner
3. **Add your applications:** Use the podinfo example as a template
4. **Setup secret management:** Use ESO to sync secrets from Vault

## Troubleshooting

### Flux not syncing
```bash
flux get sources git
flux logs --kind=GitRepository --name=flux-system -n flux-system
```

### HelmRelease failing
```bash
kubectl describe helmrelease <name> -n <namespace>
flux logs --kind=HelmRelease --name=<name> -n <namespace>
```

### Vault sealed after restart
```bash
kubectl exec -it -n vault vault-0 -- vault operator unseal <key-1>
kubectl exec -it -n vault vault-0 -- vault operator unseal <key-2>
kubectl exec -it -n vault vault-0 -- vault operator unseal <key-3>
```

## Documentation

- [README.md](README.md) - Full repository documentation
- [infrastructure/base/vault/README.md](infrastructure/base/vault/README.md) - Vault setup
- [infrastructure/base/external-secrets/README.md](infrastructure/base/external-secrets/README.md) - ESO setup
- [Flux Documentation](https://fluxcd.io/docs/)

## Getting Help

- Check Flux status: `flux check`
- View events: `kubectl get events -A --sort-by='.lastTimestamp'`
- Check logs: `flux logs --all-namespaces --follow`
- Flux documentation: https://fluxcd.io/docs/
