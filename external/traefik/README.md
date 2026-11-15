# External proxy routes

`homelab.yaml` is a Traefik dynamic configuration fragment for **piproxy**
(`10.10.10.231`), not a Kubernetes manifest. Flux does not deploy this file.

During recovery on November 15, 2026, the proxy lacked routes for 22 cluster
Ingress hosts, including Authentik and Gitea. The fragment forwards those exact
SNI names to the cluster HTTPS NodePort (30581), preserving TLS through to the
cluster's cert-manager certificates. Existing HTTP routes for media/Matrix and
non-cluster services remain in the proxy configuration.

Merge the fragment's `tcp.routers` and `tcp.services` entries into
`/home/pi/traefik/data/traefik-config.yaml`, preserving all other configuration.
Do **not** replace the complete dynamic file with this fragment. The incident
repair saved the original as `traefik-config.yaml.pre-cycle-20261115` alongside
it. Keep that backup private; the full configuration is not tracked here.

The container bind-mounts a single file. Write the merged configuration into
the existing file (preserving the inode); restart the external `traefik`
container if the provider does not reload. Verify both direct proxy access
and the public Cloudflare path with normal certificate verification:

```bash
curl --resolve auth.alucard.dev:443:10.10.10.231 \
  https://auth.alucard.dev/application/o/gitea/.well-known/openid-configuration
curl https://auth.alucard.dev/application/o/gitea/.well-known/openid-configuration
curl -I https://code.alucard.dev
```

For rollback, copy the backup contents into the existing dynamic configuration
file and reload/restart Traefik. The rule is an explicit allow-list; adding a
new public Ingress requires updating the proxy too. Unlisted hosts still use
the proxy's existing routing. Existing HTTP middlewares are not used by these
new TLS passthrough routes; application routing and TLS terminate in-cluster.

Cinny retains its pre-existing default-origin-certificate configuration (see
`apps/matrix/cinny-ingress.yaml`); direct origin hostname verification for
Cinny will fail. Its public path relies on Cloudflare's existing Full mode.
Do not treat that as evidence of a newly broken passthrough route, or claim
that all origin certificates have been validated.

See [Traefik TLS passthrough](https://doc.traefik.io/traefik/v2.11/routing/routers/).
