# K3s certificate expiry and recovery

An API server that answers with `You must be logged in to the server` may
have an expired client certificate, even when the endpoint and CA are correct.
Check certificate dates before replacing credentials or rebuilding anything.

During the November 2026 incident, the admin and worker kube-proxy certificates
expired on October 22. Kubelets still had valid certificates, so workers could
report `Ready` while service and network-policy watches failed with
`Unauthorized`. Restarting only the server restored administrative access but
did not refresh the running workers. Stale networking also blocked Vault
snapshots. The separate offline worker had stopped reporting on October 4 and
needed a physical power-cycle; its original failure was not established.

## Diagnose without exposing credentials

Use an explicit kubeconfig throughout. Display only certificate metadata:

```bash
kubectl --kubeconfig ~/.kube/homelab1.yaml config view --raw \
  -o jsonpath='{.users[0].user.client-certificate-data}' |
  base64 -d | openssl x509 -noout -dates
```

On the server, inspect `/var/lib/rancher/k3s/server/tls/client-admin.crt`.
On **every worker**, inspect both certificates:

```bash
sudo openssl x509 -in /var/lib/rancher/k3s/agent/client-kube-proxy.crt -noout -dates
sudo openssl x509 -in /var/lib/rancher/k3s/agent/client-kubelet.crt -noout -dates
sudo journalctl -u k3s-agent --since '10 minutes ago' --no-pager |
  grep -E 'Unauthorized|certificate has expired'
```

Check host clocks as well. A healthy kubelet certificate does not prove that
kube-proxy or network-policy controllers can authenticate.

## Renew in a controlled sequence

Service restarts are live maintenance and require operator authorization.
Preserve existing data, CA material, and cluster configuration. Do not reset
the cluster, delete certificate directories, or reinstall K3s to renew leaves.

1. On the control-plane node, run `sudo systemctl restart k3s`. Verify the
   service is active, the admin certificate has a future expiry, and
   `sudo k3s kubectl get nodes` succeeds.
2. Back up the local kubeconfig with mode `0600`. Refresh its embedded client
   certificate and key from `/etc/rancher/k3s/k3s.yaml` over SSH, preserving the
   reachable API endpoint and context names. Validate a temporary copy before
   replacing the original. Never print or commit kubeconfig credentials.
3. Discover the live worker list with `kubectl get nodes -o wide`; the Ansible
   inventory may not contain every subsequently added worker.
4. Restart `k3s-agent` on each affected worker **one at a time**. Verify the
   service is active, `client-kube-proxy.crt` has renewed, and the node is
   `Ready` before proceeding. Confirm its API watches no longer report
   `Unauthorized`. Avoid restarting application pods unless they still fail.

K3s renews eligible certificates at startup. Renewal windows vary by version;
the deployed v1.29.10 release uses the older 90-day window. Long-running
services need planned maintenance before expiry. See the upstream
[certificate documentation](https://docs.k3s.io/cli/certificate).

## Verify recovery beyond node readiness

- Check deployments, StatefulSets, DaemonSets, PVCs, and recent warning events.
  Distinguish retained failed Jobs from currently failing workloads.
- Confirm all Flux Kustomizations, HelmReleases, ExternalSecrets, and issued
  Certificates are ready.
- Check Prometheus targets and alerts, especially
  `KubeClientCertificateExpiration`. Inspect dates on disk even if an alert
  clears; historical metric windows can also keep an alert active temporarily.
- Verify Vault is unsealed and run a replacement snapshot from its CronJob.
  Confirm both snapshot creation and B2 upload finish successfully.
- Run a fresh Velero backup from the affected schedule and inspect its final
  phase, errors, hooks, and pod-volume backups. Old `PartiallyFailed` backups
  remain failed records; they are not repaired by cluster recovery.
- Test application endpoints through the cluster NodePort and through public
  DNS separately. Successful direct routing does not verify Cloudflare or the
  external reverse proxy. Obtain current NodePorts from the Traefik Service.

The built-in `KubeClientCertificateExpiration` alert must be acted on before
expiry. Include certificate-date checks for the server, every worker, and
copied administrator kubeconfigs in routine maintenance. Review
[monitoring](monitoring.md) for the alert delivery path.
