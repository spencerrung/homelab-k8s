# 1. Flux GitOps with tiered Kustomizations

Accepted 2025-10 (initial), restructured 2026-07.

Everything post-k3s is declared in this repo and reconciled by Flux. The
cluster state is layered as dependency tiers (`sources →
infra-controllers → infra-configs → platform-apps / apps-web /
apps-stateful`, plus `monitoring → monitoring-configs`) instead of the
original two mega-Kustomizations, so failures have small blast radius,
tiers carry explicit healthChecks, and CRD instances never share a layer
with the chart that installs their CRDs (Flux dry-runs everything before
applying).
