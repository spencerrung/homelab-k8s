# November 2026 cluster upgrade plan

Authorized scope: upgrade the deployed homelab services, preserve custom behavior,
merge reviewed PRs and verify each rollout. K3s 1.37.2+k3s1 and Flux 2.10.0
are already complete. All targets must be checked against official releases,
ARM64 images and supported upgrade paths before deployment.

## Completion status (November 16, 07:55 UTC)

Application upgrades and all eight serviceable node OS upgrades are complete.
Every serviceable node runs K3s 1.37.2+k3s1 and kernel
6.12.115+rpt-rpi-v8; Flux remains 2.10.0. Each node passed package auditing,
reported no remaining upgrades from its configured repositories, and retained
its EEPROM configuration and disabled automatic-flashing policy. Debian 12 and
the existing supported PostgreSQL major versions were retained with current
available patches; this maintenance did not perform distribution or database
major-version migrations.

The sole unfinished hardware item is raspberrypi-51249e4e (10.10.10.29), whose
root SD storage failed during backup reads. It remains quarantined pending
physical diagnosis/repair. Its two affected services were recovered on pi-02;
see the recovery points and possible data gap below. Do not interpret the
healthy-node checks as a nine-node all-clear.

Final checks passed: 76 workloads, 69 Flux resources, 27 certificates,
26 ExternalSecrets, one ClusterSecretStore and three CEL policies. Eight public
service endpoints and in-cluster DNS passed after each node. Monitoring retained
all 29 baseline Grafana dashboards, 27 rule groups and the Matrix alert route;
53 healthy targets passed, with only the failed node's three targets excluded.
Loki was ready and returned log labels. The completed post-service Velero backup
and isolated notifier restore are recorded below.

The reviewed changes are in homelab-k8s PRs #43–#96 and rpi-netboot PRs #2–#5,
plus this completion record. Detailed private evidence and backups are retained
under `~/homelab-backups/services-20261115`; no credentials or private records
are committed here.

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
  recovered directory. At this recovery checkpoint, the service had 74 public
  tables; authenticated LiteLLM model discovery returned the expected aliases.
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


## Service upgrade results (November 16 UTC)

- Storage/ingress/security controllers: NFS CSI 4.13.6, Traefik 3.7.19
  (chart 42.4.0), cert-manager 1.21.3, External Secrets 2.15 and Kyverno
  1.20 (chart 3.10). Certificates, external secrets and all three migrated
  CEL policies pass readiness. Policy regression checks cover 41 cases.
- Monitoring: kube-prometheus-stack 93.3.0, Grafana 13.3.1, Loki 3.7.10
  (chart 21.2.3), Alloy 1.22.0 (chart 1.16), Matrix receiver 2026.9.23.
  All 29 baseline dashboard UIDs remain, alert routing is preserved, and
  fresh Loki ingestion passed. The failed node's three kubelet targets are
  explicitly excluded from the healthy-target gate, not silently reported up.
- AI: LiteLLM 1.109.1 applied 98 official migrations after disabling the old
  schema updater; authenticated model aliases passed. Open WebUI 0.13.3
  passed SQLite integrity and retained-record checks. SearXNG
  2026.11.15-2d500cb6b returned 42 results in its JSON search test.
- Matrix: Synapse 1.165, Element 1.12.35 and Cinny 4.12.8. Signing identity
  is unchanged; client/federation APIs, clients and well-known routing passed.
- Home Assistant 2026.11.1 passed its live configuration check. Homarr 2.13.1
  retained dashboard records, exact integration configuration/credentials and
  saved custom-widget definitions. The four legacy definitions are disabled
  examples, with no customApi widgets placed; no data rewrite was needed.
- Gitea 28.4.0/chart 12.7 uses Recreate rollouts, memory cache, database
  sessions and the intended local level queue. Repository count and OIDC
  redirects passed. Unlimited Actions run history is retained. Valkey queues
  were empty before removal and their PVCs remain intact.
- Tekton Pipelines 1.18, Triggers 0.38 and Dashboard 0.74 each passed a
  nonpublishing generate-tag TaskRun. The generated Gitea EventListener image
  and readiness were checked after controller reconciliation; waiting only
  for the pre-existing Deployment rollout was insufficient during transition.
- PDS 0.4.5051 is pinned by digest. All four SQLite backups passed integrity
  checks, and repository identities were retained after deployment.

### pi-04 container-runtime recovery

Radarr startup exposed an NFS-backed containerd garbage-collection stall.
A goroutine dump showed snapshot deletion holding the metadata write lock while
new container creation waited for it. The active deletion traversed obsolete
Home Assistant layer `89470`; no process mount table referenced that snapshot.
An initial agent restart did not resolve the underlying cleanup load. With the
agent stopped, the already-discarded layer was renamed on the same filesystem
into `/var/lib/rancher/k3s/agent/gc-quarantine-20261116/89470`, then the agent
was started again. Preserve that cache for controlled offline cleanup; do not
recursively delete it during active service maintenance. Application PVCs and
running container layers were untouched. Runtime diagnostic stacks are retained
with the private maintenance evidence.

### Final application gates

- rclone 1.76.0 successfully uploaded a fresh Vault snapshot, downloaded it
  from B2 and validated the archive: `vault-20261116-035928.snap`.
- Radarr 7.0.3 passed exact settings comparisons (apart from the reviewed new
  language-selector metadata), media-root accessibility and application health.
  The anime guard passed before and after with all non-GET/HEAD requests
  intercepted and Matrix credentials replaced in the temporary test jobs.
  Both tests attempted zero writes. The post-upgrade test was rescheduled on
  pi-02 after pi-04's obsolete-image cleanup delayed its image pull; production
  CronJob scheduling was unchanged.
- At the application checkpoint, all eight nonquarantined nodes and services,
  75 workloads, 69 Flux resources, 27 certificates, 26 ExternalSecrets, the
  ClusterSecretStore and three CEL policies passed the full health audit.

### Verified post-service backup and notifier recovery

The first post-upgrade backup reproduced a race with the one-minute Bluesky
notifier: its Pod disappeared before Velero could expose its persistent volume.
All other selected volumes completed. PR #95 adds a credential-free helper with
a read-only state mount and a fail-closed SQLite online-backup pre-hook; the
transient notifier excludes its data mount from filesystem backup. All 15
fixture tests and the server-side dry-run passed, followed by a live hook check.

Replacement `post-services-upgrade-verified-20261116` completed with 1,079 items,
13 filesystem volume backups and zero errors. Restore
`bsky-sqlite-verify-20261116` recovered only the helper's snapshot volume into an
isolated namespace, removing source/code mounts and the source-dependent probe.
The restored SQLite file matched the source snapshot byte-for-byte and passed
integrity checking. No notifier ran in isolation. The temporary namespace was
removed after verification. The complete application health audit then passed
with 76 workloads, including the new helper.

### Node maintenance execution details

Run the package transaction in a transient systemd unit with `--no-block` and
poll its status over SSH. Waiting for the unit's start transaction can disconnect
when the systemd package restarts D-Bus, even while apt continues successfully.
Resume monitoring the existing unit rather than starting a second transaction.

The conservative `apt-get --with-new-pkgs upgrade` left `rpi-eeprom` behind on
the canary. After the base transaction, `apt-get --no-remove install
--only-upgrade rpi-eeprom` completed without removals. All eight nodes had the
EEPROM update service deliberately disabled. Capture bootloader configuration
and version first, runtime-mask that service during package installation, then
restore its disabled state and verify the saved configuration. This updates the
package without overriding the existing automatic-flashing policy or changing
network boot order. Retain old kernels and do not autoremove recovery caches.

During drains of other nodes, briefly cordon pi-04 as well to avoid repeatedly
extracting evacuated workloads' images onto its slower NFS root. Uncordon the
rebooted node and pi-04 before the full health gate. After the pi-02 reboot,
Kyverno recovered before several workload controllers' admission-error backoff
expired. Metadata-only retry annotations on the affected StatefulSets and
ReplicaSets prompted creation without changing their Pod templates or data.

PR #96 adds an explicit SIGTERM handler to the backup helper's PID 1 command.
Its first node drain otherwise waited for the entire shutdown grace period.
The exact command passed a local signal/exit-code check and server-side dry-run.
The SQLite backup hook and read-only source mount are unchanged.


### SD boot configuration correction

Netboot PR #4 adds `scripts/update-local-boot-initramfs.py` for the existing SD
installations. Their explicit `initramfs initrd.img followkernel` directive still
selected the copied 6.6.31 archive after apt installed a newer `kernel8.img` and
package-managed `initramfs8`. The helper verifies the kernel checksum, matching
root modules and initramfs module version before selecting `initramfs8`. It saves
the prior configuration/archive and retains the old `initrd.img` and kernels.
Three fixture tests and a live canary dry-run passed before deployment. All seven
reachable SD installations passed apply and repeat verification; the two nodes
still awaiting their OS transaction were first aligned to their current kernel.
The package transaction is followed by another matching-version check before
reboot. The separate TFTP helper handles pi-04's NFS boot files.

raspberrypi-e2c042ff took approximately ten minutes to return after reboot. The
previous shutdown log ends after enabling a ten-minute hardware watchdog; actual
startup took 33 seconds. A shutdown delay is consistent with that evidence, but
the exact blocking process was not identified. The node returned without console
intervention on 6.12.115, and database/application readiness, endpoint checks,
package state and the full cluster audit passed. The stale initramfs was a
separate configuration defect; it was not established as the cause of the delay.


pi-04's first kernel package configuration failed because provisioning mounted
`/var/tmp` as a 30 MB tmpfs. `mkinitramfs` exhausted that mount while expanding
modules despite 19 GB free on the NFS root. Netboot PR #5 configures a root-only
persistent build directory through initramfs-tools `conf.d/TMPDIR`, preserving
the existing temporary mount limits. Ansible syntax and a targeted live check
passed before applying only those three configuration tasks. The original apt
transaction was allowed to finish before retrying package configuration.

The repaired kernel packages configured successfully and `dpkg --audit` was
empty. The NFS boot gate must accept built-in kernel support: 6.12.115 has
`CONFIG_NFS_FS`, `CONFIG_NFS_V3`, `CONFIG_ROOT_NFS`, `CONFIG_BCMGENET`,
`CONFIG_IP_PNP` and `CONFIG_IP_PNP_DHCP` enabled as `y`. Requiring corresponding
`.ko` files in the initramfs incorrectly rejected this valid kernel. Verify
those built-ins or the relevant archive modules, plus `scripts/nfs` and
`nfsmount`, before staging the matched TFTP files.


### Final node results

Nodes completed sequentially in this order: raspberrypi-f3bf5023, pi-02,
pi-05, raspberrypi-d868c445, raspberrypi-e2c042ff, pi-04, pi-03 and pi-01.
Each returned on 6.12.115+rpt-rpi-v8 and passed the full cluster and endpoint
gates before proceeding. pi-04 retained its NFS root and successfully booted
from the matched TFTP set. pi-03's fresh Vault snapshot passed B2 readback;
Vault was unsealed after reboot and all ExternalSecrets refreshed successfully.
A fresh consistent SQLite/token/TLS/credential archive preceded pi-01's update.
Its API returned ready after reboot. Authentik's servers restarted during the
control-plane outage, completed startup and both became ready before completion.

All eight nodes are uncordoned. The failed ninth node stays cordoned and tainted;
its old volumes and recovery copies remain preserved. Retain the documented
containerd quarantine directories for controlled offline cleanup. No original
application PVCs were deleted to complete the upgrades.
