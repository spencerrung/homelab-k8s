# Flux upgrades

Flux controllers and CRDs are managed by the `flux-controllers` Kustomization
from `infrastructure/flux-system`. Its prune setting is false so accidentally
removing that entry cannot delete the controllers or cluster CRDs. Application
Kustomizations retain their existing dependency graph.

Generate controller manifests with the checksum-verified official Flux CLI
for the exact target release; do not hand-edit `gotk-components.yaml`:

```sh
flux install --version=v2.10.0 \
  --components-extra=image-reflector-controller,image-automation-controller \
  --export > infrastructure/flux-system/gotk-components.yaml
```

Before each minor upgrade:

1. Confirm Kubernetes is supported by the target Flux release. The planned
   path is 2.7.2 -> 2.8.8 -> 2.9.6 -> 2.10.0, alongside sequential K3s upgrades.
2. Back up the Kubernetes datastore and Flux resources privately. Review the
   target release notes, controller arguments, RBAC changes and ARM64 images.
3. Use the target CLI's `flux migrate -f . --dry-run`, then migrate the repo
   manifests. Review the diff and render affected Kustomizations.
4. Run `flux migrate --kubeconfig <cluster>` before installing the new CRDs.
   This rewrites existing resources to current stored API versions and removes
   obsolete storedVersions. Do not simply patch storedVersions without first
   migrating the objects.
5. Validate and merge the release PR, reconcile the source and
   `flux-controllers`, and wait for all six controllers plus the existing
   Kustomizations, Helm releases and image automation to become Ready.
6. Only proceed to the next minor after health checks succeed. Keep local CLI
   versions separate so intermediate upgrades can be reproduced.

The image automation resources use `image.toolkit.fluxcd.io/v1`; beta APIs
are removed by newer Flux releases. Notification APIs must be reviewed again
for Flux 2.10, including deprecated summary/interval fields and secret handling.
Install the Flux 2.10 CRDs/controllers before a separate commit promotes
Alert and Provider manifests to v1. Their existing v1beta3 API remains served
during this transition, so independent GitOps tiers cannot race to apply an
API version the cluster does not serve yet. Then run the live migration again
to update the notification resources' stored version.

References:
https://github.com/fluxcd/flux2/discussions/5572
https://github.com/fluxcd/flux2/releases
