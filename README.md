# Homelab K8s GitOps

GitOps repository for managing Kubernetes applications on the homelab k3s cluster using Flux.

## Overview

This repository uses [Flux](https://fluxcd.io/) to manage application deployments on a Raspberry Pi k3s cluster. All cluster state is defined declaratively in Git, and Flux automatically reconciles the cluster to match.

## Repository Structure

```
.
├── clusters/
│   └── homelab/              # Main k3s cluster configuration
│       └── flux-system/      # Flux system components (auto-generated)
├── infrastructure/           # Core infrastructure components
│   ├── base/                 # Base infrastructure manifests
│   └── overlays/
│       └── homelab/          # Homelab-specific infrastructure config
├── apps/                     # Application deployments
│   ├── base/                 # Base application manifests
│   └── overlays/
│       └── homelab/          # Homelab-specific app config
└── bootstrap/                # Bootstrap scripts and helpers
```

## Prerequisites

- Running k3s cluster (bootstrapped via ansible)
- `flux` CLI installed: `curl -s https://fluxcd.io/install.sh | sudo bash`
- `kubectl` configured to access your cluster
- GitHub personal access token with repo permissions

## Initial Setup

1. **Bootstrap Flux on your cluster:**

   ```bash
   ./bootstrap/flux-bootstrap.sh
   ```

   Or manually:

   ```bash
   flux bootstrap github \
     --owner=<your-github-username> \
     --repository=homelab-k8s \
     --branch=main \
     --path=clusters/homelab \
     --personal
   ```

2. **Verify Flux installation:**

   ```bash
   flux check
   kubectl get pods -n flux-system
   ```

3. **Watch Flux reconcile:**

   ```bash
   flux get kustomizations --watch
   ```

## Adding Infrastructure Components

Infrastructure components (ingress controllers, cert-manager, storage, etc.) go in the `infrastructure/` directory:

1. Add base manifests or Helm releases to `infrastructure/base/`
2. Add environment-specific overlays to `infrastructure/overlays/homelab/`
3. Reference in `clusters/homelab/infrastructure.yaml`
4. Commit and push - Flux will automatically deploy

## Adding Applications

Applications go in the `apps/` directory:

1. Add base manifests or Helm releases to `apps/base/`
2. Add environment-specific overlays to `apps/overlays/homelab/`
3. Reference in `clusters/homelab/apps.yaml`
4. Commit and push - Flux will automatically deploy

## Common Commands

```bash
# Check Flux status
flux check

# View all Flux resources
flux get all

# View Kustomizations
flux get kustomizations

# View Helm releases
flux get helmreleases

# Suspend reconciliation (for maintenance)
flux suspend kustomization apps

# Resume reconciliation
flux resume kustomization apps

# Force immediate reconciliation
flux reconcile kustomization apps --with-source

# View logs
flux logs --follow --all-namespaces
```

## Troubleshooting

- **Check Flux reconciliation status:** `flux get kustomizations`
- **View events:** `kubectl get events -n flux-system --sort-by='.lastTimestamp'`
- **Check specific resource:** `flux get helmrelease <name> -n <namespace>`
- **View logs:** `flux logs --kind=HelmRelease --name=<name> -n <namespace>`

## Directory Conventions

- **base/**: Shared base configurations using Kustomize or raw manifests
- **overlays/**: Environment-specific customizations
- **Namespaces**: Each app/component creates its own namespace
- **Helm**: Use `HelmRepository` and `HelmRelease` CRDs for Helm charts

## Security Notes

- Secrets should be encrypted using SOPS or sealed-secrets (to be configured)
- Never commit plain-text credentials
- Use read-only deploy keys where possible

## Links

- [Flux Documentation](https://fluxcd.io/docs/)
- [Flux GitHub](https://github.com/fluxcd/flux2)
- [Awesome Flux](https://github.com/fluxcd/awesome-flux)
