# Media stack: getting started

The arr suite in the `media` namespace: Prowlarr (indexer manager),
Sonarr (TV), Radarr (movies), qBittorrent (downloads), Jellyseerr
(requests). Manifests: `apps/media/`.

## What is IaC vs what you configure once in the UI

**Declared in git/Vault (never configure by hand):**

- All deployments, ingresses, storage, resource limits
- The shared media volume (UNAS NFS, mounted at `/data` everywhere)
- **API keys** — fixed values from Vault, injected as
  `SONARR__AUTH__APIKEY` / `RADARR__AUTH__APIKEY` /
  `PROWLARR__AUTH__APIKEY`. Seed once (before first launch, or restart
  the pods after):

  ```bash
  kubectl exec -n vault -i vault-0 -- env VAULT_TOKEN="$VAULT_ROOT_TOKEN" \
    sh -c 'vault kv put secret/media/api-keys \
      sonarr=$(head -c16 /dev/urandom | xxd -p) \
      radarr=$(head -c16 /dev/urandom | xxd -p) \
      prowlarr=$(head -c16 /dev/urandom | xxd -p)'
  ```

  Read a key back when a UI asks for one:
  `kubectl get secret -n media media-api-keys -o jsonpath='{.data.sonarr}' | base64 -d`

**One-time UI setup (state lives in each app's SQLite on its config
PVC, which Velero does NOT back up — media namespace is excluded; if you
want config backed up say so and we'll add the config PVCs):** the
connection wiring below.

## Directory convention (the hardlink rule)

Everything shares one volume at the same path — imports are instant
hardlinks/moves, never copies across NFS:

```
/data/downloads   qBittorrent writes here
/data/tv          Sonarr library
/data/movies      Radarr library
```

Create the directories once (any pod):
`kubectl exec -n media deploy/sonarr -- mkdir -p /data/downloads /data/tv /data/movies`

## Setup order

### 1. qBittorrent — `qbt.alucard.dev`

1. Get the temporary admin password from the logs:
   `kubectl logs -n media deploy/qbittorrent | grep -i "temporary password"`
2. Log in as `admin` + that password → Settings → WebUI: set a permanent
   password.
3. Same page: **check "Bypass authentication for clients in whitelisted
   IP subnets"** and add `10.42.0.0/16` (the pod CIDR). This is how
   Sonarr/Radarr connect without a shared credential — subnet trust
   instead of secrets.
4. Settings → Downloads: Default Save Path `/data/downloads`.
5. Settings → BitTorrent (recommended): enable "Keep incomplete torrents
   in" `/data/downloads/incomplete`.

### 2. Sonarr — `sonarr.alucard.dev` / Radarr — `radarr.alucard.dev`

First visit asks for auth: choose Forms, create your login. Then in each:

1. Settings → Media Management → Add Root Folder: `/data/tv` (Sonarr) /
   `/data/movies` (Radarr). Enable "Use Hardlinks instead of Copy"
   (Settings → Media Management → Importing — on by default).
2. Settings → Download Clients → + → qBittorrent:
   - Host `qbittorrent` · Port `8080` (in-cluster DNS, same namespace)
   - Leave username/password empty (subnet whitelist handles it)
3. Nothing to do for indexers — Prowlarr pushes them (next step).

### 3. Prowlarr — `prowlarr.alucard.dev`

1. First visit: Forms auth, create login.
2. Settings → Apps → + for each:
   - **Sonarr**: Prowlarr Server `http://prowlarr:9696`, Sonarr Server
     `http://sonarr:8989`, API key = the `sonarr` value from Vault
   - **Radarr**: Radarr Server `http://radarr:7878`, API key = the
     `radarr` value
   - Sync Level: "Add and Remove Only" (or Full Sync)
3. Indexers → + : add your indexers/trackers. They propagate to
   Sonarr/Radarr automatically — never add indexers in the arr apps
   directly.

### 4. Jellyseerr — `requests.alucard.dev`

1. First visit: sign-in setup. No Plex/Jellyfin? Choose local account
   (a media server can be attached later).
2. Settings → Services → add Sonarr (`http://sonarr:8989`, API key,
   quality profile, root folder `/data/tv`) and Radarr
   (`http://radarr:7878`, root `/data/movies`); mark both as default.
3. Household members get accounts here and request; Sonarr/Radarr do the
   rest.

## In-cluster connection matrix

| From → To | URL | Auth |
|---|---|---|
| Prowlarr → Sonarr | `http://sonarr:8989` | Vault `media/api-keys` `sonarr` |
| Prowlarr → Radarr | `http://radarr:7878` | Vault `radarr` |
| Sonarr/Radarr → qBittorrent | `http://qbittorrent:8080` | subnet whitelist |
| Jellyseerr → Sonarr/Radarr | same as Prowlarr | same keys |

## Verify the hardlink promise

After the first completed download imports:

```bash
kubectl exec -n media deploy/sonarr -- sh -c \
  'ls -li /data/downloads/<file> /data/tv/<show>/<file>'
```

Same inode number on both = hardlink, zero copy. Different = check the
paths all live under the single `/data` mount.

## FlareSolverr (Cloudflare-protected indexers)

Deployed cluster-internal at `http://flaresolverr:8191`. One-time wiring:
Prowlarr → Settings → Indexers → Add Indexer Proxy → FlareSolverr, host
`http://flaresolverr:8191`, tag `flaresolverr`. Then add that tag to
exactly the indexers that need challenge-solving — tagged searches take
a few extra seconds each (headless Chromium on a Pi), so don't tag
indexers that work without it.

## Going further (optional, not yet installed)

- **Recyclarr**: declarative TRaSH-guide quality profiles for
  Sonarr/Radarr as a CronJob — the next IaC step if you start tuning
  quality settings.
- **Bazarr** (subtitles), **gluetun** VPN sidecar for qBittorrent — both
  slot into the existing layout; ask when wanted.
- **Jellyfin**: deliberately not deployed — Pi 4 has no usable container
  transcode path. Direct-play-only is possible; running it on the UNAS
  is likely better.
