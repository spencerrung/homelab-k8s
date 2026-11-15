# Media upgrade — November 2026

| Component | Previous | Target |
|---|---|---|
| Sonarr | 4.0.19 | 4.0.20 |
| Radarr | 6.2.1 | 6.4.4 |
| Prowlarr | 2.4.0 | 2.7.0 |
| Bazarr | 1.6.0 | 1.6.2 |
| Jellyseerr → Seerr | 2.7.3 | 3.5.2 |
| qBittorrent | 5.2.2 | 5.3.0 |
| Gluetun | 3.41.1 | 3.41.3 |
| FlareSolverr | 3.5.0 | 3.5.2 |
| Recyclarr | 8.6.0 | 8.8.1 |
| PostgreSQL | running 16.14, floating 16-alpine | 16.16-alpine |
| Anime guard Python | 3.12.13 | 3.12.16 |

The watchdog stays on Kubernetes 1.29.10, matching the cluster. PostgreSQL
stays on major 16; a major database migration is a separate operation.
All target images publish ARM64 manifests.

## Compatibility checks

- Seerr's [official migration guide](https://docs.seerr.dev/migration-guide/)
  requires a backup and uses UID/GID 1000. The Deployment retains its resource,
  Service and PVC names, URL, and connections. Its pod security context grants
  the non-root image access to the existing PVC and shared patch directory.
- Seerr 3.5.2 still searches an entire existing series by default. Keep the
  fail-closed season-search patch. Tests execute the compiled target image
  module with mocked APIs and verify requested seasons, deduplication, preserved
  monitoring, disabled searches, empty requests, new-series behavior and the
  newly added episode re-monitoring behavior. No live search is needed.
- An isolated Docker container with **no network** successfully migrated a copy
  of the current Seerr database/config. SQLite integrity and user/media/request
  row counts were preserved, as were Sonarr/Radarr/Plex/Jellyfin settings.
  Upstream adds notification defaults and renames blacklist settings to blocklist.
- Recyclarr 8.8.1 preview successfully reads both services with the existing
  config. Keep the 05:00 UTC scheduled sync; do not run a mutating ad-hoc sync.
  Language scores, anime exceptions, naming and compact-pack sizes are unchanged.
- qBittorrent 5.3.0 retains jq and curl with c-ares support for `--dns-servers`.
  Preserve the completion hook, categories, paths, memory setting and auth
  whitelist. Test Matrix with a read-only endpoint, not a test notification.
- Gluetun 3.41.3 fixes a port-forwarding deadlock. Preserve PIA region,
  UDP/1197, MTU/MSS, DoH, kill switch, firewall rules and forwarding hook.
- Radarr/Prowlarr add hostname validation. Empty AllowedHosts retains existing
  access behavior; test both service DNS and public ingress after rollout.
- Bazarr's new postprocessing argument handling does not affect the current
  configuration: custom postprocessing is disabled with an empty command.

## Backups and rollback

Private backups for this run are on the operator workstation under
`~/homelab-backups/media-20261115/` (outside Git, restricted permissions):
PostgreSQL `pg_dumpall`, app config archives, consistent Jellyseerr/Bazarr
SQLite snapshots, and Arr/qBittorrent settings baselines. Arr built-in manual
backups were also taken. The shared `/data` library is not copied or modified
by these backup operations.

An image downgrade alone is not a database rollback. If a schema migration
fails, first stop the affected app through a reviewed GitOps change, preserve
its failed state, restore its pre-upgrade database/config with the matching
old image, and then resume. Restore the PostgreSQL dump only after stopping
both Arr writers and confirming which databases require recovery. For Seerr,
use the consistent `jellyseerr-db.sqlite3` in place of the archive's live DB,
removing stale WAL/SHM files while stopped. Preserve current media files.

After Flux reconciliation, verify readiness, actual versions, unchanged
quality/custom-format/naming rules and integration settings, downloader
connectivity, VPN DNS/forwarded port, request UI and browser-backed
FlareSolverr response. Keep any transient indexer failures distinct from
migration failures. Preview checks do not exercise real downloads/imports.
