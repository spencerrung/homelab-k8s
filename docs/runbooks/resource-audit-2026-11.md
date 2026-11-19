# Homelab resource and alert audit — November 19, 2026

Status: IaC proposal for PR review, **not deployed**. Baseline: main `a94dfae`.
Only homelab-k8s is changed. No live resources, Jobs, alerts, or Matrix messages
were modified during the audit. Publishing this proposal for review does not
authorize merging, reconciliation, or rollout.

## Evidence and scope

Read 1,242 alert-bot messages from the preceding seven days (13 Matrix history
pages), current Prometheus alerts, Kubernetes workload state/events, CronJob
success timestamps, and recent backup status. Credentials were held in memory
for authenticated read-only Matrix requests and were not saved or printed.

All nine nodes report Ready, but only eight are serviceable. The quarantined
`raspberrypi-51249e4e` remains cordoned with failed SD storage; do not uncordon it.
Node CPU snapshot: 1–14%; memory: 33–63%. All Flux Kustomizations were Ready at
inspection. The last three scheduled nightly Velero backups completed.

Memory figures below are the maximum container working set over 24 hours;
CPU is p95 of five-minute rates sampled every five minutes over 24 hours.
Seven-day peaks were also checked for upgrade/startup effects. These are
observations, not guarantees for future peaks. A memory request reserves
scheduler capacity; exceeding it alone is not an OOM or throttling event.
No results were returned by the seven-day container OOM-event increase query;
this does not establish complete OOM coverage or recover lost container history.

## Recurring notifications

| Finding | Evidence | Proposed action |
| --- | --- | --- |
| Retained failed CronJobs | Nine failures: three bsky-notifier, two anime-guard, two qbittorrent-watchdog, two vault-snapshot. Failures date to Nov 1, 6, 15–16; all four CronJobs succeeded Nov 19. Retained notifier logs show URLError, anime-guard connection timeout; watchdog and Vault Jobs hit deadlines. Some old pod logs are unavailable. | Replace default KubeJobFailed with a recovery-aware rule for these named serial CronJobs plus recyclarr. Preserve failed objects and alert on new/unrecovered failures. |
| Velero DaemonSet rollout/misscheduled | Seven desired/ready agents plus one old agent on the quarantined node. NoSchedule blocked new scheduling but left the existing pod. | Add the explicit quarantine node-affinity exclusion already used by CSI/node-exporter. Keep the quarantine and taints. |
| Bluesky backup CPU throttling | Approximately 68–78% active-period throttling despite p95 CPU of 2.6m; helper sleeps between probes and backup hooks. | Remove its 100m CPU limit, preserve 5m request and 64Mi memory limit; reserve 32Mi memory instead of 16Mi. |
| apps-web Flux timeout | Aimtrix's cold image pull on pi-04 took 7m20s, longer than the tier's 5m health timeout. Both replicas subsequently became Ready. | Allow 15m health checks; leave failure notifications enabled. |
| Historical upgrade failures | Kyverno/webhook availability, Flux controller failures, node load/I/O, transient target outages dominated older messages. Current active alerts do not include these. | Keep these alerts. Hardware quarantine/repair remains a separate operational item. |

At baseline the active non-meta alerts were nine KubeJobFailed instances, two
Velero DaemonSet alerts, and one CPUThrottlingHigh. Evaluating the proposed Job
rule against current live metrics returned no unresolved Job failures. This
predicts resolution after deployment; it does not change running Prometheus.

## Allocation changes

Memory values are MiB. CPU requests are millicores. Limits remain unchanged
unless shown. Existing CPU limits on other workloads are preserved.

| Container | Observed memory peak / CPU p95 | Memory request old → new | Memory limit old → new | CPU request old → new |
| --- | ---: | ---: | ---: | ---: |
| Prometheus | 1396 / 130m | 1280 → 1536 | 1536 → 2048 | 200 unchanged |
| FlareSolverr | 1010 / 315m | 256 → 768 | 1024 → 1536 | 100 → 400 |
| Velero server | 499 / 123m | 256 → 512 | 512 → 768 | 100 → 150 |
| Alloy, maximum across agents | 250 / 10m | 192 → 256 each | 256 → 384 each | 50 unchanged |
| Open WebUI | 1056 / 11m | 512 → 1152 | 1536 unchanged | 100 unchanged |
| LiteLLM server | 874 / 8m | 512 → 1024 | 2048 unchanged | 100 unchanged |
| LiteLLM migration init | 1497 (7-day peak) | 512 → 1536 | 2048 unchanged | 100 unchanged |
| Authentik server, two replicas | 713 / 62m | 512 → 768 each | 1536 unchanged | 100 unchanged |
| Authentik PostgreSQL | 337 / 605m | 256 → 384 | 800 unchanged | 100 → 750 |
| Sonarr | 392 / 570m | 192 → 384 | 512 unchanged | 100 → 600 |
| Prowlarr | 322 / 98m | 128 → 384 | 512 unchanged | 50 → 100 |
| Radarr | 337 / 15m | 192 → 384 | 512 unchanged | 100 unchanged |
| Jellyseerr | 296 / 5m | 192 → 320 | 512 unchanged | 100 unchanged |
| Grafana | 402 / 23m | 192 → 384 | 512 unchanged | 50 unchanged |
| Bluesky backup helper | 20 / 3m | 16 → 32 | 64 unchanged | 5 unchanged; CPU limit removed |
| Velero maintenance Jobs | 373 (7-day peak) | unset → 256 | unset → 768 | unset → 100; no CPU limit |

Velero maintenance Jobs currently produce repeated resource-policy warnings.
Configure their resources through chart 12.2.5's repository-maintenance ConfigMap,
retaining three historical Jobs. This follows the
[Velero 1.18 repository maintenance configuration](https://velero.io/docs/v1.18/repository-maintenance/).

The audit covered 146 running containers. Other measured request overruns worth
tracking include Flux controllers (129–193Mi vs 64Mi reservations), External
Secrets (180Mi vs 64Mi), cert-manager (86Mi vs 32Mi), and CSI sidecars. Their
limits have headroom; this first adjustment prioritizes near-limit workloads
and the largest sustained mismatches. Static web servers use roughly 5–13Mi,
well below their requests; no aggressive downsizing from one day's data.
Older qBittorrent pods approached 2Gi during the upgrade window, but the current
pod is far below that limit; keep its existing 2Gi cap and monitor recurrence.

## Capacity and rollout

Conservative same-node request estimates include the maximum init-container
reservation; they exclude transient rollout surge/maintenance Jobs and do not
predict scheduler placement. LiteLLM's init request remains reserved for the
Pod's lifetime, so it is included even after migration finishes.

| Node | CPU requests before → after | Memory requests before → after | Allocatable memory |
| --- | ---: | ---: | ---: |
| pi-02 | 1440 → 2440m | 3402 → 4618Mi | 7821Mi |
| pi-03 | 800 → 800m | 1874 → 2706Mi | 7821Mi |
| pi-04 | 400 → 400m | 966 → 1222Mi | 3791Mi |
| pi-05 | 1005 → 1005m | 4230 → 6022Mi | 7821Mi |
| raspberrypi-d868c445 | 1235 → 1235m | 3050 → 3130Mi | 7821Mi |
| raspberrypi-e2c042ff | 1525 → 1575m | 2698 → 3018Mi | 7821Mi |
| raspberrypi-f3bf5023 | 575 → 1075m | 998 → 1254Mi | 1846Mi |

Each node has four cores. pi-01 is reserved for critical add-ons; the quarantined
node is not spare capacity. pi-05 has the tightest proposed reservations.
Limits can still overcommit nodes; simultaneous bursts and deployment surge
need observation. Resource edits recreate pods, including stateful services;
roll out in stages through GitOps and verify each tier before the next.

After explicit deployment authorization:

1. Review and merge the IaC through the normal GitOps workflow.
2. Verify monitoring/Velero readiness, healthy Prometheus targets, and seven
   desired/ready Velero agents with zero misscheduled agents. Do not manually
   remove the hardware quarantine.
3. Verify the custom KubeJobFailed rule is loaded exactly once; retained recovered
   Jobs should stop firing. Observe the next naturally scheduled CronJob runs.
4. Verify stateful application readiness and absence of Pending/OOMKilled pods;
   monitor pi-05 and the 2Gi node through the next nightly backup.
5. Verify maintenance Jobs receive resources, nightly backup completion, and
   reduced limit utilization over 24–72 hours. Revisit under-reserved controllers
   and any remaining policy warnings after this first pass.

No live rollout or end-to-end recovery verification has been performed.

## Local validation

- Kustomize: apps/stateful/homelab, apps/web/homelab,
  infrastructure/controllers/homelab, infrastructure/platform/homelab,
  infrastructure/base/monitoring.
- Cluster Flux YAML rendered using a temporary wrapper: clusters/homelab has no
  checked-in kustomization.yaml and cannot be rendered directly with Kustomize.
- Helm: kube-prometheus-stack 93.3.0, Velero 12.2.5, Alloy 1.16.0,
  Authentik 2026.8.5 with proposed values.
- Inspected rendered Velero node affinity, maintenance ConfigMap and server flag;
  exactly one rendered KubeJobFailed rule.
- promtool 3.16.0 syntax validation and ten synthetic recovery/failure cases,
  including missing metrics, duplicate scrapes, namespace isolation, one-off
  jobs, old successes, and the 15-minute firing delay.
- Proposed PromQL evaluated against live data; git diff whitespace validation.
