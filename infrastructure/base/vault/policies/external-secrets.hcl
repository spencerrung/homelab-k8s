# Read-only access to the KV v2 mount for External Secrets Operator.
# Applied by bootstrap/vault-init.sh.
path "secret/data/*" {
  capabilities = ["read"]
}

path "secret/metadata/*" {
  capabilities = ["read", "list"]
}
