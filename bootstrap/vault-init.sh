#!/usr/bin/env bash
# Initialize and configure the production (raft) Vault.
#
# Idempotent: safe to re-run. Run from a workstation with kubectl access.
#
# Fresh install:  ./vault-init.sh
#   - initializes Vault (1 key share), prints the unseal key + root token
#     ONCE - store both in your password manager immediately
# Re-run / after pod restart:
#   VAULT_UNSEAL_KEY=... ./vault-init.sh          (unseal only)
#   VAULT_UNSEAL_KEY=... VAULT_ROOT_TOKEN=... ./vault-init.sh   (full re-apply)
#
# Disaster recovery from a raft snapshot does NOT use this script's init
# path - see docs/runbooks/disaster-recovery.md.
set -euo pipefail

NS=vault
POD=vault-0
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
POLICY_DIR="$REPO_ROOT/infrastructure/base/vault/policies"

# Namespaces whose external-secrets-sa may authenticate (tighten to
# 'external-secrets' once the ClusterSecretStore migration lands).
ESO_NAMESPACES="external-secrets,atproto,matrix,authentik,gitea,cert-manager,tekton-pipelines"

vexec() {
  kubectl exec -n "$NS" "$POD" -- env VAULT_TOKEN="${VAULT_ROOT_TOKEN:-}" vault "$@"
}

echo "==> waiting for $POD"
kubectl wait -n "$NS" pod/"$POD" --for=condition=PodScheduled --timeout=300s >/dev/null
until kubectl exec -n "$NS" "$POD" -- vault status -format=json >/dev/null 2>&1; do
  # vault status exits non-zero while sealed/uninitialized but still answers;
  # only retry if the container itself isn't responding yet
  kubectl exec -n "$NS" "$POD" -- vault status >/dev/null 2>&1 && break
  sleep 3
done

INITIALIZED=$(kubectl exec -n "$NS" "$POD" -- vault status -format=json 2>/dev/null | grep -o '"initialized": *[a-z]*' | grep -o '[a-z]*$' || echo false)

if [ "$INITIALIZED" != "true" ]; then
  echo "==> initializing (1 share / threshold 1)"
  INIT_OUT=$(kubectl exec -n "$NS" "$POD" -- vault operator init -key-shares=1 -key-threshold=1 -format=json)
  VAULT_UNSEAL_KEY=$(echo "$INIT_OUT" | grep -o '"unseal_keys_b64": *\[ *"[^"]*"' | grep -o '[^"]*"$' | tr -d '"')
  VAULT_ROOT_TOKEN=$(echo "$INIT_OUT" | grep -o '"root_token": *"[^"]*"' | cut -d'"' -f4)
  echo
  echo "############################################################"
  echo "  STORE THESE IN YOUR PASSWORD MANAGER NOW - shown once."
  echo "  Unseal key: $VAULT_UNSEAL_KEY"
  echo "  Root token: $VAULT_ROOT_TOKEN"
  echo "############################################################"
  echo
fi

SEALED=$(kubectl exec -n "$NS" "$POD" -- vault status -format=json 2>/dev/null | grep -o '"sealed": *[a-z]*' | grep -o '[a-z]*$' || echo true)
if [ "$SEALED" = "true" ]; then
  [ -n "${VAULT_UNSEAL_KEY:-}" ] || { echo "ERROR: sealed and no VAULT_UNSEAL_KEY set"; exit 1; }
  echo "==> unsealing"
  kubectl exec -n "$NS" "$POD" -- vault operator unseal "$VAULT_UNSEAL_KEY" >/dev/null
fi

[ -n "${VAULT_ROOT_TOKEN:-}" ] || { echo "unsealed; no VAULT_ROOT_TOKEN set, skipping configuration"; exit 0; }

echo "==> enabling KV v2 at secret/ (if absent)"
vexec secrets enable -path=secret kv-v2 2>/dev/null || true

echo "==> enabling + configuring kubernetes auth"
vexec auth enable kubernetes 2>/dev/null || true
vexec write auth/kubernetes/config \
  kubernetes_host="https://kubernetes.default.svc:443" >/dev/null

echo "==> writing policies"
kubectl exec -n "$NS" "$POD" -i -- env VAULT_TOKEN="$VAULT_ROOT_TOKEN" \
  vault policy write external-secrets - <"$POLICY_DIR/external-secrets.hcl" >/dev/null
kubectl exec -n "$NS" "$POD" -i -- env VAULT_TOKEN="$VAULT_ROOT_TOKEN" \
  vault policy write vault-snapshot - <"$POLICY_DIR/vault-snapshot.hcl" >/dev/null

echo "==> creating auth roles"
vexec write auth/kubernetes/role/external-secrets \
  bound_service_account_names=external-secrets-sa \
  bound_service_account_namespaces="$ESO_NAMESPACES" \
  policies=external-secrets \
  ttl=1h >/dev/null
vexec write auth/kubernetes/role/vault-snapshot \
  bound_service_account_names=vault-snapshot \
  bound_service_account_namespaces=vault \
  policies=vault-snapshot \
  ttl=15m >/dev/null

echo "==> done. import secrets next (see scratch vault-import.py or 'vault kv put')."
