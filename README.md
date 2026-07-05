# Homelab K8s GitOps

Flux GitOps repo for a 9-node Raspberry Pi 4B k3s cluster (`alucard.dev`).
A separate ansible repo installs the OS and k3s; everything after that is
declared here and reconciled by Flux.

## Layout

```
clusters/homelab/     Flux Kustomizations (the dependency tiers)
infrastructure/
  base/<component>/   one directory per component (HelmRelease or manifests)
  controllers/        tier: cert-manager, traefik, ESO, vault, velero
  configs/            tier: cluster issuers, flux-alerts
  platform/           tier: authentik, gitea, tekton
apps/
  <name>/             one directory per app (raw manifests)
  web/ stateful/      tier membership lists
bootstrap/            flux bootstrap + vault init scripts
docs/                 architecture, runbooks, decisions
```

## Docs

- [Architecture](docs/architecture.md) — diagrams: traffic, Flux tier
  graph, secrets flow
- Runbooks: [bootstrap](docs/runbooks/bootstrap.md) ·
  [disaster recovery](docs/runbooks/disaster-recovery.md) ·
  [add an app](docs/runbooks/add-an-app.md) ·
  [monitoring](docs/runbooks/monitoring.md)
- [Decision records](docs/decisions/)
- [ARM64 notes](docs/arm64-notes.md)

## Day-to-day

```bash
flux get kustomizations              # tier status
flux reconcile kustomization <tier> --with-source
flux logs --follow --all-namespaces
kubectl get externalsecrets -A      # secret sync status
```

Reconciliation failures and Prometheus alerts land in the Matrix
**Homelab Alerts** room. Grafana: `grafana.alucard.dev`.

**If the vault pod restarted**, Vault is sealed (ESO alerts will fire):
`VAULT_UNSEAL_KEY=... ./bootstrap/vault-init.sh`
