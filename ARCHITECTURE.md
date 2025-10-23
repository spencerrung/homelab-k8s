# Architecture Overview

This document explains the architecture of the homelab GitOps setup.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GitHub Repository                        │
│  (homelab-k8s - this repo)                                      │
│                                                                   │
│  ├── clusters/homelab/        - Flux cluster config             │
│  ├── infrastructure/          - Vault, ESO, Terraform code       │
│  └── apps/                    - Application manifests            │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ Git sync (every 1m)
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster (k3s)                      │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    flux-system namespace                  │  │
│  │                                                            │  │
│  │  ├── source-controller    - Fetches from Git             │  │
│  │  ├── kustomize-controller - Applies manifests            │  │
│  │  ├── helm-controller      - Manages Helm releases        │  │
│  │  └── tf-controller        - Runs Terraform               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    vault namespace                        │  │
│  │                                                            │  │
│  │  └── vault-0              - Secret storage                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              external-secrets namespace                   │  │
│  │                                                            │  │
│  │  └── external-secrets     - Syncs Vault → K8s secrets    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    app namespaces                         │  │
│  │                                                            │  │
│  │  └── your-app             - Your applications            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## GitOps Flow

```
Developer
    │
    │ 1. Edit code
    │ 2. git commit
    │ 3. git push
    ↓
GitHub Repository
    ↓
    │ Flux polls every 1m
    ↓
Flux Controllers
    │
    ├─→ Kustomize Controller ──→ Apply K8s manifests
    │
    ├─→ Helm Controller ──────→ Deploy Helm releases
    │
    └─→ Terraform Controller ──→ Run Terraform
            │
            ↓
        Infrastructure
        (Vault, Cloud, etc.)
```

## Terraform + Vault Flow

```
┌──────────────────────────────────────────────────────────────┐
│  1. Terraform code in Git                                     │
│     infrastructure/base/vault/terraform/main.tf               │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Flux syncs
                 ↓
┌──────────────────────────────────────────────────────────────┐
│  2. Terraform Controller detects Terraform CRD                │
│     infrastructure/base/vault/terraform-vault-config.yaml     │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Creates runner pod
                 ↓
┌──────────────────────────────────────────────────────────────┐
│  3. Runner Pod executes Terraform                             │
│     - terraform init                                          │
│     - terraform plan                                          │
│     - terraform apply                                         │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Uses vault_token from Secret
                 ↓
┌──────────────────────────────────────────────────────────────┐
│  4. Vault configured via Terraform                            │
│     - KV v2 secrets engine                                    │
│     - Kubernetes auth backend                                 │
│     - Policies and roles                                      │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Outputs stored in Secret
                 ↓
┌──────────────────────────────────────────────────────────────┐
│  5. Terraform outputs available                               │
│     vault-terraform-outputs Secret                            │
└──────────────────────────────────────────────────────────────┘
```

## Secret Management Flow

```
Developer stores secret in Vault
    │
    ↓
┌─────────────────────────────────────┐
│  Vault (vault namespace)             │
│  secret/data/myapp/config            │
│    - db_password: xxxxx              │
│    - api_key: yyyyy                  │
└─────────────┬───────────────────────┘
              │
              │ External Secrets Operator polls every 1h
              ↓
┌─────────────────────────────────────┐
│  ExternalSecret (myapp namespace)    │
│  Spec:                               │
│    secretStoreRef: vault-backend     │
│    data:                             │
│      - secretKey: db_password        │
│        remoteRef:                    │
│          key: myapp/config           │
│          property: db_password       │
└─────────────┬───────────────────────┘
              │
              │ Creates/updates
              ↓
┌─────────────────────────────────────┐
│  Kubernetes Secret (myapp namespace) │
│  myapp-secrets:                      │
│    db_password: xxxxx (base64)       │
└─────────────┬───────────────────────┘
              │
              │ Mounted in Pod
              ↓
┌─────────────────────────────────────┐
│  Application Pod                     │
│  env:                                │
│    - name: DB_PASSWORD               │
│      valueFrom:                      │
│        secretKeyRef:                 │
│          name: myapp-secrets         │
│          key: db_password            │
└─────────────────────────────────────┘
```

## Component Interactions

```
┌──────────────┐
│    GitHub    │
│  Repository  │
└──────┬───────┘
       │
       │ SSH/HTTPS
       │
┌──────▼───────────────────────────────────────────────┐
│              Flux Source Controller                   │
│  - Watches GitHub for changes                        │
│  - Creates GitRepository resource                    │
└──────┬───────────────────────────────────────────────┘
       │
       ├──────────────────────────────────┐
       │                                  │
┌──────▼──────────┐           ┌──────────▼────────────┐
│   Kustomize     │           │    Terraform          │
│   Controller    │           │    Controller         │
│                 │           │                       │
│ Applies:        │           │ Runs:                 │
│ - Namespaces    │           │ - Vault config        │
│ - Deployments   │           │ - Cloud resources     │
│ - Services      │           │                       │
└──────┬──────────┘           └──────────┬────────────┘
       │                                 │
       │                                 │
       ▼                                 ▼
┌─────────────────┐           ┌──────────────────────┐
│  Helm           │           │  Infrastructure      │
│  Controller     │           │  (Vault, etc.)       │
│                 │           │                      │
│ Deploys:        │           │ - Auth backends      │
│ - Vault         │           │ - Secret paths       │
│ - ESO           │           │ - Policies           │
│ - Apps          │           │                      │
└─────────────────┘           └──────────────────────┘
```

## Drift Detection & Auto-Remediation

```
Desired State (Git)
        │
        │ Flux reconciles every interval
        │
        ↓
    ┌───────────────┐
    │ Git matches   │
    │   cluster?    │
    └───┬───────┬───┘
        │       │
    NO  │       │  YES
        │       │
        ↓       ↓
    ┌───────┐ ┌──────────┐
    │ Apply │ │ Do       │
    │ change│ │ nothing  │
    └───────┘ └──────────┘
```

### For Kubernetes Resources (via Flux)
- Interval: 1m (configurable)
- Auto-remediation: Enabled by default
- Example: If someone runs `kubectl delete pod`, Flux recreates it

### For Terraform Resources (via tf-controller)
- Interval: 10m (configurable)
- Auto-remediation: If `approvePlan: auto`
- Example: If someone manually changes Vault policy, Terraform reverts it

## Deployment Pipeline

### Application Deployment
```
1. Developer commits app manifest
        ↓
2. GitHub webhook (optional) or Flux polls
        ↓
3. Flux detects change
        ↓
4. Kustomize/Helm controller applies
        ↓
5. Kubernetes creates resources
        ↓
6. Application running
```

### Infrastructure Deployment
```
1. Developer commits Terraform code
        ↓
2. Flux detects change
        ↓
3. Terraform controller creates runner pod
        ↓
4. Runner pod executes terraform plan
        ↓
5. If approvePlan: auto, applies automatically
        ↓
6. Infrastructure configured
        ↓
7. Outputs stored in Secret
```

## Security Boundaries

```
┌─────────────────────────────────────────────────────┐
│  GitHub Repository (Public/Private)                  │
│  - No secrets stored                                 │
│  - Only references to secrets                        │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ Read-only access
                   ↓
┌─────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                  │
│                                                       │
│  ┌────────────────────────────────────────────────┐ │
│  │  flux-system namespace                         │ │
│  │  - Flux controllers (privileged)               │ │
│  │  - Terraform secrets (gitignored)              │ │
│  └────────────────────────────────────────────────┘ │
│                                                       │
│  ┌────────────────────────────────────────────────┐ │
│  │  vault namespace                               │ │
│  │  - Vault pod (stores encrypted secrets)       │ │
│  │  - PersistentVolume (encrypted data)          │ │
│  └────────────────────────────────────────────────┘ │
│                                                       │
│  ┌────────────────────────────────────────────────┐ │
│  │  App namespaces                                │ │
│  │  - Limited RBAC                                │ │
│  │  - Secrets from ESO (read-only from Vault)    │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Git | GitHub | Source of truth for all configs |
| GitOps | Flux | Continuous delivery and reconciliation |
| Container Orchestration | k3s | Lightweight Kubernetes |
| Helm | Flux Helm Controller | Package management |
| IaC | Terraform + tf-controller | Infrastructure as code |
| Secret Management | HashiCorp Vault | Centralized secret storage |
| Secret Sync | External Secrets Operator | Vault → K8s Secret sync |
| Networking | k3s default (Flannel) | Pod networking |
| Storage | Local Path Provisioner | Persistent volumes |

## Data Flow: Adding a New App

```
1. Create app manifests
   apps/base/myapp/
   ├── namespace.yaml
   ├── deployment.yaml
   └── kustomization.yaml

2. Commit to Git
   git add apps/base/myapp/
   git commit -m "Add myapp"
   git push

3. Flux syncs (within 1m)
   source-controller fetches new commit

4. Kustomize controller processes
   Builds manifests from kustomization

5. Resources created
   Namespace, Deployment, Service, etc.

6. If secrets needed:
   a. Store in Vault
   b. Create ExternalSecret
   c. ESO syncs to K8s Secret
   d. App mounts Secret

7. Application running!
```

## Monitoring Points

```
┌──────────────────────────────────────┐
│  flux get all -A                      │  ← Overall Flux status
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  kubectl get terraform -A             │  ← Terraform status
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  kubectl get externalsecrets -A       │  ← Secret sync status
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  kubectl get helmreleases -A          │  ← Helm deployment status
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  kubectl logs -n vault vault-0        │  ← Vault logs
└──────────────────────────────────────┘
```

## Failure Scenarios

### Scenario: Flux can't connect to Git
- **Symptom**: `flux get sources git` shows error
- **Impact**: No new deployments, but existing workloads continue
- **Resolution**: Fix network/credentials, Flux auto-recovers

### Scenario: Terraform fails to apply
- **Symptom**: `kubectl get terraform` shows failure
- **Impact**: Infrastructure not updated, but apps still work
- **Resolution**: Check logs, fix Terraform code, commit

### Scenario: Vault sealed
- **Symptom**: ExternalSecrets show errors
- **Impact**: New pods can't get secrets
- **Resolution**: Unseal Vault, ESO auto-syncs

### Scenario: Git repo unavailable
- **Symptom**: Source controller errors
- **Impact**: Cluster continues with last known state
- **Resolution**: Flux retries automatically when Git returns

## Scalability

Current setup optimized for:
- **Cluster size**: 3-10 Raspberry Pi nodes
- **App count**: 10-50 applications
- **Terraform resources**: 100-500 resources
- **Secrets**: 100-1000 secrets in Vault

For larger scale:
- Use remote Terraform backends
- Consider Vault HA mode
- Implement caching/CDN for Helm charts
- Use Flux sharding for multi-cluster

## Resources

- [Flux Architecture](https://fluxcd.io/docs/concepts/)
- [Terraform Controller Architecture](https://weaveworks.github.io/tf-controller/overview/)
- [Vault Architecture](https://www.vaultproject.io/docs/internals/architecture)
- [External Secrets Architecture](https://external-secrets.io/latest/introduction/overview/)
