# Add a new app

The honest checklist, including the steps outside this repo that everyone
forgets.

## 1. Manifests

Copy the shape of an existing app:

- stateless: `apps/breathe/` (namespace, deployment, service, ingress)
- stateful / multi-component / secrets: `apps/matrix/`

Conventions:

- namespace = app name; arm64 images only (`docker manifest inspect` to
  check); exact tags, never `:latest` (first-party Tekton-built images are
  the exception until image automation fully lands)
- requests **and** limits on everything; liveness + readiness probes
- ingress annotations, verbatim:

  ```yaml
  kubernetes.io/ingress.class: traefik
  cert-manager.io/cluster-issuer: letsencrypt-prod
  traefik.ingress.kubernetes.io/router.entrypoints: web,websecure
  ```

  with `tls.secretName: <name>-tls`
- PVCs: add `kustomize.toolkit.fluxcd.io/prune: disabled` annotation if
  the data would hurt to lose; remember local-path data is node-local

## 2. Secrets (if any)

1. Put values in Vault: `vault kv put secret/<app>/<name> key=value ...`
2. Add an `ExternalSecret` referencing
   `secretStoreRef: {kind: ClusterSecretStore, name: vault-backend}` —
   copy from `apps/matrix/externalsecrets.yaml`. No per-namespace
   SecretStore or ServiceAccount is needed.

## 3. Register with Flux

Add the app directory to the right tier:

- `apps/web/homelab/kustomization.yaml` — stateless
- `apps/stateful/homelab/kustomization.yaml` — has PVCs

New HelmRelease in a new namespace? Also add the namespace to the Alert in
`infrastructure/base/flux-alerts/alerts.yaml`, and add it to the Velero
`nightly-stateful` schedule in `infrastructure/base/velero/release.yaml`
if it holds data.

## 4. Outside this repo (the forgotten steps)

1. **Cloudflare**: DNS record for `<host>.alucard.dev`
2. **External reverse proxy**: route for the new hostname to the cluster

## 5. Ship and verify

```bash
git push   # or PR
flux reconcile kustomization apps-web --with-source   # or apps-stateful
kubectl get certificate -n <app>     # Ready
curl -I https://<host>.alucard.dev
```

If you added a new top-level Flux Kustomization (rare), update the graph
in [architecture.md](../architecture.md).
