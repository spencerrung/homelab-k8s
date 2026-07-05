# ARM64 / Raspberry Pi notes

Everything in this repo runs on arm64 (Raspberry Pi 4B). The evergreen
rules:

## Before adding any image

```bash
docker manifest inspect <image:tag> | jq '.manifests[].platform.architecture'
# or: crane manifest <image:tag> | jq ...
```

If there's no `arm64` entry, find another image or build multi-arch
yourself (Tekton/kaniko builds in this cluster produce arm64 natively).
Most official images (nginx, postgres, redis, traefik, prometheus,
grafana, vault, linuxserver.io) are multi-arch; niche projects and older
tags often are not — check per-tag, not per-repo.

## Sizing on Pi 4B

- Fleet: 6×8GB, 1×4GB, 2×2GB. Set requests AND limits on everything; the
  2GB nodes will OOM otherwise. DaemonSets must fit the 2GB nodes.
- Heavy stateful things (Prometheus, Loki, Vault, databases) are pinned to
  specific 8GB nodes via `nodeSelector` — partly for memory, partly
  because local-path PVC data is node-local anyway.
- SD-card/SSD IO is the usual bottleneck, not CPU. Prometheus/Loki/postgres
  prefer nodes with SSDs; watch node IO-wait when things feel slow.
- JVM- and Electron-adjacent images (GitLab, large Java apps) are painful
  on Pi 4 — prefer Go/Rust-based alternatives (see
  [ADR 4](decisions/0004-gitea-over-gitlab.md)).

## Gotchas seen in practice

- Some charts default amd64-only sidecars (metrics exporters, test
  hooks) — disable or override them if pods ImagePullBackOff on
  `no matching manifest for linux/arm64`.
- `:latest` on multi-arch repos can regress arm64 support silently —
  another reason everything is pinned.
