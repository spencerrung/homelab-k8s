# Monitoring

## Where things are

| Thing | Location |
|---|---|
| Grafana | `grafana.alucard.dev` — admin creds in Vault `secret/monitoring/grafana` |
| Prometheus | `kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090` |
| Alertmanager | `... svc/kube-prometheus-stack-alertmanager 9093:9093` |
| Loki | Grafana → Explore → Loki |
| Alerts | Matrix room **Homelab Alerts** (`!blIpnGzhOAWXoAkiSG:alucard.dev`), bot `@alertmanager:alucard.dev` (creds in Vault `secret/monitoring/matrix`) |

Both Alertmanager (via `metio/matrix-alertmanager-receiver`) and Flux (via
the native matrix Provider in `infrastructure/base/flux-alerts/`) post to
the same room.

## Add scraping for a new component

- Helm chart: flip its `serviceMonitor`/`metrics` values on — Prometheus
  is configured with `*SelectorNilUsesHelmValues: false`, so any
  ServiceMonitor/PodMonitor in any namespace is picked up automatically.
- Raw manifests: add a ServiceMonitor/PodMonitor to
  `infrastructure/base/monitoring-configs/` (NOT `monitoring/` — CRD
  instances live a tier below the chart that installs the CRDs).

## Add a dashboard

Preferred: `gnetId` entry in the `grafana.dashboards.default` block of
`infrastructure/base/monitoring/kube-prometheus-stack.yaml`. **Verify the
revision exists first** (`https://grafana.com/api/dashboards/<id>`) — a
bad revision fails the Grafana pod. Custom dashboards: ConfigMap labeled
`grafana_dashboard: "1"` in `monitoring-configs/` (sidecar watches all
namespaces).

## Test the alert path

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093 &
curl -X POST localhost:9093/api/v2/alerts -H 'Content-Type: application/json' -d \
 '[{"labels":{"alertname":"Test","severity":"warning"},"annotations":{"summary":"test"}}]'
```

Message should reach the Matrix room within ~1 minute (group_wait 30s).

## Known shape of the stack

Prometheus (pi-05, 7d/8GB retention, 15Gi PVC), Loki single-binary
(pi-02, 7d, 10Gi), Alloy DaemonSet (all nodes, ~150Mi each), Grafana
stateless (dashboards from values + sidecar). k3s trims: scheduler,
controller-manager, kube-proxy, etcd scrapes and their default rules are
disabled — k3s folds those metrics into the apiserver endpoint.
