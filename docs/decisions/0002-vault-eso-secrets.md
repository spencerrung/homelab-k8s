# 2. Vault + External Secrets Operator for secrets

Accepted 2025-10; hardened 2026-07.

Secrets live in Vault (prod mode, single-node raft on a PVC), rendered
into k8s Secrets by ESO through one ClusterSecretStore. Nothing secret is
committed to git. Trade-off accepted: a vault pod restart leaves it sealed
until a human runs the unseal script — workloads keep running on rendered
Secrets, and monitoring alerts on the failure. Auto-unseal was rejected
because storing the unseal key in-cluster defeats the seal, and cloud KMS
adds an external dependency. SOPS-in-git was rejected to keep a single
runtime source of truth with k8s-auth access control.

tofu-controller (which originally configured Vault) was removed 2026-07:
it managed ~30 lines of Vault config with plaintext seeds in git; replaced
by `bootstrap/vault-init.sh` + policy files.
