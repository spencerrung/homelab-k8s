# atproto PDS (Bluesky)

Self-hosted AT Protocol Personal Data Server using the official
[bluesky-social/pds](https://github.com/bluesky-social/pds), deployed via Flux.
Federates into the real Bluesky network.

- **PDS host:** `https://pds.alucard.dev` (Cloudflare **proxied / orange** — origin IP hidden, like matrix)
- **Handles:** custom domains, e.g. `@you.alucard.dev` (set per-account via a `_atproto` TXT record — no wildcard)
- **Image:** `ghcr.io/bluesky-social/pds:0.4` (multi-arch, arm64 — public, no pull secret)
- **Storage:** SQLite + on-disk blobs in `/pds` (single container, no separate DB)

> **Note:** We originally scoped `tranquil-pds` (the PDS a friend runs) but it
> ships amd64-only images and this cluster is arm64. Running the official PDS
> for now; we can migrate to tranquil later via atproto account migration if an
> arm64 build appears. See `~/.claude/plans/enchanted-crunching-lerdorf.md`.

## Architecture

| Piece | What | Where |
|-------|------|-------|
| pds | PDS (Node + SQLite) | `deployment.yaml` |
| Secrets | Vault → ESO → env | `vault-store.yaml`, `externalsecrets.yaml` |
| TLS | cert-manager via ingress annotation (single host) | `ingress.yaml` |

Non-secret config is plain env in `deployment.yaml`. Secrets (`PDS_JWT_SECRET`,
`PDS_ADMIN_PASSWORD`, `PDS_PLC_ROTATION_KEY_K256_PRIVATE_KEY_HEX`) come from the
ESO-managed `pds-secrets` secret — nothing secret in Git.

## ⚠️ Gotchas

- **Cloudflare proxied:** `pds.alucard.dev` is orange-clouded (proxied) just like
  matrix, so the origin IP stays hidden. cert-manager issues the origin cert
  (DNS-01) and CF proxies it. We deliberately avoid a `*.pds.alucard.dev`
  wildcard (CF's free cert can't cover a 2-level wildcard while proxied, which
  would force a grey-cloud / exposed-IP setup).
- **Handles:** because there's no wildcard, user handles are custom domains
  (`@you.alucard.dev`), set after account creation via a `_atproto` DNS TXT
  record (standard atproto custom-handle flow). One TXT per account.
- **Permanent identity:** once accounts exist, the PDS hostname is baked into
  their DIDs. Changing hostnames later means account migration, not a rename.

## One-time bootstrap (not in Git)

### 1. Vault secrets
```sh
kubectl exec -n vault vault-0 -- vault kv put secret/atproto/pds \
  jwt_secret="$(openssl rand --hex 16)" \
  admin_password="$(openssl rand --hex 16)" \
  plc_rotation_key="$(openssl ecparam --name secp256k1 --genkey --noout --outform DER | tail --bytes=+8 | head --bytes=32 | xxd --plain --cols 32)"
```
(`plc_rotation_key` must be a 64-hex-char secp256k1 private key — the command
above matches the official PDS installer.)

### 2. DNS (Cloudflare, proxied / orange cloud)
One record, proxied like your other services (origin IP stays hidden):
- `pds.alucard.dev` → origin IP → **orange / Proxied**

### 3. Create your account
The image has no `pdsadmin` script; use the admin HTTP API (admin basic-auth
user is `admin`, password is `PDS_ADMIN_PASSWORD` from Vault):
```sh
ADMIN=$(kubectl exec -n vault vault-0 -- vault kv get -field=admin_password secret/atproto/pds)

# 1. mint a single-use invite code
CODE=$(curl -sX POST https://pds.alucard.dev/xrpc/com.atproto.server.createInviteCode \
  -u "admin:$ADMIN" -H 'Content-Type: application/json' \
  -d '{"useCount":1}' | jq -r .code)

# 2. create the account
curl -sX POST https://pds.alucard.dev/xrpc/com.atproto.server.createAccount \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"you@example.com\",\"handle\":\"spencer.pds.alucard.dev\",\"password\":\"<pick-a-strong-pw>\",\"inviteCode\":\"$CODE\"}"
```
The initial `spencer.pds.alucard.dev` handle won't resolve (no wildcard, by
design). Log into any Bluesky client with server `https://pds.alucard.dev`, then
immediately switch to your real handle:

### 4. Set your custom handle (@you.alucard.dev)
In the Bluesky app: **Settings → Handle → I have my own domain** → enter
`you.alucard.dev`. It shows a `_atproto` TXT record to add in Cloudflare:
- **Type** TXT · **Name** `_atproto.you` · **Content** `did=did:plc:...` · TTL Auto
  (TXT records aren't proxied — orange/grey is irrelevant.)

Verify in the app; your handle becomes `@you.alucard.dev`. Repeat one TXT per
account. (No handle A-record needed — resolution is via the TXT; the DID's
service endpoint already points at `pds.alucard.dev`.)

## Verify
```sh
flux reconcile kustomization apps --with-source
kubectl -n atproto get pods,externalsecret,ingress,certificate
curl https://pds.alucard.dev/xrpc/_health                              # -> {"version":"..."}
curl https://pds.alucard.dev/xrpc/com.atproto.server.describeServer    # -> JSON
```
After creating your account, post from a client pointed at
`https://pds.alucard.dev` and confirm it appears on bsky.app (federation).
