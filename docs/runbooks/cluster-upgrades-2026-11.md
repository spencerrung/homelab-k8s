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
6. AI: guard the old LiteLLM schema first, then migrate LiteLLM, Open WebUI
   and SearXNG with database/config backups and checks
   of authentication, provider configuration and search.
7. Matrix: PostgreSQL already patched; Synapse, Element, Cinny and notifier
   runtime. Preserve signing identity, OIDC, federation and notification hooks.
8. Home Assistant and Homarr with persistent-data backups and migration review.
9. Gitea: restore the configured memory cache, database sessions and local
   queue first; chart defaults had silently enabled Valkey. Confirm queues are
   empty and retain Valkey PVCs, then upgrade Gitea and validate OIDC/repositories.
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

## Authentication, databases and Vault checkpoint

- PRs #46, #50, #60, #67 and #77: Authentik advanced through 2025.10.4,
  2025.12.6, 2026.2.7, 2026.5.8 and 2026.8.5. Final chart is 2026.8.5;
  all four replicas are ready. Login and OIDC discovery return HTTP 200, with
  HTTPS issuer/authorization endpoints. Application, provider and custom scope
  settings are retained. Reviewed upstream blueprint changes added an
  authenticator-validation policy, removed an obsolete initial-setup policy
  and tightened the initial-setup entrypoint check. Remaining policies match
  their baseline. Each migration was followed by a fresh database dump.
- PR #47 gives Authentik 15 minutes for image extraction on the Pi nodes.
  A stalled container lifecycle on pi-04 required restarting its k3s agent;
  the node was temporarily cordoned and is now uncordoned and Ready.
- PRs #48 and #49: Gitea and Matrix PostgreSQL patched to 15.20. SQL version,
  SELECT 1 and application HTTP checks passed. AI/media PostgreSQL already
  report 16.16. Database upgrades remain on supported existing major versions.
- PRs #51, #78 and #79: Vault advanced 2.0.3 → 2.0.4 → 2.1.2 → 2.2.2.
  Restarted the OnDelete StatefulSet deliberately, manually unsealed through
  the local API, and verified Raft status and External Secrets after each step.
  Snapshot upload, readback and archive checks passed before every step and
  again on 2.2.2. Final verified object: `vault-20261116-021452.snap`.
- Nightly backup `velero-nightly-stateful-20261116020037` completed successfully
  with 1,052 Kubernetes items during the maintenance window.

## Reviewed migration preparations

- Custom Kyverno policies must migrate to CEL ValidatingPolicy before Kyverno
  1.20, which no longer executes legacy ClusterPolicy. 41 regression cases
  passed, including all seven original controller kinds, namespace exceptions and
  existing audit behavior. PR #85 uses explicit controller matches because
  legacy ReplicationController is not covered by CEL auto-generation.
- Isolated migrations of current Homarr and Open WebUI databases passed health,
  integrity and retained-record checks. Homarr's four custom widgets remain.
- LiteLLM's official migration command passed against a strict database restore.
  Disable the old proxy's schema updater first, then use Recreate plus a target
  image migration init container; keep schema changes disabled in the server.
- Radarr 7.0.3 was released during this maintenance window (November 16 01:40 UTC).
  Its ARM64 image is available. An isolated PostgreSQL migration with the live
  512 MiB limit retained 149 movies, 144 file records, nine quality profiles,
  five custom formats and settings. Kometa metadata is disabled; the new Irish
  language selector is UI metadata and selected rule values are unchanged.
  PR #82 is queued with fresh backups and a guard test that intercepts writes.
- First-party image policies are current. Aimtrix's deliberate rc.8 digest pin
  corresponds to its latest built release; preserve it. BusyBox 1.36.1 remains
  the latest stable branch, so do not substitute unstable 1.37/1.38 tags.

## Node maintenance preparation

Apply supported Debian 12 package/kernel updates only after service upgrades
and recovery backups are complete. Upgrade one node at a time, control plane
last, retaining old kernels. Cordon, install packages with existing configuration
preserved, drain workloads, reboot, uncordon and verify cluster/service health.
Vault's single-instance disruption budget is intentional: on pi-03, drain other
pods, stop Vault deliberately after its snapshot, then unseal after reboot.

pi-04 boots from `10.10.10.231:/srv/nfs/raspios-pi`, serial `c56a6028`.
Its TFTP boot set must match the upgraded NFS-root kernel before rebooting.
The merged rpi-netboot PRs #2 and #3 add a validated staging helper, retain the
previous boot directory and ensure files remain readable by TFTP. Do not run
initial provisioning to perform an OS upgrade. Node root and boot/configuration
archives are being uploaded with server-side encryption to the existing B2
backup bucket; full readback checksums and gzip validation gate each backup.
K3s/PVC runtime directories are excluded from OS archives and covered by
cluster/database backups. Take a fresh consistent control-plane SQLite/token/
TLS backup immediately before upgrading pi-01.


## Storage incident and recovery checkpoint (November 16, 02:50 UTC)

During OS archive reads, `raspberrypi-51249e4e` (`10.10.10.29`) reported MMC
read failures, failed writes and EXT4 buffer I/O errors, then stopped responding
to kubelet and SSH. Its root archive failed validation; do not treat that object
as a complete OS backup. All eight other nodes have verified root and boot/etc
archives with full B2 readback checksums and gzip validation.

The affected node remains cordoned, tainted
`homelab.alucard.dev/storage-failed=true:NoSchedule`, and labelled
`homelab.alucard.dev/quarantined=true`. Its OS update is excluded pending physical
storage/power diagnosis and repair. Do not uncordon it or remove the quarantine
label merely because it becomes reachable. Preserve its original local volumes
and previously quarantined containerd directory for investigation.

PRs #86 and #88 move two affected services onto retained, explicitly bound local
volumes on pi-02. The same-night Velero backup restored successfully into isolated
`ai-sd-recovery` and `newhope-sd-recovery` namespaces before cutover:

- AI PostgreSQL recovery point: 02:01:47 UTC. PostgreSQL started successfully,
  exported a complete logical dump, then stopped cleanly before copying its
  recovered directory. The live service has 74 public tables and authenticated
  LiteLLM model discovery returns the expected aliases.
- New Hope engagement recovery point: 02:11:42 UTC. The JSON file parsed and the
  public stats API matches its restored counts.
- Changes after those recovery points cannot be verified while the original
  node is unavailable. Original PVCs, isolated recovery copies and off-cluster
  backups remain intact. The copied directories compared byte-for-byte before
  either application started.
- The PostgreSQL StatefulSet was recreated with orphan propagation to remove
  its immutable legacy claim template. Merely changing its container mount
  would still inject the old template-generated volume and bind scheduling to
  the failed node. No original PVC or PV was deleted.

PR #87 excludes quarantined nodes from broadly tolerated CSI and node-exporter
DaemonSets. The other DaemonSets respect the quarantine taint. Monitoring keeps
reporting the failed node; rollout checks identify its three kubelet targets as
known failures and require all remaining targets to be healthy.

PR #89 manages the Git source and uses GitHub SSH on port 443 after repeated
port 22 timeouts. The new host alias was verified against an existing trusted
GitHub host key; the deploy private key did not change. Source reconciliation
succeeded through the new endpoint.

The eight healthy nodes remain the OS upgrade scope. pi-04 is temporarily
cordoned during application rollouts and must be uncordoned before node updates.
No node OS package upgrades had begun at this checkpoint.


## LiteLLM deployment-strategy transition

PR #63 changes LiteLLM to Recreate before database migrations. The live
Deployment had defaulted `rollingUpdate` fields retained under server-side
apply, so the API rejected the strategy change. A declarative null alone did
not remove those existing fields. After a server dry-run, a one-time merge
patch replaced only the strategy with `type: Recreate` and
`rollingUpdate: null`; it did not modify the Pod template. The full proposed
manifest then passed Flux-style server-side dry-run. PR #92 makes the intended
absence of rolling-update settings explicit. Allow the schema guard to finish
rolling out and pass its checks before merging the actual image/migration bump.
