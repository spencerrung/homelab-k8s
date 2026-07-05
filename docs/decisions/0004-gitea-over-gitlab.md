# 4. Gitea over GitLab

Accepted 2025-11; GitLab remnants removed 2026-07.

GitLab was deployed first but is far too heavy for Raspberry Pi 4 nodes
(multi-GB memory footprint, slow arm64 performance). Gitea provides git
hosting, OIDC login via Authentik, a container registry, and webhooks for
Tekton at a fraction of the footprint. CI runs on Tekton rather than
GitLab CI. The deploy registry for cluster workloads is Docker Hub, not
the in-cluster Gitea registry, so images survive cluster loss
(DR consideration).
