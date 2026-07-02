# Gitea

Gitea deployed via the official Helm chart, with **Authentik OIDC** login and an
**external single-instance PostgreSQL** (`postgresql.yaml`).

## Database

The chart's Bitnami `postgresql-ha` (repmgr) subchart was chronically broken
(split-brain crashloop) and Bitnami deprecated its free image catalog, so it was
replaced with a single-instance `postgres:15-alpine` StatefulSet (`postgresql.yaml`),
mirroring the Authentik pattern. The unused `redis-cluster` was also disabled
(this Gitea uses `cache=memory`, `session=db`, `queue=level`).

Git repositories live on the `gitea-shared-storage` PVC and are unaffected by the
database change. Users re-provision automatically on next Authentik OIDC login.

Credentials come from Vault (`secret/gitea/postgresql`) via ESO
(`gitea-postgresql` ExternalSecret) and the password is injected into `app.ini`
through `gitea.additionalConfigFromEnvs`.

## One-time bootstrap (before the first reconcile)

Seed the Postgres credentials in Vault (strong random password, never committed):

```sh
kubectl exec -n vault vault-0 -- vault kv put secret/gitea/postgresql \
  username=gitea password="$(openssl rand -hex 24)"
```

The existing `external-secrets` Vault policy already grants read on
`secret/data/*`, so no policy change is needed.

## After migration — clean up orphaned Bitnami resources (optional)

Disabling the HA subchart leaves the old StatefulSet PVCs behind (retained by
design). Once the new Gitea is verified healthy, reclaim the space:

```sh
kubectl delete pvc -n gitea \
  data-gitea-postgresql-ha-postgresql-0 \
  data-gitea-postgresql-ha-postgresql-1 \
  data-gitea-postgresql-ha-postgresql-2 \
  valkey-data-gitea-valkey-cluster-0 \
  valkey-data-gitea-valkey-cluster-1 \
  valkey-data-gitea-valkey-cluster-2
```

## Verify

```sh
kubectl -n gitea get pods                     # postgresql-0 + one gitea pod Ready
kubectl -n gitea logs deploy/gitea -c init-app-ini | grep -i database
curl -s https://code.alucard.dev/api/v1/version   # -> {"version":"..."}
```

Then log in at <https://code.alucard.dev> via Authentik.
