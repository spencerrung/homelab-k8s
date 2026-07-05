# Disaster Recovery

From bare metal to healthy cluster. Assumes total loss of the cluster but
not of the break-glass credentials.

## Break-glass list (password manager, kept current)

| Credential | Used for |
|---|---|
| GitHub PAT | `flux bootstrap github` |
| Vault unseal key + root token | unseal + re-configure Vault |
| B2 app key `velero` (alucard-velero bucket) | Velero restores |
| B2 app key `vault-snapshots` (alucard-vault-snapshots bucket) | fetching raft snapshots |
| Cloudflare API token | seeded into Vault for cert-manager DNS-01 |
| Docker Hub credentials | Tekton image pushes (Phase 5+) |

## What is backed up where

| Data | Mechanism | Destination | Schedule / retention |
|---|---|---|---|
| Vault (all secrets) | raft snapshot CronJob (`infrastructure/base/vault/snapshot-cronjob.yaml`) | `b2://alucard-vault-snapshots/` | 01:30 UTC nightly / 30 days (B2 lifecycle) |
| matrix, atproto, gitea, authentik namespaces incl. PVCs | Velero `nightly-stateful` (kopia file-level) | `b2://alucard-velero/` | 02:00 UTC nightly / 14 days |
| whole cluster (minus kube-system, flux-system, velero) | Velero `weekly-full` | `b2://alucard-velero/` | Sun 03:00 UTC / 60 days |
| everything else (manifests) | git | GitHub `spencerrung/homelab-k8s` | — |

Consistency notes:
- Postgres (matrix, gitea, authentik): a `pg_dumpall` pre-hook writes
  `/var/lib/postgresql/data/velero-dump.sql` inside the volume before the
  file copy. On restore, prefer the dump if the copied datadir is unclean.
- atproto PDS: sqlite is copied live at 02:00 (image has no sqlite3 for a
  `.backup` hook). WAL sqlite copies are normally recoverable; blobs are
  plain files. Low traffic window mitigates.
- Matrix signing key also lives in Vault at `secret/matrix/signing-key`
  (belt and braces - it's the federation identity).

## Recovery procedure

1. **k3s**: reinstall via the ansible repo (separate repository).
2. **Flux**: `bootstrap/flux-bootstrap.sh` (needs GitHub PAT). Flux
   reconciles everything in git. Stateless apps go healthy; anything
   needing secrets stays degraded until step 4. Expected.
3. **Vault restore** (do NOT run the init path of vault-init.sh for DR):
   ```bash
   # vault pod is up but uninitialized. Init with a THROWAWAY key first:
   kubectl exec -n vault vault-0 -- vault operator init -key-shares=1 -key-threshold=1
   kubectl exec -n vault vault-0 -- vault operator unseal <throwaway-unseal-key>

   # fetch the latest snapshot (break-glass B2 vault-snapshots key)
   rclone copyto :s3:alucard-vault-snapshots/<latest>.snap /tmp/vault.snap \
     --s3-provider Other --s3-endpoint https://s3.us-west-004.backblazeb2.com --s3-env-auth
   kubectl cp /tmp/vault.snap vault/vault-0:/tmp/vault.snap
   kubectl exec -n vault vault-0 -- env VAULT_TOKEN=<throwaway-root-token> \
     vault operator raft snapshot restore -force /tmp/vault.snap

   # after restore the ORIGINAL unseal key + root token apply
   kubectl exec -n vault vault-0 -- vault operator unseal <original-unseal-key>
   ```
4. **Re-point kubernetes auth** (cluster CA/JWTs changed with the rebuild):
   re-run the configuration half of `bootstrap/vault-init.sh` with the
   original credentials:
   ```bash
   VAULT_UNSEAL_KEY=<original> VAULT_ROOT_TOKEN=<original> ./bootstrap/vault-init.sh
   ```
5. **ESO reconnects** → secrets render → cert-manager gets the Cloudflare
   token → certificates reissue. Verify: `kubectl get externalsecrets -A`.
6. **Velero data restore** (create the credentials secret manually if ESO
   isn't ahead of you - it should be):
   ```bash
   velero restore create --from-backup <latest nightly-stateful> \
     --include-namespaces matrix,atproto,gitea,authentik
   ```
   For any postgres that comes up unclean: drop the datadir contents,
   start postgres fresh, `psql -U $POSTGRES_USER -f /var/lib/postgresql/data/velero-dump.sql`.
7. **External dependencies** (outside this repo): Cloudflare DNS records,
   external reverse-proxy routes to the cluster NodePorts.

## Verification checklist

- [ ] `flux get all -A` fully green
- [ ] `kubectl get externalsecrets -A` all SecretSynced
- [ ] Matrix: login + federation test (https://federationtester.matrix.org)
- [ ] PDS: `curl https://pds.alucard.dev/xrpc/_health`
- [ ] Gitea: clone a repo, OIDC login via Authentik
- [ ] Grafana/monitoring green (Phase 3+)
- [ ] certificates: `kubectl get certificate -A` all Ready

## Routine operations

- **Vault pod restarted / sealed**: `VAULT_UNSEAL_KEY=... ./bootstrap/vault-init.sh`
  (unseal-only takes seconds; apps keep running on rendered k8s Secrets
  meanwhile).
- **Restore test**: quarterly, restore the latest `nightly-stateful` into a
  scratch namespace and check data (see below). A backup that has never
  been restored does not exist.
  ```bash
  velero restore create --from-backup <backup> \
    --include-namespaces matrix --namespace-mappings matrix:restore-test
  # verify, then: kubectl delete ns restore-test
  ```
