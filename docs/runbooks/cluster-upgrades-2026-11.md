# November 2026 cluster upgrade plan

Authorized scope: upgrade the deployed homelab services, preserve custom behavior,
merge reviewed PRs and verify each rollout. K3s 1.37.2+k3s1 and Flux 2.10.0
are already complete. All targets must be checked against official releases,
ARM64 images and supported upgrade paths before deployment.

## Execution order

1. Backup baseline: diagnose partial Velero backups, take replacement backups,
   verify database dumps and restore a representative backup into isolation.
   Upgrade Velero and its compatible AWS plugin; preserve B2 checksum settings,
   kopia filesystem backups, exclusions, schedules and retention.
2. PostgreSQL 15 patch updates, then Authentik through supported intermediate
   versions. Preserve OIDC providers, application mappings and database tuning.
3. Vault through supported intermediate versions with verified Raft snapshots
   and a working unseal procedure; verify External Secrets after each restart.
4. NFS CSI, Traefik, cert-manager, External Secrets and Kyverno, one controller
   at a time. Preserve ingress, DNS rewrites, resolvers, policies and storage.
5. Monitoring: kube-prometheus-stack, Loki, Alloy and Matrix alert receiver.
   Preserve rules, dashboards, retention and notifications; account for CRDs.
6. AI: Open WebUI, LiteLLM and SearXNG with database/config backups and checks
   of authentication, provider configuration and search.
7. Matrix: PostgreSQL already patched; Synapse, Element, Cinny and notifier
   runtime. Preserve signing identity, OIDC, federation and notification hooks.
8. Home Assistant and Homarr with persistent-data backups and migration review.
9. Gitea and its Valkey dependency with separate datastore migration review;
   validate repository access and authentication.
10. Tekton Pipelines, Triggers and Dashboard using supported sequential paths;
    preserve RBAC, event listener, build pipelines and ARM64 behavior.
11. Remaining helpers, floating-image deployments and first-party image status;
    verify the recently upgraded media suite remains current. Audit node OS
    updates separately and apply supported updates one node at a time only
    after application upgrades are stable.

## Gates for every batch

- Start from current main in an isolated worktree; preserve existing user work.
- Read upstream migration/release notes and relevant local runbooks.
- Render affected Kustomizations/Helm charts, inspect changes and use server
  dry-run when applicable. Confirm ARM64 image availability.
- Back up persistent data before migrations; never assume image rollback can
  reverse a database migration. Retain off-cluster recovery artifacts privately.
- Review and merge the PR, reconcile the relevant Flux tier, and wait for
  readiness. Verify service-specific behavior and custom integrations.
- Stop dependent upgrades on failure, investigate and repair before continuing.
- Record actual versions, PRs, checks and any remaining blockers here.

## Baseline

9 nodes Ready; 76 workloads ready; 69 Flux resources ready; 27 certificates ready.
November 15 scheduled nightly and weekly backups each report one error and
PartiallyFailed. The separate post-cycle Authentik backup completed. Investigate
before the next stateful change. Recovery caches quarantined during the K3s
upgrade remain intentionally retained on pi-03 and raspberrypi-51249e4e.

## Completed checkpoints

- PR #43: upgrade plan merged.
- Backup recovery: November 15 failures traced to the Authentik dump hook's
  exhausted lock table before the earlier recovery fix. Replacement backup
  `pre-services-upgrade-20261115` completed with 851 items and no errors.
- All five PostgreSQL dumps saved off-cluster. Authentik's dump was restored
  into isolated PostgreSQL 15.20 with `ON_ERROR_STOP=1`, matching application
  and provider counts. Verify transfer checksums: kubectl exec stdin transfers
  truncated during testing; the successful restore used a verified SSH copy.
- PR #44: Velero 1.18.4, chart 12.2.5, AWS plugin 1.14.4 deployed; server and
  all eight worker node agents ready. Post-upgrade New Hope filesystem backup
  completed without errors; B2 storage available.
- PR #45: Authentik PostgreSQL 15.20 deployed. SQL readiness and SELECT 1
  passed; max_locks_per_transaction remains 256. Login/OIDC HTTP checks passed.
- Vault snapshot `vault-20261116-003832.snap` uploaded to B2, downloaded
  off-cluster and verified as a readable archive.
