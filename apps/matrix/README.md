# Matrix (Synapse) homeserver

Self-hosted [Matrix](https://matrix.org/) homeserver (Synapse) + Element web
client, deployed via Flux.

- **Server name:** `alucard.dev` (permanent — forms every user ID `@you:alucard.dev`)
- **Homeserver URL:** `https://matrix.alucard.dev`
- **Web client:** `https://element.alucard.dev`
- **Registration:** closed. Accounts are created manually (see step 3).
- **Delegation:** `alucard.dev/.well-known/matrix/*` is routed to Synapse
  (`wellknown-ingress.yaml`), so the short `@you:alucard.dev` handles resolve to
  the homeserver at `matrix.alucard.dev`. The static site keeps serving the rest
  of `alucard.dev`.

## Architecture

| Component | What | Where |
|-----------|------|-------|
| Synapse   | Matrix homeserver | `synapse-*.yaml` |
| PostgreSQL | Synapse database (StatefulSet) | `postgresql.yaml` |
| Element   | Web client | `element-*.yaml` |
| Secrets   | Vault → ESO → K8s Secret | `vault-store.yaml`, `externalsecrets.yaml` |

Non-secret Synapse config lives in the `synapse-config` ConfigMap
(`synapse-config.yaml`). Secret values are templated by ESO into a `secrets.yaml`
config fragment (never in Git) and merged at runtime via
`-c /config/homeserver.yaml -c /secrets/secrets.yaml`.

## One-time bootstrap

These steps are done **once**, by hand, and are intentionally **not** in Git.

### 1. Seed Vault secrets (strong random values)

```sh
PGPASS=$(openssl rand -hex 24)
kubectl exec -n vault vault-0 -- vault kv put secret/matrix/postgresql \
  username=synapse password="$PGPASS"

kubectl exec -n vault vault-0 -- vault kv put secret/matrix/synapse \
  registration_shared_secret="$(openssl rand -hex 32)" \
  macaroon_secret_key="$(openssl rand -hex 32)" \
  form_secret="$(openssl rand -hex 32)"
```

The existing `external-secrets` Vault policy already grants read on
`secret/data/*`, so no Vault/Terraform policy change is needed.

### 2. DNS (Cloudflare — same zone as alucard.dev)

Add records pointing at the cluster ingress IP (same target as `alucard.dev`):

- `matrix.alucard.dev`
- `element.alucard.dev`

Certificates use the DNS-01 solver so they issue regardless of public
reachability, but clients and **federation** need `matrix.alucard.dev` to resolve
publicly.

### 3. Create accounts (after Synapse is Running)

```sh
# Admin account for yourself
kubectl exec -n matrix deploy/synapse -- \
  register_new_matrix_user -c /config/homeserver.yaml -c /secrets/secrets.yaml \
  -u spencer -a http://localhost:8008

# A friend (drop -a for a non-admin)
kubectl exec -n matrix deploy/synapse -- \
  register_new_matrix_user -c /config/homeserver.yaml -c /secrets/secrets.yaml \
  -u friendname http://localhost:8008
```

## Verify

```sh
flux reconcile kustomization apps --with-source
kubectl -n matrix get pods,externalsecret,ingress
kubectl get certificate -n matrix          # certs should be Ready

curl https://alucard.dev/.well-known/matrix/server      # -> {"m.server":"matrix.alucard.dev:443"}
curl https://matrix.alucard.dev/_matrix/client/versions # -> JSON version list
```

Then paste `alucard.dev` into <https://federationtester.matrix.org/> (all
green), log into <https://element.alucard.dev> as `@spencer:alucard.dev`, and
`/join` your friend's room to confirm federation.
