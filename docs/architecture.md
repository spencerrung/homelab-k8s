# Architecture

GitOps layer for a 9-node Raspberry Pi 4B k3s cluster (6×8GB, 1×4GB,
2×2GB, arm64). A separate ansible repo installs the OS and k3s; everything
after that reconciles from this repo via Flux.

## Traffic

```mermaid
flowchart LR
    subgraph internet [Internet]
        U[Client]
        CF[Cloudflare DNS<br/>alucard.dev]
    end
    subgraph edge [Edge]
        XP[External reverse proxy]
    end
    subgraph cluster [k3s - 9x Raspberry Pi 4B arm64]
        TR[Traefik v3<br/>NodePort 80/443]
        CM[cert-manager<br/>DNS-01 via Cloudflare]
        subgraph platform [Platform]
            AK[Authentik OIDC]
            GT[Gitea + registry]
            TK[Tekton CI]
        end
        subgraph obs [Monitoring]
            PR[Prometheus + Grafana]
            LK[Loki + Alloy]
            AM[Alertmanager]
        end
        subgraph apps [Apps]
            MX[Matrix<br/>Synapse + Element + Cinny]
            PDS[Bluesky PDS]
            WEB[Static sites x5]
        end
    end
    U -->|HTTPS| XP
    CF -.->|DNS| U
    XP -->|NodePort| TR
    TR --> AK & GT & MX & PDS & WEB & PR
    CM -.->|DNS-01 API| CF
    CM -.->|TLS secrets| TR
    AM -.->|webhooks| MX
```

- Traefik is deliberately **NodePort**, not LoadBalancer: bare metal, no
  MetalLB; an external reverse proxy fronts the cluster and Cloudflare
  fronts public hostnames.
- Certificates are DNS-01 (Cloudflare API token via Vault/ESO), so no
  inbound HTTP challenge path is needed.

## Flux reconciliation graph

```mermaid
flowchart TD
    GR[GitRepository flux-system<br/>github.com/spencerrung/homelab-k8s]
    GR --> FS[flux-system<br/>clusters/homelab]
    FS --> SRC[sources<br/>HelmRepositories]
    SRC --> IC["infra-controllers<br/>cert-manager, traefik, ESO,<br/>vault, velero"]
    IC --> CFG["infra-configs<br/>cluster issuers, flux-alerts"]
    IC --> MON["monitoring<br/>kube-prometheus-stack,<br/>loki, alloy, matrix receiver"]
    MON --> MONC["monitoring-configs<br/>PodMonitors, dashboards"]
    CFG --> PLAT["platform-apps<br/>authentik, gitea, tekton"]
    CFG --> AW["apps-web<br/>5 static sites"]
    CFG --> AS["apps-stateful<br/>matrix, atproto-pds"]
```

Rules of the graph:

- **Update this diagram in the same PR as any new `clusters/homelab/*.yaml`.**
- `infra-controllers` and `platform-apps` use `wait: false` + explicit
  HelmRelease `healthChecks`, so one slow chart doesn't block the tier.
- CRD *instances* must not share a Kustomization with the HelmRelease that
  installs their CRDs (Flux dry-runs everything before applying) — that's
  why `monitoring-configs` exists.
- Reconciliation failures alert to the Matrix **Homelab Alerts** room
  (`infrastructure/base/flux-alerts/`). The Alert lists HelmReleases per
  namespace — add an entry when a new namespace gains one.

## Secrets

```mermaid
sequenceDiagram
    participant V as Vault (raft, ns vault)
    participant CS as ClusterSecretStore vault-backend
    participant ES as ExternalSecret (per app)
    participant S as k8s Secret
    participant P as Pod
    Note over V: KV v2 at secret/<br/>k8s auth, role external-secrets
    CS->>V: authenticate (SA external-secrets/external-secrets-sa)
    ES->>CS: remoteRef secret/<app>/<key>
    CS->>ES: values
    ES->>S: render (data or template)
    P->>S: env / volume
```

- Vault runs **production mode, single-node raft** on a local-path PVC
  pinned to `pi-03`. A pod restart leaves it **sealed**: workloads keep
  running on rendered k8s Secrets, ESO refreshes resume after
  `VAULT_UNSEAL_KEY=... bootstrap/vault-init.sh`.
- One ClusterSecretStore serves every namespace; the Vault k8s-auth role
  binds only `external-secrets/external-secrets-sa`.
- Nothing secret lives in git. Blueprints/configs that embed secrets are
  rendered by ExternalSecret templates or `${ENV}` expansion.

## Storage & backup

| Data | Where | Protected by |
|---|---|---|
| Vault (all secrets) | raft PVC on pi-03 | nightly raft snapshot → B2 (30d) |
| Matrix postgres + synapse media/signing key | local-path PVCs | Velero nightly (14d) + pg_dump hook; signing key also in Vault |
| Bluesky PDS sqlite + blobs | local-path PVC | Velero nightly (14d) |
| Gitea repos + postgres, Authentik postgres | local-path PVCs | Velero nightly (14d) + pg_dump hooks |
| Everything declarative | git | GitHub |

local-path storage is node-local: stateful pods are effectively pinned to
the node holding their data. Recovery: [runbooks/disaster-recovery.md](runbooks/disaster-recovery.md).

## Monitoring

kube-prometheus-stack (trimmed for k3s — no scheduler/controller-manager/
kube-proxy/etcd scrapes), Loki single-binary + Alloy DaemonSet for logs,
Grafana at `grafana.alucard.dev`. Alertmanager and Flux both notify the
Matrix **Homelab Alerts** room via the `@alertmanager` bot. See
[runbooks/monitoring.md](runbooks/monitoring.md).

## CI

Tekton builds app images in-cluster (kaniko) on Gitea pushes. Image
promotion into deployments is being moved to Flux image automation
(sortable tags → Docker Hub → ImagePolicy commits back to this repo).
