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

### 0. VPN (already wired)

qBittorrent runs behind a gluetun sidecar: all its traffic exits via PIA
(CA Vancouver - PIA only offers port forwarding outside the US) with a
killswitch; the ISP sees one encrypted tunnel. Creds: Vault
`secret/media/vpn`. Verify anytime:
`kubectl exec -n media deploy/qbittorrent -c qbittorrent -- wget -qO- https://ipinfo.io/json`
should show a PIA IP, not the home IP. In qbt WebUI settings enable
"Bypass authentication for clients on localhost" so gluetun can push
forwarded-port renewals into qbt. Prowlarr/FlareSolverr/arrs are NOT
tunneled (indexer browsing is ordinary HTTPS; peers never see them).

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

## Requests accepted but nothing arrives

Trace each stage before changing profiles or selecting another release:

1. Check Jellyseerr's request status, then Sonarr/Radarr Activity and history.
   An accepted request may already have a download in progress; completed
   imports are recorded separately. Do not treat a seeding torrent as a failed
   import without checking history.
2. Check qBittorrent's progress, transfer rate, peers and tracker errors. A
   stalled download can be a peer-availability problem, but DNS failures can
   also prevent tracker discovery. Preserve the torrent and partial data while
   restoring connectivity; reannounce trackers after recovery.
3. Verify both tunnel health and **the VPN container's local resolver**:

   ```bash
   kubectl -n media exec deploy/qbittorrent -c gluetun -- sh -ec \
     '/gluetun-entrypoint healthcheck && nslookup example.com 127.0.0.1 >/dev/null'
   ```

   In November 2026 the tunnel health check passed while local DNS timed out.
   The logs showed failed public-IP discovery and PIA port-forward setup.
   Restarting the pod restored DNS and forwarding, and the stalled movie began
   downloading again. Gluetun's startup, readiness and liveness probes now
   require both checks; the firewall and VPN routing remain unchanged. Startup
   allows time for DNS filter lists to download, and liveness requires three
   consecutive failures before restarting the container.
4. Compare `/tmp/gluetun/forwarded_port` in Gluetun with qBittorrent's listening
   port. A successful tunnel alone does not establish that forwarding renewed
   or that the localhost preference-update hook succeeded.
5. Test Prowlarr's indexer proxy and affected indexers. FlareSolverr's `/`
   endpoint only proves that its HTTP server responds; the proxy test exercises
   the browser. A stuck browser can leave the pod Ready while searches time out.
   After an authorized restart, repeat the proxy and indexer tests rather than
   disabling healthy sources or weakening quality rules.

For an immediate pod restart, identify its exact name and delete only that pod
after authorization; the Deployment recreates it with the existing PVC. Flux
can remove a manually added rollout-restart annotation before the replacement
is ready. Do not delete PVCs or partial downloads. Runtime API credentials must
stay in memory or the app's secret references, never in logs or committed files.

These checks concern internal service/VPN DNS. They do not require changing
public `alucard.dev` DNS records.

### Brief Gluetun readiness failures

Check container restart counts and timestamped events before interpreting a
red readiness indicator as a VPN restart. During the November 2026 recovery,
Gluetun logged TLS connection resets to Cloudflare at `1.1.1.1:853`, including
one for the readiness probe's `example.com` lookup. Both containers retained
zero restarts and the VPN had not reconnected. Resource usage was normal.
The DNS error made the shared pod temporarily unready and removed its Service
endpoint, even though existing peer connections could continue.

The configured mitigation uses `DNS_UPSTREAM_RESOLVER_TYPE=doh` with
`DNS_UPSTREAM_RESOLVERS=cloudflare,google`. Queries stay encrypted inside the
VPN and use HTTPS port 443 instead of the affected DNS-over-TLS port 853.
This is a response to the observed route failure, not proof of which network
operator reset the connection. Neither upstream availability nor long-term
VPN stability is guaranteed; compare logs and probe timings after deployment.
See Gluetun's [DNS settings](https://github.com/qdm12/gluetun-wiki/blob/main/setup/options/dns.md).

The availability watchdog also requires 15 continuous minutes of Deployment
unavailability before requesting a restart. A single failed readiness check
must not cause an unrelated five-minute CronJob to restart qBittorrent and
interrupt all its peers. Container startup/liveness probes remain responsible
for recovering a persistently unhealthy Gluetun container during that grace
period. Missing or ambiguous availability timestamps do not trigger a restart.

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

## Older shows: when auto-search never finds anything

Recurring theme (Ed Edd n Eddy, Johnny Bravo, Kim Possible, JoJo):
the custom-format rules are fine — old/niche shows fail for exactly
three reasons. Diagnose in this order:

1. **Dead seeds.** Interactive search shows releases but all rejected
   `Not enough seeders`. No setting fixes a dead torrent.
2. **Bundle-only availability.** The content only exists as a
   multi-season / "Complete Series" pack. Sonarr structurally cannot
   grab those — no profile or format change will ever help.
3. **Unparseable folder names** (mostly anime: "Part 1 & Part 2").
   The pack downloads but sits `importPending` in Activity → Queue
   with a warning. Fix: the orange icon → Manual Import (filenames
   are usually fine).

The playbook for 1 and 2 — grab the bundle directly, import manually:

```bash
# find what actually exists (raw search across all indexers)
curl -H "X-Api-Key: $PROWLARR_KEY" \
  "https://prowlarr.alucard.dev/api/v1/search?query=<show>&type=search&limit=100"
# push the chosen release's downloadUrl/magnetUrl into qbt under
# sonarr's category (single-season packs auto-import on completion)
curl -X POST http://qbittorrent:8080/api/v2/torrents/add \
  --data-urlencode "urls=<url>" --data-urlencode "category=tv-sonarr"
```

Single-season pack with a clean name → Sonarr imports it like its own
grab. Multi-season bundle → after completion use Sonarr's Manual Import
(Wanted → Manual Import, or the API) pointed at the season subfolder;
movies bundled inside go to Radarr the same way (add the movie first,
unmonitored, then Manual Import). Leftover unimported seasons stay in
`/data/downloads` — delete the torrent (with files) after seeding if
you don't want them; imported seasons are hardlinked and unaffected.

The systemic fix, if these keep annoying: a usenet indexer + client
(SABnzbd) — old content has no seeder problem there, but it's a paid
provider (~$5-10/mo). Slots into the existing layout; ask when wanted.

## Compact season packs rejected by size or existing episodes

Archer S05/S06 exposed a separate problem from dead seeds: complete 1080p
HEVC packs (~1.2–1.3 GiB for 13 episodes) were below Sonarr's 4 MB/min minimum.
The S06 pack had 59 reported seeders and only a size rejection. The S05 pack
also conflicted with the existing S05E09 WEB-DL file's higher source preference.

`apps/media/recyclarr.yaml` now declares the Sonarr `series` quality definition:
HDTV/WEB 720p minimum **2 MB/min**, HDTV/WEB 1080p minimum **3 MB/min**.
These settings are global to all Sonarr profiles and codecs, not just Archer
or HEVC. Maximum/preferred sizes and other quality minima retain the observed
live values via explicit overrides. SD/Unknown/Raw-HD are outside the guide's
series table and are not managed by this definition. Radarr is unaffected.
The tradeoff is accepting more heavily compressed HD releases; resolution and
language checks still apply. Recyclarr 8.6.0 supports these per-quality overrides:
see [the configuration reference](https://recyclarr.dev/reference/configuration/quality-definition/).

After PR merge and Flux reconciliation, the existing Recyclarr CronJob applies
the settings at **05:00 UTC**. Flux updating the ConfigMap does not immediately
change Sonarr settings. Do not create an ad-hoc Job or change Sonarr by hand to
accelerate this; use the scheduled reconciliation. Re-run an interactive search
after the sync to verify the size rejection is gone. Existing monitored episodes
do not automatically get a new backlog search just because settings changed.

For an immediate, explicitly approved exception, use Sonarr's **Interactive
Search → Manual Grab** for the verified single-season pack. This overrides grab
rejections and records the download in Sonarr history, with the `tv-sonarr`
category for normal completed-download handling. Check qBittorrent's file list
for all intended episode numbers and monitor Sonarr's queue after completion.
An existing higher-preference episode may remain; that is not a reason to delete
it. If the pack remains import-pending, inspect the individual import reasons.

Lowering size minima does **not** fix `Unknown Series` (for example, misleading
`Archer (2010)` release titles) or existing-file season-pack conflicts. Verify
identity and contents before manually grabbing those; do not weaken global
language/source rules or delete existing episodes to bypass the rejection.

## Going further (optional, not yet installed)

- **Bazarr** (subtitles) — slots into the existing layout; ask when
  wanted. (Recyclarr and the gluetun VPN sidecar are now deployed:
  `apps/media/recyclarr.yaml` syncs TRaSH language/quality policy
  nightly, and qBittorrent notifies `#downloads:alucard.dev` on
  completion via `apps/media/qbittorrent.yaml`.)
- **Jellyfin**: deliberately not deployed — Pi 4 has no usable container
  transcode path. Direct-play-only is possible; running it on the UNAS
  is likely better.
