# Recovery after a node or power cycle

Use the intended kubeconfig for every command:

```bash
export KUBECONFIG="$HOME/.kube/homelab1.yaml"
kubectl get nodes
kubectl get pods -A -o wide
kubectl get events -A --field-selector type=Warning --sort-by=.lastTimestamp
```

Local-path volumes stay on their original nodes. Do not delete PVCs or
reinitialize databases to resolve slow startup. After a simultaneous reboot,
pi-03 can take several minutes to load its stateful applications from storage.

## Vault and Flux

Vault uses one Raft replica on pi-03 with manual Shamir unseal (one share,
threshold one). Check `kubectl exec -n vault vault-0 -- vault status` first.
Exit code 2 means sealed. If initialized, **do not initialize it again**.

Unseal using the existing key from the password manager. This interactive
command prompts without placing the key in shell history or command arguments:

```bash
kubectl exec -it -n vault vault-0 -- vault operator unseal
kubectl wait -n vault pod/vault-0 --for=condition=Ready --timeout=120s
kubectl get clustersecretstore vault-backend
kubectl get externalsecrets -A
kubectl get kustomizations -n flux-system
```

Let ESO and Flux retry. Existing rendered Secrets let many applications run
while Vault is sealed, but new secret synchronization and dependent Flux tiers
remain blocked. Do not bypass this by marking sealed Vault healthy.

## Gitea and Authentik

Gitea's configure init container performs OIDC discovery against
`https://auth.alucard.dev`. Public Cloudflare/origin failures can therefore
prevent Gitea startup even when Authentik is healthy internally.

`infrastructure/base/coredns-custom` rewrites only this exact DNS name to the
Traefik Service within the cluster. The issuer URL, Host header and TLS
verification stay unchanged. External clients still use public DNS; this does
not repair a public origin outage. ACME `_acme-challenge` names are unaffected.

K3s mounts `coredns-custom` and imports `*.override`; allow ConfigMap projection
and CoreDNS reload to complete. Verify from an existing application pod that
the name resolves to the Traefik Service IP and HTTPS discovery returns 200.
Then check Gitea's init logs and deployment readiness.

See [K3s custom CoreDNS configuration](https://docs.k3s.io/advanced) and
[CoreDNS exact rewrites](https://coredns.io/plugins/rewrite/).

## Backups

Check both backup storage availability and actual backup results:

```bash
kubectl get backupstoragelocations,backuprepositories -n velero
kubectl get backups -n velero --sort-by=.metadata.creationTimestamp
```

Inspect Velero backup logs for `PartiallyFailed` results. On November 15, 2026,
the Authentik pre-backup `pg_dumpall` hook exhausted PostgreSQL's shared lock
table. `max_locks_per_transaction=256` increases capacity from the default 64;
changing this server setting requires a database restart. See the
[PostgreSQL lock settings](https://www.postgresql.org/docs/15/runtime-config-locks.html).
Verify a fresh dump and a new backup after applying the fix. A successful
backup is not a substitute for the restore test in disaster-recovery.md.

## Certificates and public access

`Ready=True` on an existing Certificate does not prove renewal is working.
Check expiration dates and pending Challenges too:

```bash
kubectl get certificates -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,EXPIRES:.status.notAfter'
kubectl get challenges -A
```

If Cloudflare rejects the API token, replace it in Vault at
`secret/cert-manager/cloudflare` (property `api-token`) and let ESO refresh
`cert-manager/cloudflare-api-token`. Verify the property against the
ExternalSecret before updating. Keep credentials out of Git and command logs.
The token needs Zone DNS Edit and Zone Read for the managed zone; see
[cert-manager's Cloudflare instructions](https://cert-manager.io/docs/configuration/acme/dns01/cloudflare/).

Test public access separately from direct NodePort access. A successful local
HTTPS request with the original hostname confirms ingress/application health,
but does not confirm Cloudflare can reach the public origin.

The external proxy route fragment and rollback procedure are tracked in
[external/traefik](../../external/traefik/README.md).

If Cloudflare accepts the token but DNS01 propagation checks remain pending,
compare normal DNS answers with public DNS-over-HTTPS. During this incident,
port-53 queries returned NXDOMAIN even when directed to public/authoritative
servers, while Cloudflare DoH saw the TXT records. The cert-manager release
therefore uses `--dns01-recursive-nameservers-only` with Cloudflare and Google
DoH endpoints. This changes certificate self-checks, not general cluster DNS.
See the [cert-manager controller flags](https://cert-manager.io/v1.20-docs/cli/controller/).

After DNS is fixed, old orders can still fail with `Expired authorization`
or `No order for ID`. Once a renewal has terminally failed, request a fresh
attempt with `cmctl renew --namespace <namespace> <certificate>`. Check the
new certificate's expiration/renewal timestamps; `Ready=True` alone may still
describe the old certificate. Keep existing certificate Secrets while retrying.
See the [cert-manager renewal FAQ](https://cert-manager.io/docs/faq/).
