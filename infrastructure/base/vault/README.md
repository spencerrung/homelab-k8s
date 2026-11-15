# Vault

The active deployment uses **single-node Raft**, one replica pinned to pi-03
with a local-path PVC. Standalone/file mode and the injector are disabled.
Raft snapshots are uploaded by the snapshot CronJob.

Vault is manually unsealed after every pod restart. The existing installation
has one Shamir share and a threshold of one; use the existing key from the
password manager. Never initialize an already initialized Vault.

```bash
export KUBECONFIG="$HOME/.kube/homelab1.yaml"
kubectl exec -n vault vault-0 -- vault status
# Interactive hidden prompt: do not put the key in command arguments.
kubectl exec -it -n vault vault-0 -- vault operator unseal
kubectl wait -n vault pod/vault-0 --for=condition=Ready --timeout=120s
kubectl get clustersecretstore vault-backend
kubectl get externalsecrets -A
```

`vault status` exits 2 while sealed. Readiness should stay false until unsealed;
existing application Secrets remain available, but ESO cannot refresh them.

For a fresh installation, use [the bootstrap runbook](../../../docs/runbooks/bootstrap.md)
and `bootstrap/vault-init.sh` from the repository root. That script owns the
KV engine, policies and Kubernetes authentication roles. Do not substitute
manual wildcard service-account permissions.

For recovery of existing data, follow [disaster recovery](../../../docs/runbooks/disaster-recovery.md).
For routine restarts and dependent services, follow
[node cycle recovery](../../../docs/runbooks/node-cycle-recovery.md).

Store unseal keys and root tokens outside Git in the password manager. This
deployment has no automatic unseal configured.
