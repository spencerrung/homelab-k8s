# Bootstrap: bare k3s → healthy cluster

For full disaster recovery (restoring data) see
[disaster-recovery.md](disaster-recovery.md). This runbook is the
fresh-install path.

## 0. Prerequisites

- k3s installed via the ansible repo (separate repository)
- `kubectl` context pointing at the cluster
- GitHub PAT with repo access
- Break-glass credentials in the password manager (Vault unseal key +
  root token only exist after step 2 on a truly fresh install)

## 1. Flux

```bash
export GITHUB_TOKEN=<PAT>
./bootstrap/flux-bootstrap.sh
```

Flux installs itself and reconciles the tier graph (see
[architecture](../architecture.md#flux-reconciliation-graph)):
`sources → infra-controllers → infra-configs → platform-apps / apps-* /
monitoring`.

Expected intermediate state: everything that needs a secret (cert-manager
issuers, authentik, gitea, matrix, pds, grafana, velero) is **degraded
until Vault is initialized** in step 2. That is normal.

## 2. Vault

```bash
./bootstrap/vault-init.sh
```

First run initializes (1 unseal key share), unseals, enables KV v2 +
kubernetes auth, writes policies/roles. **Store the printed unseal key and
root token in the password manager immediately — they are shown once.**

Re-runs (e.g. after a vault pod restart, which leaves Vault sealed):

```bash
VAULT_UNSEAL_KEY=... ./bootstrap/vault-init.sh                       # unseal only
VAULT_UNSEAL_KEY=... VAULT_ROOT_TOKEN=... ./bootstrap/vault-init.sh  # re-apply config
```

## 3. Seed secrets

Fresh install (no backup to restore): populate the KV paths that
ExternalSecrets reference — `kubectl get externalsecrets -A` shows every
consumer and `remoteRef`. Core paths:

```
secret/cert-manager/cloudflare     api-token
secret/authentik/{postgresql,secret-key,terraform-token}
secret/gitea/{postgresql,admin-token,webhook-secret}   secret/gitea-oidc
secret/matrix/{postgresql,synapse,signing-key}
secret/atproto/pds
secret/backup/{velero-b2,vault-b2}
secret/monitoring/{grafana,matrix}
```

Rebuild with existing data: **do not seed** — restore the raft snapshot
per [disaster-recovery.md](disaster-recovery.md).

## 4. Verify

```bash
flux get kustomizations          # all Ready
kubectl get externalsecrets -A   # all SecretSynced
kubectl get certificate -A       # all Ready
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded
```

External dependencies to remember (outside this repo): Cloudflare DNS
records per hostname, external reverse-proxy routes to the Traefik
NodePorts, Renovate GitHub App installed on the repo.
